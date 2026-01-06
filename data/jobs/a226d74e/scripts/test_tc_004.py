import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_import_malformed_csv_displays_error_message(authenticated_page: Page):
    """
    Test Case: TC_004
    Title: Verify system handles invalid CSV format gracefully during import
    Category: negative
    Priority: High

    Description:
    Attempt to import malformed or invalid CSV data and verify system responds with appropriate error message without crashing.
    """

    # Define constants for selectors and URLs
    BASE_URL = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
    MAINTENANCE_MENU_SELECTOR = "text=Maintenance"  # Adjust if needed
    IMPORT_EXPORT_SUBMENU_SELECTOR = "text=Import/Export"  # Adjust if needed
    IMPORT_PROFILER_DEVICE_DATA_SELECTOR = "text=Import Profiler Device Data"  # Adjust if needed
    CSV_FILE_INPUT_SELECTOR = "input[type='file']"  # Assuming standard file input
    START_IMPORT_BUTTON_SELECTOR = "button:has-text('Start Import')"  # Adjust as per actual button text
    ERROR_MESSAGE_SELECTOR = "div.error-message"  # Placeholder, adjust to actual error message container

    # Path to the malformed CSV file (ensure this file exists in the test environment)
    malformed_csv_path = "tests/resources/malformed_profiler_data.csv"

    # Step 1: Log in as admin
    page = authenticated_page
    await page.goto(BASE_URL)

    # --- Assuming login steps are handled in conftest.py fixture ---
    # If not, implement login here:
    # await page.fill('input[name="username"]', 'admin_username')
    # await page.fill('input[name="password"]', 'admin_password')
    # await page.click('button[type="submit"]')
    # await page.wait_for_load_state('networkidle')

    # Step 2: Navigate to Maintenance > Import/Export
    try:
        # Hover or click to expand Maintenance menu if needed
        await page.click(f"text=Maintenance")
        # Click on Import/Export
        await page.click(f"text=Import/Export")
        # Wait for the page to load or the section to be visible
        await expect(page.locator(IMPORT_PROFILER_DEVICE_DATA_SELECTOR)).to_be_visible()
    except Exception as e:
        pytest.fail(f"Navigation to Import/Export failed: {e}")

    # Step 3: Choose "Import Profiler Device Data" in CSV format
    try:
        await page.click(IMPORT_PROFILER_DEVICE_DATA_SELECTOR)
        # Wait for import modal or section to appear
        # (Adjust if there's a modal or specific section to wait for)
        await expect(page.locator(CSV_FILE_INPUT_SELECTOR)).to_be_visible()
    except Exception as e:
        pytest.fail(f"Selecting 'Import Profiler Device Data' failed: {e}")

    # Step 4: Upload malformed CSV file
    try:
        file_input = page.locator(CSV_FILE_INPUT_SELECTOR)
        # Set the file input to our malformed CSV
        await file_input.set_input_files(malformed_csv_path)
    except Exception as e:
        pytest.fail(f"Uploading malformed CSV failed: {e}")

    # Step 5: Start import process
    try:
        start_button = page.locator(START_IMPORT_BUTTON_SELECTOR)
        await start_button.click()
    except Exception as e:
        pytest.fail(f"Clicking 'Start Import' button failed: {e}")

    # --- Verify the system's response ---
    # Wait for potential error message to appear
    try:
        error_message_locator = page.locator(ERROR_MESSAGE_SELECTOR)
        await expect(error_message_locator).to_be_visible(timeout=5000)
        error_text = await error_message_locator.text_content()
    except Exception:
        # If no error message appears, this is a failure
        pytest.fail("No error message displayed after importing malformed CSV.")

    # Assertions:
    # 1. Check that the error message indicates data format issues
    assert error_text is not None, "Error message is empty."
    assert "format" in error_text.lower() or "invalid" in error_text.lower() or "error" in error_text.lower(), \
        f"Unexpected error message: {error_text}"

    # 2. Verify no changes made to database
    # This step may require backend verification or UI confirmation
    # For now, we can assert that the system is still on the same page or check no success message
    # (Adjust as per system behavior)
    # Example:
    current_url = page.url
    assert BASE_URL in current_url, "Unexpected navigation occurred after import."

    # 3. Confirm system logs contain the error (if logs are accessible via UI)
    # This depends on system capabilities; if logs are accessible:
    # logs = await get_system_logs(page)
    # assert "CSV format error" in logs

    # Note: If logs are not accessible via UI, backend logs should be checked separately

    # Final cleanup or additional assertions can be added here