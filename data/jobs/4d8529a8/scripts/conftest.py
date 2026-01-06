"""
conftest.py

Pytest configuration and fixtures for Playwright-based test automation.

Features:
- Async Playwright (chromium) browser and page fixtures
- Authenticated page fixture (login once, reuse session)
- Test data management fixture
- Screenshot on failure
- Centralized configuration and logging
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
# Global Configuration
# =============================================================================

BASE_URL = "https://npre-miiqa2mp-eastus2.openai.azure.com/"
DEFAULT_USERNAME = "shravan"
# Password is expected to be provided via environment variable for security
PASSWORD_ENV_VAR = "TEST_APP_PASSWORD"

BROWSER_NAME = "chromium"
HEADLESS = True
VIEWPORT = {"width": 1920, "height": 1080}
DEFAULT_TIMEOUT_MS = 30_000  # 30 seconds
ENVIRONMENT = "dev"

# Directory to store screenshots, logs, etc.
ARTIFACTS_DIR = Path("artifacts")
SCREENSHOTS_DIR = ARTIFACTS_DIR / "screenshots"
LOGS_DIR = ARTIFACTS_DIR / "logs"

# =============================================================================
# Logging Setup
# =============================================================================


def _ensure_directories() -> None:
    """Ensure that artifacts directories exist."""
    for directory in (ARTIFACTS_DIR, SCREENSHOTS_DIR, LOGS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def _configure_root_logger() -> None:
    """Configure root logger for the test run."""
    _ensure_directories()

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # Avoid adding handlers multiple times if conftest is reloaded
    if logger.handlers:
        return

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler
    log_file = LOGS_DIR / f"test_run_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler.setFormatter(file_formatter)
    logger.addHandler(file_handler)


_configure_root_logger()
logger = logging.getLogger(__name__)

# =============================================================================
# Pytest Hooks
# =============================================================================


def pytest_addoption(parser: pytest.Parser) -> None:
    """Add custom command line options."""
    group = parser.getgroup("playwright")
    group.addoption(
        "--base-url",
        action="store",
        default=BASE_URL,
        help="Base URL of the target system.",
    )
    group.addoption(
        "--env",
        action="store",
        default=ENVIRONMENT,
        help="Environment name (e.g., dev, qa, prod).",
    )
    group.addoption(
        "--headed",
        action="store_true",
        default=not HEADLESS,
        help="Run browser in headed mode.",
    )


def pytest_configure(config: pytest.Config) -> None:
    """Configure test run settings."""
    logger.info("Pytest configuration initialized.")
    logger.info("Environment: %s", config.getoption("--env"))
    logger.info("Base URL: %s", config.getoption("--base-url"))


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item: pytest.Item, call: pytest.CallInfo):
    """
    Hook to access test outcome and attach it to the item.
    Used later for screenshot-on-failure logic.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, "rep_" + rep.when, rep)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_teardown(item: pytest.Item, nextitem: Optional[pytest.Item]):
    """
    Hook to take screenshot on test failure.
    This runs after each test's teardown phase.
    """
    yield

    # Only care about test call phase
    rep_call = getattr(item, "rep_call", None)
    if rep_call is None or rep_call.passed or rep_call.skipped:
        return

    # Try to get page fixture if available
    page: Optional[Page] = None
    try:
        # You may use either "page" or "auth_page" in tests; support both
        if "auth_page" in item.fixturenames:
            page = item.funcargs.get("auth_page")
        elif "page" in item.fixturenames:
            page = item.funcargs.get("page")
    except Exception:
        logger.exception("Failed to access page fixture for screenshot.")
        return

    if not page:
        logger.warning("No page fixture found for %s; skipping screenshot.", item.name)
        return

    # Take screenshot
    try:
        SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
        sanitized_name = "".join(
            c if c.isalnum() or c in ("-", "_") else "_" for c in item.name
        )
        screenshot_path = SCREENSHOTS_DIR / f"{sanitized_name}_{timestamp}.png"

        logger.info("Taking screenshot for failed test: %s", screenshot_path)
        # Use asyncio.run if needed; but here page is already running in event loop.
        # We must schedule screenshot synchronously using asyncio.
        loop = asyncio.get_event_loop()
        loop.run_until_complete(page.screenshot(path=str(screenshot_path), full_page=True))
    except RuntimeError:
        # If we are already in an event loop (e.g. with pytest-asyncio), use create_task
        try:
            asyncio.get_event_loop().create_task(
                page.screenshot(path=str(screenshot_path), full_page=True)
            )
        except Exception:
            logger.exception("Failed to schedule screenshot for failed test.")
    except Exception:
        logger.exception("Failed to take screenshot for failed test.")


# =============================================================================
# Fixtures: Configuration & Test Data
# =============================================================================


@pytest.fixture(scope="session")
def base_url(pytestconfig: pytest.Config) -> str:
    """Base URL for the application."""
    url = pytestconfig.getoption("--base-url")
    logger.info("Using base URL: %s", url)
    return url.rstrip("/") + "/"


@pytest.fixture(scope="session")
def environment(pytestconfig: pytest.Config) -> str:
    """Current environment name (dev/qa/prod/etc.)."""
    env = pytestconfig.getoption("--env")
    logger.info("Using environment: %s", env)
    return env


@pytest.fixture(scope="session")
def credentials() -> Dict[str, str]:
    """
    Provide credentials for authentication.
    Password is expected from an environment variable for security.
    """
    username = DEFAULT_USERNAME
    password = os.getenv(PASSWORD_ENV_VAR)

    if not password:
        logger.error(
            "Environment variable %s is not set. Authentication will fail.",
            PASSWORD_ENV_VAR,
        )

    return {"username": username, "password": password or ""}


@pytest.fixture(scope="session")
def test_data() -> Dict[str, Any]:
    """
    Simple test data management fixture.

    In a real framework, this might:
    - Load from JSON/YAML files
    - Load from a database
    - Be parameterized by environment

    Here we return a dict that tests can extend or override as needed.
    """
    data: Dict[str, Any] = {
        "env": ENVIRONMENT,
        "sample_user": {
            "username": "test_user",
            "email": "test_user@example.com",
        },
        # Add additional shared test data here.
    }
    logger.info("Test data fixture initialized.")
    return data


# =============================================================================
# Fixtures: Playwright & Browser
# =============================================================================


@pytest.fixture(scope="session")
async def playwright_instance() -> AsyncGenerator[Playwright, None]:
    """Start and stop the Playwright engine."""
    logger.info("Starting Playwright...")
    try:
        async with async_playwright() as p:
            yield p
    except PlaywrightError:
        logger.exception("Error while running Playwright.")
        raise
    finally:
        logger.info("Playwright session finished.")


@pytest.fixture(scope="session")
async def browser(playwright_instance: Playwright, pytestconfig: pytest.Config) -> AsyncGenerator[Browser, None]:
    """Provide a shared Browser instance for the test session."""
    headed = pytestconfig.getoption("--headed")
    headless = not headed

    logger.info("Launching browser: %s (headless=%s)", BROWSER_NAME, headless)
    try:
        browser = await playwright_instance[BROWSER_NAME].launch(
            headless=headless,
            args=["--start-maximized"],
        )
    except PlaywrightError:
        logger.exception("Failed to launch browser.")
        raise

    try:
        yield browser
    finally:
        logger.info("Closing browser...")
        try:
            await browser.close()
        except PlaywrightError:
            logger.exception("Error while closing browser.")


@pytest.fixture(scope="function")
async def browser_context(browser: Browser, base_url: str) -> AsyncGenerator[BrowserContext, None]:
    """
    Provide a fresh BrowserContext per test.

    This ensures test isolation while still sharing the Browser instance.
    """
    logger.info("Creating new browser context for test.")
    try:
        context = await browser.new_context(
            base_url=base_url,
            viewport=VIEWPORT,
        )
        # Set default timeout for all operations in this context
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    except PlaywrightError:
        logger.exception("Failed to create browser context.")
        raise

    try:
        yield context
    finally:
        logger.info("Closing browser context.")
        try:
            await context.close()
        except PlaywrightError:
            logger.exception("Error while closing browser context.")


@pytest.fixture(scope="function")
async def page(browser_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """
    Provide a new Page for each test.
    This is the base page (not necessarily authenticated).
    """
    logger.info("Opening new page for test.")
    try:
        page = await browser_context.new_page()
    except PlaywrightError:
        logger.exception("Failed to create new page.")
        raise

    try:
        yield page
    finally:
        logger.info("Closing page.")
        try:
            await page.close()
        except PlaywrightError:
            logger.exception("Error while closing page.")


# =============================================================================
# Fixtures: Authentication & Session Reuse
# =============================================================================


@pytest.fixture(scope="session")
async def auth_storage_state_file(
    browser: Browser,
    base_url: str,
    credentials: Dict[str, str],
) -> AsyncGenerator[Path, None]:
    """
    Create a storage state file after logging in once.

    This file is reused across tests to create authenticated contexts.
    """
    storage_path = ARTIFACTS_DIR / "auth_storage_state.json"
    logger.info("Preparing authenticated storage state at: %s", storage_path)

    # If storage file already exists, assume it's valid and reuse
    if storage_path.exists():
        logger.info("Existing storage state found; reusing: %s", storage_path)
        yield storage_path
        return

    # Otherwise, create a temporary context to perform login
    logger.info("No existing storage state. Performing login to create one.")
    context: Optional[BrowserContext] = None
    page: Optional[Page] = None
    try:
        context = await browser.new_context(
            base_url=base_url,
            viewport=VIEWPORT,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
        page = await context.new_page()

        username = credentials.get("username", "")
        password = credentials.get("password", "")

        if not username or not password:
            logger.error(
                "Missing credentials. Username or password is empty. "
                "Set %s environment variable for password.",
                PASSWORD_ENV_VAR,
            )
            raise RuntimeError("Missing credentials for authentication.")

        # Navigate to login page
        logger.info("Navigating to base URL for login: %s", base_url)
        await page.goto(base_url, wait_until="networkidle")

        # NOTE:
        # The actual selectors and login flow must be adapted
        # to your application's login page.
        # Below is a generic example and WILL need to be customized.

        # Example generic login flow:
        # await page.fill("input[name='username']", username)
        # await page.fill("input[name='password']", password)
        # await page.click("button[type='submit']")
        # await page.wait_for_load_state("networkidle")
        #
        # Replace the above with the real login selectors and logic.

        logger.warning(
            "Login flow is not implemented. "
            "You must implement the login steps in auth_storage_state_file fixture."
        )

        # TODO: Implement actual login logic here.
        # For now, we just save whatever state we have.
        await context.storage_state(path=str(storage_path))
        logger.info("Storage state saved to: %s", storage_path)

        yield storage_path

    except Exception:
        logger.exception("Failed to create authenticated storage state.")
        raise
    finally:
        if page:
            try:
                await page.close()
            except PlaywrightError:
                logger.exception("Error while closing auth setup page.")
        if context:
            try:
                await context.close()
            except PlaywrightError:
                logger.exception("Error while closing auth setup context.")


@pytest.fixture(scope="function")
async def auth_context(
    browser: Browser,
    base_url: str,
    auth_storage_state_file: Path,
) -> AsyncGenerator[BrowserContext, None]:
    """
    Provide an authenticated BrowserContext for tests using saved storage state.
    """
    logger.info("Creating authenticated browser context using storage state.")
    try:
        context = await browser.new_context(
            base_url=base_url,
            storage_state=str(auth_storage_state_file),
            viewport=VIEWPORT,
        )
        context.set_default_timeout(DEFAULT_TIMEOUT_MS)
    except PlaywrightError:
        logger.exception("Failed to create authenticated browser context.")
        raise

    try:
        yield context
    finally:
        logger.info("Closing authenticated browser context.")
        try:
            await context.close()
        except PlaywrightError:
            logger.exception("Error while closing authenticated browser context.")


@pytest.fixture(scope="function")
async def auth_page(auth_context: BrowserContext) -> AsyncGenerator[Page, None]:
    """
    Provide an authenticated Page for tests.
    Uses the storage state from auth_context to be already logged in.
    """
    logger.info("Opening authenticated page for test.")
    try:
        page = await auth_context.new_page()
    except PlaywrightError:
        logger.exception("Failed to create authenticated page.")
        raise

    try:
        yield page
    finally:
        logger.info("Closing authenticated page.")
        try:
            await page.close()
        except PlaywrightError:
            logger.exception("Error while closing authenticated page.")