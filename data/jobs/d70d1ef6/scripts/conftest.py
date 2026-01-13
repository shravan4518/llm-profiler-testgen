"""
conftest.py

Pytest configuration and fixtures for Playwright-based UI test automation.

Features:
- Async Playwright (chromium) browser fixture
- Authenticated page with session reuse
- Test data management fixture
- Automatic screenshot capture on failure
- Configurable base URL, environment, credentials
- Structured logging setup
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional

import pytest
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, Error

# =============================================================================
# Logging configuration
# =============================================================================

LOG_DIR = Path("logs")
LOG_DIR.mkdir(parents=True, exist_ok=True)

def _configure_root_logger() -> logging.Logger:
    logger = logging.getLogger()
    if logger.handlers:
        # Avoid adding multiple handlers when reloading
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File handler (rotating per run)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    fh = logging.FileHandler(LOG_DIR / f"test_run_{timestamp}.log", encoding="utf-8")
    fh.setLevel(logging.INFO)
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    logger.info("Logger initialized")
    return logger


LOGGER = _configure_root_logger()

# =============================================================================
# Pytest hooks
# =============================================================================

def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Register custom command line options.
    """
    group = parser.getgroup("playwright")

    group.addoption(
        "--env",
        action="store",
        default=os.getenv("TEST_ENV", "dev"),
        help="Target environment (default: dev)",
    )

    group.addoption(
        "--base-url",
        action="store",
        default=os.getenv(
            "BASE_URL",
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
        ),
        help="Base URL for the application under test",
    )

    group.addoption(
        "--headless",
        action="store",
        default=os.getenv("HEADLESS", "true"),
        choices=["true", "false"],
        help="Run browser in headless mode (true/false). Default: true",
    )

    group.addoption(
        "--browser-timeout",
        action="store",
        type=int,
        default=int(os.getenv("BROWSER_TIMEOUT", "30000")),
        help="Default timeout for Playwright operations in ms (default: 30000)",
    )

    group.addoption(
        "--username",
        action="store",
        default=os.getenv("APP_USERNAME", "shravan"),
        help="Application username (default: shravan, override via env or CLI)",
    )

    group.addoption(
        "--password",
        action="store",
        default=os.getenv("APP_PASSWORD", ""),
        help="Application password (recommended: set APP_PASSWORD env var)",
    )


def pytest_configure(config: pytest.Config) -> None:
    """
    Global pytest configuration hook.
    """
    LOGGER.info("Pytest configuration initialized")
    LOGGER.info("Environment: %s", config.getoption("--env"))
    LOGGER.info("Base URL: %s", config.getoption("--base-url"))
    LOGGER.info("Headless: %s", config.getoption("--headless"))
    LOGGER.info("Browser timeout (ms): %s", config.getoption("--browser-timeout"))


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Hook to attach test outcome to the item object for later use
    (e.g., in fixtures to know if a test failed).
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


# =============================================================================
# Event loop fixture (for async Playwright usage)
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Create an event loop for the entire test session.
    This is required when using pytest-asyncio with scope=session.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# =============================================================================
# Configuration fixtures
# =============================================================================

@pytest.fixture(scope="session")
def env(pytestconfig: pytest.Config) -> str:
    return pytestconfig.getoption("--env")


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    """
    Base URL of the application under test.
    """
    url = pytestconfig.getoption("--base-url")
    if not url:
        LOGGER.error("Base URL is not configured.")
        raise RuntimeError("Base URL must be provided via --base-url or BASE_URL env var")
    return url


@pytest.fixture(scope="session")
def app_credentials(pytestconfig: pytest.Config) -> Dict[str, str]:
    """
    Provide application credentials. Password should be provided via environment
    variable or secure secrets storage; CLI is supported but not recommended.
    """
    username = pytestconfig.getoption("--username")
    password = pytestconfig.getoption("--password")

    if not password:
        LOGGER.warning(
            "Application password not provided. "
            "Set APP_PASSWORD env var or use --password for local runs."
        )
    return {"username": username, "password": password}


@pytest.fixture(scope="session")
def browser_timeout(pytestconfig: pytest.Config) -> int:
    """
    Browser default timeout in milliseconds.
    """
    return int(pytestconfig.getoption("--browser-timeout"))


@pytest.fixture(scope="session")
def headless(pytestconfig: pytest.Config) -> bool:
    """
    Whether to run browser in headless mode.
    """
    return pytestconfig.getoption("--headless").lower() == "true"


# =============================================================================
# Playwright and Browser fixtures
# =============================================================================

@pytest.fixture(scope="session")
async def playwright_instance() -> AsyncGenerator[Playwright, None]:
    """
    Start Playwright for the entire session.
    """
    LOGGER.info("Starting Playwright...")
    try:
        async with async_playwright() as p:
            yield p
    except Exception as exc:
        LOGGER.exception("Failed to start Playwright: %s", exc)
        raise
    finally:
        LOGGER.info("Playwright stopped")


@pytest.fixture(scope="session")
async def browser(
    playwright_instance: Playwright,
    headless: bool,
    browser_timeout: int,
) -> AsyncGenerator[Browser, None]:
    """
    Provide a Chromium browser instance for the entire test session.
    """
    LOGGER.info("Launching Chromium browser (headless=%s)...", headless)
    try:
        browser = await playwright_instance.chromium.launch(
            headless=headless,
            args=[
                "--start-maximized",
                "--ignore-certificate-errors",  # for self-signed certs on internal URLs
            ],
        )
        yield browser
    except Error as exc:
        LOGGER.exception("Playwright browser error: %s", exc)
        raise
    except Exception as exc:
        LOGGER.exception("Failed to launch Chromium browser: %s", exc)
        raise
    finally:
        try:
            LOGGER.info("Closing Chromium browser...")
            await browser.close()
        except Exception as exc:
            LOGGER.warning("Error while closing browser: %s", exc)


@pytest.fixture(scope="session")
async def browser_context(
    browser: Browser,
    browser_timeout: int,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Provide a browser context for the entire session.
    This context is used for authenticated session reuse.
    """
    LOGGER.info("Creating browser context (viewport=1920x1080)...")
    context: Optional[BrowserContext] = None
    try:
        context = await browser.new_context(
            viewport={"width": 1920, "height": 1080},
            ignore_https_errors=True,
        )
        context.set_default_timeout(browser_timeout)
        yield context
    except Exception as exc:
        LOGGER.exception("Failed to create browser context: %s", exc)
        raise
    finally:
        if context:
            try:
                LOGGER.info("Closing browser context...")
                await context.close()
            except Exception as exc:
                LOGGER.warning("Error while closing browser context: %s", exc)


@pytest.fixture(scope="function")
async def page(
    browser_context: BrowserContext,
) -> AsyncGenerator[Page, None]:
    """
    Provide a fresh Page for each test function.
    """
    LOGGER.debug("Opening new page for test...")
    page: Optional[Page] = None
    try:
        page = await browser_context.new_page()
        yield page
    except Exception as exc:
        LOGGER.exception("Error during page usage: %s", exc)
        raise
    finally:
        if page:
            try:
                LOGGER.debug("Closing page...")
                await page.close()
            except Exception as exc:
                LOGGER.warning("Error while closing page: %s", exc)


# =============================================================================
# Authentication and session reuse
# =============================================================================

SESSION_STATE_PATH = Path(".auth") / "dev_auth_state.json"
SESSION_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)


async def _perform_login(
    page: Page,
    base_url: str,
    username: str,
    password: str,
) -> None:
    """
    Perform login on the target system.

    NOTE: This function uses generic selectors as the actual DOM is unknown.
    Update selectors according to the real login page implementation.
    """
    LOGGER.info("Navigating to login page: %s", base_url)
    await page.goto(base_url, wait_until="networkidle")

    # Example selectors - must be adjusted to actual application
    try:
        # Replace '#username', '#password', '#loginBtn' with real selectors
        await page.fill("#username", username)
        await page.fill("#password", password)
        await page.click("#loginBtn")
    except Error as exc:
        LOGGER.exception("Playwright error during login interaction: %s", exc)
        raise
    except Exception as exc:
        LOGGER.exception("Unexpected error during login interaction: %s", exc)
        raise

    # Validate successful login
    # Replace this with a robust condition, such as checking for a specific URL,
    # element, or text that appears only after successful login.
    try:
        await page.wait_for_load_state("networkidle")
        # Example: wait for an element that indicates successful login
        # await page.wait_for_selector("text=Dashboard", timeout=15000)
    except Error as exc:
        LOGGER.exception("Login likely failed; page did not reach expected state: %s", exc)
        raise RuntimeError("Login did not reach expected post-login state") from exc

    LOGGER.info("Login completed successfully")


@pytest.fixture(scope="session")
async def authenticated_context(
    browser: Browser,
    base_url: str,
    app_credentials: Dict[str, str],
    browser_timeout: int,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Provide an authenticated browser context with session reuse.

    - On first run, logs in and saves storage state to SESSION_STATE_PATH.
    - On subsequent runs, loads storage state to avoid re-logging.
    """
    LOGGER.info("Preparing authenticated browser context...")

    context: Optional[BrowserContext] = None
    try:
        if SESSION_STATE_PATH.exists():
            LOGGER.info("Loading existing auth state from %s", SESSION_STATE_PATH)
            context = await browser.new_context(
                storage_state=str(SESSION_STATE_PATH),
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )
        else:
            LOGGER.info("Auth state not found. Performing login and saving session.")
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                ignore_https_errors=True,
            )
            context.set_default_timeout(browser_timeout)
            page = await context.new_page()
            try:
                await _perform_login(
                    page=page,
                    base_url=base_url,
                    username=app_credentials["username"],
                    password=app_credentials["password"],
                )
                LOGGER.info("Saving authenticated storage state to %s", SESSION_STATE_PATH)
                await context.storage_state(path=str(SESSION_STATE_PATH))
            finally:
                await page.close()

        context.set_default_timeout(browser_timeout)
        yield context
    except Exception as exc:
        LOGGER.exception("Failed to create authenticated context: %s", exc)
        raise
    finally:
        if context:
            try:
                LOGGER.info("Closing authenticated context...")
                await context.close()
            except Exception as exc:
                LOGGER.warning("Error while closing authenticated context: %s", exc)


@pytest.fixture(scope="function")
async def authenticated_page(
    authenticated_context: BrowserContext,
) -> AsyncGenerator[Page, None]:
    """
    Provide an authenticated Page for each test function.
    """
    LOGGER.debug("Opening authenticated page for test...")
    page: Optional[Page] = None
    try:
        page = await authenticated_context.new_page()
        yield page
    except Exception as exc:
        LOGGER.exception("Error during authenticated page usage: %s", exc)
        raise
    finally:
        if page:
            try:
                LOGGER.debug("Closing authenticated page...")
                await page.close()
            except Exception as exc:
                LOGGER.warning("Error while closing authenticated page: %s", exc)


# =============================================================================
# Test data management fixture
# =============================================================================

@pytest.fixture(scope="session")
def test_data(env: str) -> Dict[str, Any]:
    """
    Provide test data based on environment.

    In a real project this might load from JSON/YAML files, a database,
    or a config service. For now, we return a simple dictionary that can
    be expanded as needed.
    """
    LOGGER.info("Loading test data for environment: %s", env)

    # Example structure – extend as needed
    data: Dict[str, Any] = {
        "env": env,
        "default_timeout_seconds": 30,
        "users": {
            "admin": {
                "username": "shravan",
                "roles": ["admin"],
            }
        },
        "ui": {
            "login_page_title": "Login",
            "home_page_title": "Home",
        },
    }

    return data


# =============================================================================
# Screenshot on failure fixture
# =============================================================================

SCREENSHOT_DIR = Path("artifacts") / "screenshots"
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


@pytest.fixture(scope="function", autouse=True)
async def screenshot_on_failure(
    request: pytest.FixtureRequest,
    page: Page = None,  # type: ignore[assignment]
) -> AsyncGenerator[None, None]:
    """
    Automatically capture a screenshot on test failure.

    This fixture assumes that a `page` fixture is available in the test.
    If the test uses `authenticated_page` only, you can:
    - rename `authenticated_page` to `page`, or
    - add a second fixture like this one that uses `authenticated_page`.

    The fixture is autouse, so it runs for every test function.
    """
    yield

    # At this point, the test has finished executing.
    # We check the outcome and take a screenshot if it failed.
    rep = getattr(request.node, "rep_call", None)
    if rep is None or rep.passed:
        return

    if page is None:
        # Test might not use the `page` fixture; nothing to screenshot.
        LOGGER.debug("No page fixture available; skipping screenshot.")
        return

    test_name = request.node.name
    safe_test_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in test_name)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_name = f"{safe_test_name}_{timestamp}.png"
    screenshot_path = SCREENSHOT_DIR / file_name

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
        LOGGER.info("Screenshot saved for failed test '%s' at %s", test_name, screenshot_path)
    except Exception as exc:
        LOGGER.warning("Failed to capture screenshot for test '%s': %s", test_name, exc)