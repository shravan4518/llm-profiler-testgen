"""
conftest.py

Pytest configuration and fixtures for Playwright-based test automation.

Key features:
- Async Playwright (chromium) browser fixture
- Authenticated page fixture (login once per session, reuse context)
- Test data fixture (placeholder for real data management)
- Automatic screenshots on failure
- Centralized logging
- Configurable base URL and environment
"""

import asyncio
import logging
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional

import pytest
from playwright.async_api import async_playwright, Browser, BrowserContext, Page, Playwright, Error as PlaywrightError


# =============================================================================
# Global configuration
# =============================================================================

DEFAULT_BASE_URL = "https://npre-miiqa2mp-eastus2.openai.azure.com/"
DEFAULT_ENV = "dev"
DEFAULT_BROWSER = "chromium"
DEFAULT_HEADLESS = True
DEFAULT_VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_TIMEOUT_MS = 30_000  # 30 seconds

# Username is provided, password should be supplied via environment for security
DEFAULT_USERNAME = "shravan"
PASSWORD_ENV_VAR = "TEST_USER_PASSWORD"  # export TEST_USER_PASSWORD='secret'


# =============================================================================
# Logging setup
# =============================================================================

def _setup_logging() -> logging.Logger:
    """
    Configure root logger for the test run.

    Logs to both console and a file under ./logs.
    """
    logger = logging.getLogger("test_logger")
    if logger.handlers:
        # Already configured
        return logger

    logger.setLevel(logging.DEBUG)

    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"test_run_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.log"

    # Console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%H:%M:%S",
    )
    ch.setFormatter(ch_formatter)

    # File handler (more verbose)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(filename)s:%(lineno)d] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    fh.setFormatter(fh_formatter)

    logger.addHandler(ch)
    logger.addHandler(fh)

    logger.debug("Logging initialized")
    return logger


LOGGER = _setup_logging()


# =============================================================================
# Pytest hooks
# =============================================================================

def pytest_addoption(parser: pytest.Parser) -> None:
    """
    Add custom command line options for configuring tests.
    """
    group = parser.getgroup("playwright")
    group.addoption(
        "--base-url",
        action="store",
        default=DEFAULT_BASE_URL,
        help=f"Base URL for the application under test (default: {DEFAULT_BASE_URL})",
    )
    group.addoption(
        "--env",
        action="store",
        default=DEFAULT_ENV,
        help=f"Environment name (default: {DEFAULT_ENV})",
    )
    group.addoption(
        "--headless",
        action="store_true",
        default=DEFAULT_HEADLESS,
        help="Run browser in headless mode (default: True). "
             "Use --no-headless to override if added.",
    )
    group.addoption(
        "--no-headless",
        action="store_true",
        default=not DEFAULT_HEADLESS,
        help="Run browser in headed mode (overrides --headless).",
    )
    group.addoption(
        "--browser",
        action="store",
        default=DEFAULT_BROWSER,
        choices=["chromium", "firefox", "webkit"],
        help=f"Browser to use (default: {DEFAULT_BROWSER}).",
    )


def pytest_configure(config: pytest.Config) -> None:
    """
    Called after command line options are parsed.
    """
    LOGGER.info("Pytest configured with environment: %s", config.getoption("--env"))
    LOGGER.info("Base URL: %s", config.getoption("--base-url"))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Hook to get test outcome for screenshots on failure.
    """
    outcome = yield
    rep = outcome.get_result()

    # Attach the report to the item for later access in fixtures
    setattr(item, "rep_" + rep.when, rep)


# =============================================================================
# Event loop for async fixtures
# =============================================================================

@pytest.fixture(scope="session")
def event_loop() -> asyncio.AbstractEventLoop:
    """
    Override pytest-asyncio's event_loop fixture to use a session-scoped loop.

    This allows Playwright to reuse the same loop across the entire test session.
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    yield loop
    loop.close()


# =============================================================================
# Configuration fixtures
# =============================================================================

@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    """
    Base URL for the application under test.
    """
    url = pytestconfig.getoption("--base-url")
    if not url.endswith("/"):
        url += "/"
    LOGGER.debug("Using base URL: %s", url)
    return url


@pytest.fixture(scope="session")
def env(pytestconfig: pytest.Config) -> str:
    """
    Environment name (e.g., dev, qa, prod).
    """
    environment = pytestconfig.getoption("--env")
    LOGGER.debug("Using environment: %s", environment)
    return environment


@pytest.fixture(scope="session")
def browser_name(pytestconfig: pytest.Config) -> str:
    """
    Browser name to use (chromium, firefox, webkit).
    """
    browser = pytestconfig.getoption("--browser")
    LOGGER.debug("Using browser: %s", browser)
    return browser


@pytest.fixture(scope="session")
def headless(pytestconfig: pytest.Config) -> bool:
    """
    Whether to run the browser in headless mode.
    """
    # --no-headless overrides --headless
    if pytestconfig.getoption("--no-headless"):
        LOGGER.debug("Headless mode disabled via --no-headless")
        return False
    headless_flag = pytestconfig.getoption("--headless")
    LOGGER.debug("Headless mode: %s", headless_flag)
    return headless_flag


# =============================================================================
# Playwright and browser fixtures
# =============================================================================

@pytest.fixture(scope="session")
async def playwright_instance() -> AsyncGenerator[Playwright, None]:
    """
    Session-scoped Playwright instance.
    """
    LOGGER.info("Starting Playwright...")
    try:
        async with async_playwright() as p:
            yield p
    except Exception as exc:
        LOGGER.exception("Failed to start Playwright: %s", exc)
        raise


@pytest.fixture(scope="session")
async def browser(
    playwright_instance: Playwright,
    browser_name: str,
    headless: bool,
) -> AsyncGenerator[Browser, None]:
    """
    Session-scoped browser instance.
    """
    LOGGER.info("Launching browser: %s (headless=%s)", browser_name, headless)
    try:
        browser_type = getattr(playwright_instance, browser_name)
    except AttributeError as exc:
        LOGGER.exception("Unsupported browser type: %s", browser_name)
        raise RuntimeError(f"Unsupported browser type: {browser_name}") from exc

    try:
        browser = await browser_type.launch(
            headless=headless,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
            ],
        )
        yield browser
    except PlaywrightError as exc:
        LOGGER.exception("Failed to launch browser: %s", exc)
        raise
    finally:
        LOGGER.info("Closing browser...")
        try:
            await browser.close()
        except Exception as exc:
            LOGGER.warning("Error while closing browser: %s", exc)


@pytest.fixture(scope="session")
async def browser_context(
    browser: Browser,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Session-scoped browser context.

    This is where login state is stored so that it can be reused across tests.
    """
    LOGGER.info("Creating browser context...")
    context: Optional[BrowserContext] = None
    try:
        context = await browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            ignore_https_errors=True,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        LOGGER.debug("Browser context created with viewport=%s, timeout=%s ms",
                     DEFAULT_VIEWPORT, DEFAULT_TIMEOUT_MS)
        yield context
    except PlaywrightError as exc:
        LOGGER.exception("Failed to create browser context: %s", exc)
        raise
    finally:
        if context:
            LOGGER.info("Closing browser context...")
            try:
                await context.close()
            except Exception as exc:
                LOGGER.warning("Error while closing browser context: %s", exc)


@pytest.fixture(scope="function")
async def page(
    browser_context: BrowserContext,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[Page, None]:
    """
    Function-scoped page fixture.

    Creates a new page for each test and handles screenshot capture on failure.
    """
    LOGGER.debug("Creating new page for test: %s", request.node.name)
    page: Optional[Page] = None
    try:
        page = await browser_context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        yield page
    finally:
        # Check if the test failed and take screenshot
        rep_call = getattr(request.node, "rep_call", None)
        failed = bool(rep_call and rep_call.failed)

        if failed and page:
            screenshots_dir = Path("artifacts") / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{request.node.name}_{timestamp}.png"
            screenshot_path = screenshots_dir / filename

            LOGGER.info("Test failed, capturing screenshot: %s", screenshot_path)
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception as exc:
                LOGGER.warning("Failed to capture screenshot: %s", exc)

        if page:
            LOGGER.debug("Closing page for test: %s", request.node.name)
            try:
                await page.close()
            except Exception as exc:
                LOGGER.warning("Error while closing page: %s", exc)


# =============================================================================
# Authentication fixtures
# =============================================================================

async def _perform_login(
    page: Page,
    base_url: str,
    username: str,
    password: str,
) -> None:
    """
    Implement the login flow here.

    This is a placeholder implementation. You must update selectors and steps
    according to the actual application's login page.
    """
    LOGGER.info("Starting login for user '%s'", username)

    # Example login flow; adjust selectors and URLs as needed.
    login_url = base_url  # or f"{base_url}login" if login page is at /login
    try:
        await page.goto(login_url, wait_until="networkidle")
        LOGGER.debug("Navigated to login page: %s", login_url)

        # Replace '#username', '#password', '#login-button' with real selectors
        await page.fill("#username", username)
        await page.fill("#password", password)
        await page.click("#login-button")

        # Wait for some post-login element that indicates successful login
        # Replace '#dashboard' with a reliable selector
        await page.wait_for_selector("#dashboard", timeout=DEFAULT_TIMEOUT_MS)
        LOGGER.info("Login successful for user '%s'", username)
    except PlaywrightError as exc:
        LOGGER.exception("Login failed for user '%s': %s", username, exc)
        raise RuntimeError(f"Login failed for user '{username}'") from exc


@pytest.fixture(scope="session")
async def authenticated_context(
    browser: Browser,
    base_url: str,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Session-scoped authenticated browser context.

    Performs login once and reuses the logged-in state for all tests.
    """
    LOGGER.info("Creating authenticated browser context...")

    password = os.getenv(PASSWORD_ENV_VAR)
    if not password:
        LOGGER.error(
            "Environment variable %s is not set. Cannot perform authenticated tests.",
            PASSWORD_ENV_VAR,
        )
        raise RuntimeError(
            f"Environment variable {PASSWORD_ENV_VAR} must be set with the test user password."
        )

    context: Optional[BrowserContext] = None
    try:
        context = await browser.new_context(
            viewport=DEFAULT_VIEWPORT,
            ignore_https_errors=True,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)

        # Use a temporary page to perform login
        page = await context.new_page()
        try:
            await _perform_login(page, base_url, DEFAULT_USERNAME, password)
        finally:
            try:
                await page.close()
            except Exception as exc:
                LOGGER.warning("Error while closing login page: %s", exc)

        # At this point, the context should have authenticated state (cookies, storage)
        LOGGER.info("Authenticated context created successfully.")
        yield context
    finally:
        if context:
            LOGGER.info("Closing authenticated browser context...")
            try:
                await context.close()
            except Exception as exc:
                LOGGER.warning("Error while closing authenticated context: %s", exc)


@pytest.fixture(scope="function")
async def authenticated_page(
    authenticated_context: BrowserContext,
    request: pytest.FixtureRequest,
) -> AsyncGenerator[Page, None]:
    """
    Function-scoped authenticated page fixture.

    Opens a new page in the authenticated context for each test and
    captures screenshots on failure.
    """
    LOGGER.debug("Creating new authenticated page for test: %s", request.node.name)
    page: Optional[Page] = None
    try:
        page = await authenticated_context.new_page()
        page.set_default_timeout(DEFAULT_TIMEOUT_MS)
        yield page
    finally:
        # Screenshot on failure
        rep_call = getattr(request.node, "rep_call", None)
        failed = bool(rep_call and rep_call.failed)

        if failed and page:
            screenshots_dir = Path("artifacts") / "screenshots"
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            filename = f"{request.node.name}_authenticated_{timestamp}.png"
            screenshot_path = screenshots_dir / filename

            LOGGER.info("Test failed, capturing authenticated screenshot: %s", screenshot_path)
            try:
                await page.screenshot(path=str(screenshot_path), full_page=True)
            except Exception as exc:
                LOGGER.warning("Failed to capture authenticated screenshot: %s", exc)

        if page:
            LOGGER.debug("Closing authenticated page for test: %s", request.node.name)
            try:
                await page.close()
            except Exception as exc:
                LOGGER.warning("Error while closing authenticated page: %s", exc)


# =============================================================================
# Test data management fixtures
# =============================================================================

@pytest.fixture(scope="session")
def test_data_dir() -> Path:
    """
    Directory where test data files are stored.

    Customize this path according to your project structure.
    """
    data_dir = Path("test_data")
    data_dir.mkdir(parents=True, exist_ok=True)
    LOGGER.debug("Using test data directory: %s", data_dir)
    return data_dir


@pytest.fixture(scope="function")
def test_data(request: pytest.FixtureRequest, test_data_dir: Path) -> Dict[str, Any]:
    """
    Test data fixture.

    Provides a per-test dictionary that can be used to store data.
    Also serves as a hook to load data from files if needed.

    Extend this to load JSON/YAML/CSV per test, e.g.:
      - Use markers like @pytest.mark.datafile("file.json")
      - Read from test_data_dir / file.json
    """
    data: Dict[str, Any] = {}

    # Example: support marker @pytest.mark.datafile("sample.json")
    marker = request.node.get_closest_marker("datafile")
    if marker:
        filename = marker.args[0] if marker.args else None
        if filename:
            file_path = test_data_dir / filename
            LOGGER.info("Loading test data from: %s", file_path)
            if not file_path.exists():
                LOGGER.error("Test data file not found: %s", file_path)
                raise FileNotFoundError(f"Test data file not found: {file_path}")
            try:
                import json

                with file_path.open("r", encoding="utf-8") as f:
                    data_from_file = json.load(f)
                data.update(data_from_file)
            except Exception as exc:
                LOGGER.exception("Failed to load test data from %s: %s", file_path, exc)
                raise

    # Tests can modify this dict; changes are isolated per test
    return data