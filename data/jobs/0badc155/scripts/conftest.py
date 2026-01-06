"""
conftest.py

Pytest configuration and fixtures for Playwright-based test automation using
the async API. Provides:

- Logging setup
- Base URL / environment configuration
- Async Playwright + browser / context / page fixtures
- Authenticated page fixture (login once per session, reuse context)
- Test data management fixture
- Automatic screenshot capture on failure
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, Generator, Optional

import pytest
from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Page,
)

# =============================================================================
# Global configuration / constants
# =============================================================================

DEFAULT_ENV = "dev"
DEFAULT_BROWSER = "chromium"
DEFAULT_BASE_URL = "https://npre-miiqa2mp-eastus2.openai.azure.com/"

# Credentials:
# NOTE: Password is intentionally not hard-coded. It must be provided via
# environment variable or a secure secrets manager.
USERNAME = "shravan"
PASSWORD_ENV_VAR = "TEST_PASSWORD"  # set this in your environment securely

# Playwright config
HEADLESS = True
VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_TIMEOUT_MS = 30_000  # 30 seconds


# =============================================================================
# Logging setup
# =============================================================================

def _create_log_directory() -> Path:
    logs_dir = Path("logs")
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def _configure_root_logger() -> None:
    """Configure root logger for test run."""
    logs_dir = _create_log_directory()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    log_file = logs_dir / f"test_run_{timestamp}.log"

    # Basic configuration
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(log_file, encoding="utf-8"),
        ],
    )

    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("playwright").setLevel(logging.INFO)


# Configure logging as soon as the module is imported
_configure_root_logger()
logger = logging.getLogger(__name__)


# =============================================================================
# Pytest hooks
# =============================================================================

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    group = parser.getgroup("playwright")
    group.addoption(
        "--env",
        action="store",
        default=DEFAULT_ENV,
        help="Target environment (default: dev)",
    )
    group.addoption(
        "--base-url",
        action="store",
        default=DEFAULT_BASE_URL,
        help=f"Base URL for the application (default: {DEFAULT_BASE_URL})",
    )
    group.addoption(
        "--browser",
        action="store",
        default=DEFAULT_BROWSER,
        choices=["chromium", "firefox", "webkit"],
        help="Browser type for Playwright (default: chromium)",
    )
    group.addoption(
        "--headed",
        action="store_true",
        default=False,
        help="Run browser in headed mode (default: headless)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Pytest configuration hook."""
    logger.info("Pytest configuration initialized")
    logger.info("Environment: %s", config.getoption("--env"))
    logger.info("Base URL: %s", config.getoption("--base-url"))
    logger.info("Browser: %s", config.getoption("--browser"))
    logger.info("Headless: %s", not config.getoption("--headed"))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo) -> Any:
    """
    Hook to access test outcome and attach it to the test item.

    This is used later by fixtures to decide whether to take screenshots
    on failure.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)


# =============================================================================
# Session-level configuration fixtures
# =============================================================================

@pytest.fixture(scope="session")
def env(pytestconfig: pytest.Config) -> str:
    """Current test environment (e.g., dev, qa, prod)."""
    return pytestconfig.getoption("--env")


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    """Base URL for the application under test."""
    url = pytestconfig.getoption("--base-url")
    if not url.endswith("/"):
        url = url + "/"
    return url


@pytest.fixture(scope="session")
def browser_name(pytestconfig: pytest.Config) -> str:
    """Browser name (chromium, firefox, webkit)."""
    return pytestconfig.getoption("--browser")


@pytest.fixture(scope="session")
def headless(pytestconfig: pytest.Config) -> bool:
    """Whether to run browser in headless mode."""
    return not pytestconfig.getoption("--headed")


@pytest.fixture(scope="session")
def test_password() -> str:
    """
    Securely obtain the password for authentication.

    The password must be provided via environment variable TEST_PASSWORD.
    """
    pwd = os.getenv(PASSWORD_ENV_VAR)
    if not pwd:
        logger.error(
            "Environment variable %s is not set. Cannot run authenticated tests.",
            PASSWORD_ENV_VAR,
        )
        raise RuntimeError(
            f"Missing required environment variable: {PASSWORD_ENV_VAR}"
        )
    return pwd


# =============================================================================
# Async Playwright / Browser fixtures
# =============================================================================

@pytest.fixture(scope="session")
async def playwright_instance() -> AsyncGenerator[Any, None]:
    """Start and stop Playwright (async)."""
    logger.info("Starting Playwright")
    try:
        async with async_playwright() as p:
            yield p
    except Exception as exc:
        logger.exception("Error during Playwright session: %s", exc)
        raise
    finally:
        logger.info("Playwright session closed")


@pytest.fixture(scope="session")
async def browser(
    playwright_instance: Any,
    browser_name: str,
    headless: bool,
) -> AsyncGenerator[Browser, None]:
    """Create a shared browser instance for the entire test session."""
    logger.info("Launching browser: %s (headless=%s)", browser_name, headless)
    browser: Optional[Browser] = None
    try:
        launch_args = {
            "headless": headless,
            "timeout": DEFAULT_TIMEOUT_MS,
        }
        browser = await getattr(playwright_instance, browser_name).launch(**launch_args)
        logger.info("Browser launched successfully")
        yield browser
    except PlaywrightError as exc:
        logger.exception("Failed to launch %s browser: %s", browser_name, exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error launching browser: %s", exc)
        raise
    finally:
        if browser:
            logger.info("Closing browser")
            try:
                await browser.close()
            except Exception as exc:
                logger.warning("Error while closing browser: %s", exc)


@pytest.fixture(scope="session")
async def auth_context(
    browser: Browser,
    base_url: str,
    test_password: str,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Authenticated browser context.

    - Logs in once per session.
    - Reuses the same context (and storage state) across tests.
    """
    logger.info("Creating authenticated browser context")
    context: Optional[BrowserContext] = None
    try:
        context = await browser.new_context(
            base_url=base_url,
            viewport=VIEWPORT,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)

        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)

        await _perform_login(page, base_url, USERNAME, test_password)

        yield context
    except Exception as exc:
        logger.exception("Error creating authenticated context: %s", exc)
        raise
    finally:
        if context:
            logger.info("Closing authenticated browser context")
            try:
                await context.close()
            except Exception as exc:
                logger.warning("Error while closing authenticated context: %s", exc)


async def _perform_login(page: Page, base_url: str, username: str, password: str) -> None:
    """
    Perform login on the application.

    Adjust selectors and flow according to your actual login page.
    """
    logger.info("Starting login flow for user '%s'", username)
    try:
        await page.goto(base_url, wait_until="load")
        logger.debug("Navigated to base URL: %s", base_url)

        # Example login flow – replace with real selectors.
        # These are placeholders; customize them for your AUT.
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        await page.click('button[type="submit"]')

        # Wait for a post-login element that indicates success
        # Replace this with a real selector (e.g., user menu, dashboard, etc.)
        await page.wait_for_load_state("networkidle")
        logger.info("Login successful for user '%s'", username)
    except PlaywrightError as exc:
        logger.exception("Playwright error during login: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error during login: %s", exc)
        raise


@pytest.fixture(scope="function")
async def page(
    browser: Browser,
    base_url: str,
) -> AsyncGenerator[Page, None]:
    """
    Fresh page for tests that do NOT require authentication.

    Each test gets a new context + page to ensure isolation.
    """
    logger.info("Creating new non-authenticated context and page")
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    try:
        context = await browser.new_context(
            base_url=base_url,
            viewport=VIEWPORT,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = await context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        yield page
    except Exception as exc:
        logger.exception("Error creating non-authenticated page: %s", exc)
        raise
    finally:
        if context:
            logger.info("Closing non-authenticated context")
            try:
                await context.close()
            except Exception as exc:
                logger.warning("Error while closing non-authenticated context: %s", exc)


@pytest.fixture(scope="function")
async def auth_page(
    auth_context: BrowserContext,
) -> AsyncGenerator[Page, None]:
    """
    Authenticated page fixture.

    Uses the session-level authenticated context and creates a new page
    per test function.
    """
    logger.info("Creating authenticated page for test")
    page: Optional[Page] = None
    try:
        page = await auth_context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        yield page
    except Exception as exc:
        logger.exception("Error creating authenticated page: %s", exc)
        raise
    finally:
        if page:
            logger.info("Closing authenticated page")
            try:
                await page.close()
            except Exception as exc:
                logger.warning("Error while closing authenticated page: %s", exc)


# =============================================================================
# Test data management fixture
# =============================================================================

@pytest.fixture(scope="function")
def test_data(request: pytest.FixtureRequest) -> Dict[str, Any]:
    """
    Test data fixture.

    Provides a mutable dictionary per test that can be used to store
    test-specific data.

    Example usage:
        def test_example(test_data):
            test_data["user"] = {"name": "Alice"}
    """
    nodeid = request.node.nodeid
    logger.debug("Initializing test data for: %s", nodeid)
    return {
        "test_name": nodeid,
        "env": request.config.getoption("--env"),
        "timestamp": datetime.utcnow().isoformat(),
    }


# =============================================================================
# Screenshot on failure
# =============================================================================

def _create_screenshot_directory() -> Path:
    screenshots_dir = Path("screenshots")
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    return screenshots_dir


@pytest.fixture(scope="function", autouse=True)
async def screenshot_on_failure(
    request: pytest.FixtureRequest,
) -> AsyncGenerator[None, None]:
    """
    Automatically capture a screenshot on test failure.

    This fixture runs for every test (autouse=True). It attempts to locate
    a `Page` instance from the test's fixtures (prefers 'auth_page' then 'page').
    """
    yield  # Run the test first

    # After test execution, check result and capture screenshot on failure
    item = request.node
    # We care about the "call" phase (actual test body)
    rep = getattr(item, "rep_call", None)
    if not rep or rep.passed or rep.skipped:
        return

    # Try to locate a Page instance among used fixtures
    page: Optional[Page] = None
    try:
        if "auth_page" in item.fixturenames:
            page = request.getfixturevalue("auth_page")  # type: ignore[assignment]
        elif "page" in item.fixturenames:
            page = request.getfixturevalue("page")  # type: ignore[assignment]
    except Exception as exc:
        logger.warning("Could not resolve page fixture for screenshot: %s", exc)

    if page is None:
        logger.debug("No page fixture found for test %s; skipping screenshot", item.name)
        return

    screenshots_dir = _create_screenshot_directory()
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    safe_name = item.nodeid.replace("/", "_").replace("::", "__").replace(" ", "_")
    screenshot_path = screenshots_dir / f"{safe_name}_{timestamp}.png"

    try:
        logger.info("Test failed; capturing screenshot: %s", screenshot_path)
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except PlaywrightError as exc:
        logger.warning("Playwright error while taking screenshot: %s", exc)
    except Exception as exc:
        logger.warning("Unexpected error while taking screenshot: %s", exc)


# =============================================================================
# Event loop fixture for async tests (if needed)
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> Generator[asyncio.AbstractEventLoop, None, None]:
    """
    Custom event loop for pytest-asyncio.

    This ensures a single event loop is used for the entire test session,
    which works better with Playwright's async API.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()