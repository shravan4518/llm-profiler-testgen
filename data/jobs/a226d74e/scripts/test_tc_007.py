import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_access_control_import_export(authenticated_page: Page):
    """
    Test Case: TC_007
    Title: Verify access control: only authorized users can perform import/export operations
    Category: security
    Priority: Critical

    Description:
    Ensure that only users with proper permissions can execute profiler database import or export functions.
    """
    # Constants for URLs and credentials
    BASE_URL = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
    # Replace these with actual test credentials
    NON_ADMIN_USERNAME = "read_only_user"
    NON_ADMIN_PASSWORD = "password123"
    ADMIN_USERNAME = "admin_user"
    ADMIN_PASSWORD = "adminpass456"

    # Selectors for navigation and actions
    # Note: Replace these with actual selectors from the application
    MAINTENANCE_MENU_SELECTOR = "text=Maintenance"
    IMPORT_EXPORT_OPTION_SELECTOR = "text=Import/Export"
    IMPORT_BUTTON_SELECTOR = "button#import"
    EXPORT_BUTTON_SELECTOR = "button#export"
    AUTH_ERROR_MESSAGE_SELECTOR = "text=You do not have permission to perform this action"
    # Assuming login form selectors
    USERNAME_INPUT_SELECTOR = "input[name='username']"
    PASSWORD_INPUT_SELECTOR = "input[name='password']"
    LOGIN_BUTTON_SELECTOR = "button#login"

    async def login(page: Page, username: str, password: str):
        """Helper function to perform login."""
        await page.goto(BASE_URL)
        await page.fill(USERNAME_INPUT_SELECTOR, username)
        await page.fill(PASSWORD_INPUT_SELECTOR, password)
        await page.click(LOGIN_BUTTON_SELECTOR)
        # Wait for navigation or dashboard element to confirm login
        # Replace with an actual element that appears post-login
        await page.wait_for_load_state("networkidle")
        # Alternatively, wait for a specific element
        # await page.wait_for_selector("selector_for_dashboard_or_homepage")

    async def navigate_to_import_export(page: Page):
        """Helper function to navigate to Maintenance > Import/Export."""
        # Expand Maintenance menu if necessary
        await page.click(MAINTENANCE_MENU_SELECTOR)
        # Wait for the menu to expand
        await page.wait_for_selector(IMPORT_EXPORT_OPTION_SELECTOR)
        await page.click(IMPORT_EXPORT_OPTION_SELECTOR)
        # Wait for Import/Export page to load
        await page.wait_for_selector(IMPORT_BUTTON_SELECTOR)

    async def attempt_import_export(page: Page):
        """Helper function to attempt import and export operations."""
        # Try to click import
        await page.click(IMPORT_BUTTON_SELECTOR)
        # Check for permission error
        try:
            # Wait for either success or error message
            await page.wait_for_selector(AUTH_ERROR_MESSAGE_SELECTOR, timeout=3000)
            error_message = await page.inner_text(AUTH_ERROR_MESSAGE_SELECTOR)
            return error_message
        except:
            # If no error message, assume success
            return None

        # Similarly for export
        await page.click(EXPORT_BUTTON_SELECTOR)
        try:
            await page.wait_for_selector(AUTH_ERROR_MESSAGE_SELECTOR, timeout=3000)
            error_message = await page.inner_text(AUTH_ERROR_MESSAGE_SELECTOR)
            return error_message
        except:
            return None

    # Step 1: Log in as non-admin user
    page = authenticated_page
    try:
        await login(page, NON_ADMIN_USERNAME, NON_ADMIN_PASSWORD)
        # Verify login success - e.g., by checking URL or dashboard element
        # For now, assume login successful if no error
    except Exception as e:
        pytest.fail(f"Login as non-admin user failed: {e}")

    # Step 2: Navigate to Import/Export
    try:
        await navigate_to_import_export(page)
    except Exception as e:
        pytest.fail(f"Navigation to Import/Export failed for non-admin user: {e}")

    # Step 3: Attempt import/export operations
    try:
        import_error = await attempt_import_export(page)
        # Assert that access is denied
        assert import_error is not None and "permission" in import_error.lower(), \
            "Non-admin user was able to perform import/export operations, which should be blocked."
    except Exception as e:
        pytest.fail(f"Import/Export operation attempt failed: {e}")

    # Log out non-admin user
    # Implement logout if necessary
    # await page.click("selector_for_logout")
    # await page.wait_for_load_state("networkidle")

    # Step 4: Log in as admin user
    try:
        await login(page, ADMIN_USERNAME, ADMIN_PASSWORD)
        # Verify login success
    except Exception as e:
        pytest.fail(f"Login as admin user failed: {e}")

    # Step 5: Repeat navigation and operations as admin
    try:
        await navigate_to_import_export(page)
    except Exception as e:
        pytest.fail(f"Navigation to Import/Export failed for admin user: {e}")

    # Attempt import/export operations
    try:
        import_error = await attempt_import_export(page)
        # Assert that operations succeed (no error message)
        assert import_error is None or "permission" not in import_error.lower(), \
            "Admin user was unable to perform import/export operations."
    except Exception as e:
        pytest.fail(f"Import/Export operation attempt as admin failed: {e}")