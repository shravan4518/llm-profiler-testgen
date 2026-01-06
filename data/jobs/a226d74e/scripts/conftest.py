import pytest
import asyncio
import logging
from pathlib import Path
from playwright.async_api import async_playwright, Browser, Page, Error as PlaywrightError

# Configure logging
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
formatter = logging.Formatter(
    "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
handler.setFormatter(formatter)
logger.addHandler(handler)

# Constants for the target system
BASE_URL = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
USERNAME = "shravan"
PASSWORD = "[SECURED]"  # Replace with actual password or load from environment securely
SCREENSHOTS_DIR = Path("screenshots")
SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)

# Fixture for Playwright instance
@pytest.fixture(scope="session")
async def playwright_instance():
    """
    Initialize Playwright asynchronously for the session.
    """
    try:
        logger.info("Launching Playwright")
        async with async_playwright() as pw:
            yield pw
    except PlaywrightError as e:
        logger.exception("Error initializing Playwright: %s", e)
        raise

# Fixture for Browser instance
@pytest.fixture(scope="session")
async def browser(playwright_instance):
    """
    Launch a Chromium browser in headless mode.
    """
    try:
        logger.info("Launching Chromium browser")
        browser = await playwright_instance.chromium.launch(
            headless=True,
            args=["--start-maximized"]
        )
        yield browser
    except PlaywrightError as e:
        logger.exception("Error launching browser: %s", e)
        raise
    finally:
        await browser.close()
        logger.info("Browser closed")

# Fixture for authenticated Page
@pytest.fixture(scope="session")
async def page(browser):
    """
    Create a new page, perform login once, and reuse session.
    """
    context = await browser.new_context(
        viewport={"width": 1920, "height": 1080},
        base_url=BASE_URL,
        ignore_https_errors=True  # Skip SSL errors if any
    )
    page = await context.new_page()

    # Login procedure
    try:
        logger.info("Navigating to login page")
        await page.goto(BASE_URL, timeout=30000)
        # Replace the selectors below with actual login form selectors
        await page.fill('input[name="username"]', USERNAME)
        await page.fill('input[name="password"]', PASSWORD)
        await page.click('button[type="submit"]')  # Adjust selector as needed

        # Wait for navigation or specific element indicating login success
        await page.wait_for_load_state("networkidle", timeout=30000)
        logger.info("Login successful")
    except PlaywrightError as e:
        logger.exception("Error during login: %s", e)
        await page.screenshot(path=SCREENSHOTS_DIR / "login_error.png")
        await context.close()
        raise

    # Attach a finalizer to close context after tests
    yield page

    await context.close()
    logger.info("Browser context closed after tests")

# Fixture for test data management
@pytest.fixture(scope="session")
def test_data():
    """
    Provide test data, could be extended to load from files or databases.
    """
    # Example static data; replace or extend as needed
    data = {
        "expected_title": "Welcome - Dana",
        "test_user": USERNAME,
        "test_password": PASSWORD,
    }
    return data

# Fixture for capturing screenshots on failure
@pytest.hookimpl(tryfirst=True)
async def pytest_runtest_makereport(item, call):
    """
    Hook to take screenshot upon test failure.
    """
    if call.when == "call":
        outcome = call.excinfo
        if outcome is not None:
            # Access the page fixture if available
            page = item.funcargs.get("page", None)
            if page:
                test_name = item.name
                screenshot_path = SCREENSHOTS_DIR / f"{test_name}.png"
                try:
                    await page.screenshot(path=str(screenshot_path))
                    logger.info(f"Screenshot saved to {screenshot_path}")
                except PlaywrightError as e:
                    logger.exception("Failed to take screenshot: %s", e)

# Optional: Add a fixture for cleanup or additional setup if needed
@pytest.fixture(scope="session", autouse=True)
async def session_cleanup():
    """
    Placeholder for any session-wide cleanup if necessary.
    """
    yield
    # Cleanup code here if needed