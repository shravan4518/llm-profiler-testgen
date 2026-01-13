"""
conftest.py

Pytest configuration and fixtures for Playwright-based test automation.

Features:
- Async Playwright (chromium) setup
- Headless by default, configurable via CLI
- Authenticated page fixture (session reuse)
- Test data management fixture
- Automatic screenshot on failure
- Centralized logging
"""

import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional

import pytest
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, Error as PWError


# =============================================================================
# CONSTANTS / DEFAULTS
# =============================================================================

DEFAULT_BASE_URL = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
DEFAULT_ENV = "dev"
DEFAULT_BROWSER = "chromium"
DEFAULT_HEADLESS = True
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_TIMEOUT = 30_000  # ms for Playwright

# Sensitive values should be injected via environment variables or secrets manager
DEFAULT_USERNAME = "shravan"
DEFAULT_PASSWORD_ENV_VAR = "TARGET_PASSWORD"  # must be set in environment


# =============================================================================
# PYTEST HOOKS - CLI OPTIONS & LOGGING
# =============================================================================

def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options for test run configuration."""
    group = parser.getgroup("playwright")
    group.addoption(
        "--base-url",
        action="store",
        default=DEFAULT_BASE_URL,
        help="Base URL for the target application.",
    )
    group.addoption(
        "--env",
        action="store",
        default=DEFAULT_ENV,
        help="Target environment (e.g., dev, qa, prod).",
    )
    group.addoption(
        "--browser",
        action="store",
        default=DEFAULT_BROWSER,
        choices=["chromium", "firefox", "webkit"],
        help="Browser type to use for Playwright tests.",
    )
    group.addoption(
        "--headed",
        action="store_true",
        default=not DEFAULT_HEADLESS,
        help="Run browser in headed mode (UI visible).",
    )
    group.addoption(
        "--screenshot-dir",
        action="store",
        default="artifacts/screenshots",
        help="Directory to store screenshots.",
    )
    group.addoption(
        "--pw-timeout",
        action="store",
        type=int,
        default=DEFAULT_TIMEOUT,
        help="Default Playwright timeout in milliseconds.",
    )


def _init_root_logger(log_level: int = logging.INFO) -> None:
    """Initialize root logger with console handler."""
    logger = logging.getLogger()
    if logger.handlers:
        # Already configured (e.g., by another conftest)
        return

    logger.setLevel(log_level)

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] [%(name)s] %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)


def pytest_configure(config: pytest.Config) -> None:
    """Global pytest configuration hook."""
    _init_root_logger()
    logging.getLogger(__name__).info("Pytest configuration initialized.")

    # Ensure screenshot directory exists
    screenshot_dir = Path(config.getoption("--screenshot-dir"))
    screenshot_dir.mkdir(parents=True, exist_ok=True)


# =============================================================================
# GLOBAL FIXTURES - CONFIGURATION
# =============================================================================

@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    """Base URL for the target system."""
    url = pytestconfig.getoption("--base-url")
    logging.getLogger(__name__).info("Using base URL: %s", url)
    return url


@pytest.fixture(scope="session")
def env(pytestconfig: pytest.Config) -> str:
    """Environment name (dev, qa, prod, etc.)."""
    environment = pytestconfig.getoption("--env")
    logging.getLogger(__name__).info("Test environment: %s", environment)
    return environment


@pytest.fixture(scope="session")
def browser_name(pytestconfig: pytest.Config) -> str:
    """Browser name to use with Playwright."""
    browser = pytestconfig.getoption("--browser")
    logging.getLogger(__name__).info("Browser selected: %s", browser)
    return browser


@pytest.fixture(scope="session")
def headed(pytestconfig: pytest.Config) -> bool:
    """Whether to run browser headed (UI visible)."""
    return pytestconfig.getoption("--headed")


@pytest.fixture(scope="session")
def pw_timeout(pytestconfig: pytest.Config) -> int:
    """Default timeout for Playwright operations (milliseconds)."""
    timeout = pytestconfig.getoption("--pw-timeout")
    logging.getLogger(__name__).info("Playwright default timeout: %d ms", timeout)
    return timeout


@pytest.fixture(scope="session")
def screenshot_dir(pytestconfig: pytest.Config) -> Path:
    """Directory to store screenshots."""
    directory = Path(pytestconfig.getoption("--screenshot-dir")).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    return directory


# =============================================================================
# PLAYWRIGHT & BROWSER FIXTURES (ASYNC)
# =============================================================================

@pytest.fixture(scope="session")
async def playwright_instance() -> AsyncGenerator[Playwright, None]:
    """
    Session-scoped Playwright instance.

    Ensures proper startup and shutdown of Playwright.
    """
    logger = logging.getLogger(__name__)
    logger.info("Starting Playwright...")
    try:
        async with async_playwright() as p:
            yield p
    except Exception as exc:
        logger.exception("Error during Playwright session: %s", exc)
        raise
    finally:
        logger.info("Playwright session finished.")


@pytest.fixture(scope="session")
async def browser(
    playwright_instance: Playwright,
    browser_name: str,
    headed: bool,
) -> AsyncGenerator[Browser, None]:
    """
    Session-scoped Browser fixture.

    Uses Chromium by default; configurable via CLI.
    """
    logger = logging.getLogger(__name__)
    logger.info("Launching browser: %s (headed=%s)", browser_name, headed)

    browser: Optional[Browser] = None
    try:
        launch_kwargs: Dict[str, Any] = {
            "headless": not headed,
            "args": [
                "--start-maximized",
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        }
        browser_type = getattr(playwright_instance, browser_name)
        browser = await browser_type.launch(**launch_kwargs)
        yield browser
    except PWError as pw_err:
        logger.exception("Playwright error when launching browser: %s", pw_err)
        raise
    except Exception as exc:
        logger.exception("Unexpected error when launching browser: %s", exc)
        raise
    finally:
        if browser:
            logger.info("Closing browser...")
            await browser.close()
            logger.info("Browser closed.")


@pytest.fixture(scope="function")
async def browser_context(
    browser: Browser,
    base_url: str,
    pw_timeout: int,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Function-scoped BrowserContext.

    Each test gets a fresh context for isolation.
    """
    logger = logging.getLogger(__name__)
    context: Optional[BrowserContext] = None
    try:
        context = await browser.new_context(
            base_url=base_url,
            viewport=DEFAULT_VIEWPORT,
        )
        context.set_default_timeout(pw_timeout)
        logger.debug("Created new browser context with base_url=%s", base_url)
        yield context
    except PWError as pw_err:
        logger.exception("Playwright error in browser_context: %s", pw_err)
        raise
    except Exception as exc:
        logger.exception("Unexpected error in browser_context: %s", exc)
        raise
    finally:
        if context:
            logger.debug("Closing browser context...")
            await context.close()
            logger.debug("Browser context closed.")


@pytest.fixture(scope="function")
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """
    Function-scoped Page fixture.

    Provides a new page for each test.
    """
    logger = logging.getLogger(__name__)
    page: Optional[Page] = None
    try:
        page = await browser_context.new_page()
        logger.debug("New page created.")
        yield page
    except PWError as pw_err:
        logger.exception("Playwright error in page fixture: %s", pw_err)
        raise
    except Exception as exc:
        logger.exception("Unexpected error in page fixture: %s", exc)
        raise
    finally:
        if page:
            logger.debug("Closing page...")
            await page.close()
            logger.debug("Page closed.")


# =============================================================================
# AUTHENTICATION / SESSION REUSE
# =============================================================================

SESSION_STORAGE_FILE = Path(".auth") / "dev_session_storage.json"


async def _perform_login(
    page: Page,
    username: str,
    password: str,
    base_url: str,
    logger: logging.Logger,
) -> None:
    """
    Perform login steps on the given page.

    Adjust selectors according to actual login page structure.
    """
    logger.info("Performing login for user '%s'...", username)
    await page.goto(base_url, wait_until="domcontentloaded")

    # NOTE: Selectors below are placeholders and must be adjusted to real app
    try:
        # Example selectors - replace with actual ones
        await page.fill("input[name='username']", username)
        await page.fill("input[name='password']", password)
        await page.click("button[type='submit']")

        # Wait for a post-login element or URL change
        # Adjust this condition to your application's behavior
        await page.wait_for_load_state("networkidle")
        logger.info("Login flow completed (network idle).")
    except PWError as pw_err:
        logger.exception("Playwright error during login: %s", pw_err)
        raise
    except Exception as exc:
        logger.exception("Unexpected error during login: %s", exc)
        raise


async def _save_storage_state(context: BrowserContext, storage_file: Path, logger: logging.Logger) -> None:
    """Save storage state (cookies, localStorage, etc.) to a file for reuse."""
    storage_file.parent.mkdir(parents=True, exist_ok=True)
    state = await context.storage_state()
    storage_file.write_text(json.dumps(state, indent=2))
    logger.info("Saved storage state to %s", storage_file)


def _load_password_from_env(logger: logging.Logger) -> str:
    """Load password from environment variable, raising clear error if missing."""
    password = os.getenv(DEFAULT_PASSWORD_ENV_VAR)
    if not password:
        logger.error(
            "Environment variable %s is not set; cannot authenticate.",
            DEFAULT_PASSWORD_ENV_VAR,
        )
        raise RuntimeError(
            f"Target password not set. Please export {DEFAULT_PASSWORD_ENV_VAR} "
            "with the target system password."
        )
    return password


@pytest.fixture(scope="session")
async def authenticated_storage_state(
    playwright_instance: Playwright,
    browser_name: str,
    base_url: str,
) -> Path:
    """
    Session-scoped fixture that ensures a valid authenticated storage state file.

    Login is performed once per session; subsequent tests reuse the storage state.
    """
    logger = logging.getLogger(__name__)
    storage_file = SESSION_STORAGE_FILE

    # If storage state already exists, reuse it
    if storage_file.exists():
        logger.info("Using existing authenticated storage state: %s", storage_file)
        return storage_file

    logger.info("No existing storage state found. Performing initial login...")

    password = _load_password_from_env(logger)
    username = DEFAULT_USERNAME

    browser: Optional[Browser] = None
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None

    try:
        browser_type = getattr(playwright_instance, browser_name)
        browser = await browser_type.launch(headless=True)
        context = await browser.new_context(base_url=base_url, viewport=DEFAULT_VIEWPORT)
        page = await context.new_page()

        await _perform_login(page, username, password, base_url, logger)
        await _save_storage_state(context, storage_file, logger)
        logger.info("Authenticated storage state created.")
    except Exception:
        logger.exception("Failed to create authenticated storage state.")
        raise
    finally:
        if page:
            await page.close()
        if context:
            await context.close()
        if browser:
            await browser.close()

    return storage_file


@pytest.fixture(scope="function")
async def auth_context(
    browser: Browser,
    authenticated_storage_state: Path,
    base_url: str,
    pw_timeout: int,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Function-scoped authenticated BrowserContext.

    Uses session storage state to avoid repeated logins.
    """
    logger = logging.getLogger(__name__)
    context: Optional[BrowserContext] = None
    try:
        context = await browser.new_context(
            base_url=base_url,
            viewport=DEFAULT_VIEWPORT,
            storage_state=authenticated_storage_state.read_text(),
        )
        context.set_default_timeout(pw_timeout)
        logger.debug("Authenticated context created with storage state: %s", authenticated_storage_state)
        yield context
    except PWError as pw_err:
        logger.exception("Playwright error in auth_context: %s", pw_err)
        raise
    except Exception as exc:
        logger.exception("Unexpected error in auth_context: %s", exc)
        raise
    finally:
        if context:
            logger.debug("Closing authenticated context...")
            await context.close()
            logger.debug("Authenticated context closed.")


@pytest.fixture(scope="function")
async def auth_page(auth_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """
    Function-scoped authenticated Page.

    Tests using this fixture start from an authenticated state.
    """
    logger = logging.getLogger(__name__)
    page: Optional[Page] = None
    try:
        page = await auth_context.new_page()
        logger.debug("Authenticated page created.")
        yield page
    except PWError as pw_err:
        logger.exception("Playwright error in auth_page fixture: %s", pw_err)
        raise
    except Exception as exc:
        logger.exception("Unexpected error in auth_page fixture: %s", exc)
        raise
    finally:
        if page:
            logger.debug("Closing authenticated page...")
            await page.close()
            logger.debug("Authenticated page closed.")


# =============================================================================
# TEST DATA MANAGEMENT FIXTURE
# =============================================================================

@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """
    Base directory for test data files.

    Adjust as needed to your project structure.
    """
    data_dir = Path("test_data").resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir


@pytest.fixture(scope="function")
def test_data(test_data_dir: Path) -> Dict[str, Any]:
    """
    Test data management fixture.

    Returns a dict that can be used / modified by tests. If you prefer
    loading from JSON/YAML per test, you can extend this to read files
    based on node name or markers.
    """
    # Example default data structure; customize as needed.
    return {
        "env": DEFAULT_ENV,
        "sample_user": {
            "username": "test_user",
            "roles": ["admin"],
        },
        "paths": {
            "data_dir": str(test_data_dir),
        },
    }


# =============================================================================
# SCREENSHOT ON FAILURE
# =============================================================================

@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Hook to add test outcome information to the item for later use
    (e.g., in fixtures).
    """
    outcome = yield
    rep = outcome.get_result()

    # Attach result to test item for access in fixtures
    setattr(item, "rep_" + rep.when, rep)


@pytest.fixture(autouse=True)
async def screenshot_on_failure(
    request: pytest.FixtureRequest,
    screenshot_dir: Path,
) -> AsyncGenerator[None, None]:
    """
    Autouse fixture that captures a screenshot on test failure.

    It attempts to locate a Playwright Page from the test's fixtures
    (prefers 'auth_page', then 'page').
    """
    yield  # Run the test first

    logger = logging.getLogger(__name__)
    # Only care about call phase (actual test body)
    rep: pytest.TestReport = getattr(request.node, "rep_call", None)  # type: ignore[assignment]
    if not rep or rep.passed or rep.skipped:
        return

    # Try to get a Page instance from fixtures
    page: Optional[Page] = None
    for candidate in ("auth_page", "page"):
        if candidate in request.fixturenames:
            maybe_page = request.getfixturevalue(candidate)
            if isinstance(maybe_page, Page):
                page = maybe_page
                break

    if not page:
        logger.warning(
            "Test %s failed but no Playwright Page fixture ('page' or 'auth_page') found; "
            "skipping screenshot.",
            request.node.nodeid,
        )
        return

    # Build screenshot path
    test_name = request.node.nodeid.replace("::", "_").replace("/", "_")
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
    screenshot_path = screenshot_dir / f"{test_name}_{timestamp}.png"

    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
        logger.info("Saved failure screenshot for %s to %s", request.node.nodeid, screenshot_path)
    except PWError as pw_err:
        logger.exception(
            "Playwright error while taking screenshot for failed test %s: %s",
            request.node.nodeid,
            pw_err,
        )
    except Exception as exc:
        logger.exception(
            "Unexpected error while taking screenshot for failed test %s: %s",
            request.node.nodeid,
            exc,
        )