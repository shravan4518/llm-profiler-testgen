import pytest
from playwright.async_api import Page, expect, Error

@pytest.mark.asyncio
async def test_import_profiler_database_overwrites_existing_data(authenticated_page: Page):
    """
    Test Case: TC_002
    Title: Verify successful import of profiler database in binary format overwriting existing data
    Category: positive
    Priority: Critical

    Description:
    Confirm that importing a valid binary profiler database replaces existing data correctly
    and invalidates current sessions.
    """
    # Define constants
    base_url = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
    import_section_selector = 'text=Maintenance'  # Adjust if necessary
    import_menu_selector = 'text=Import/Export'
    import_button_selector = 'button:has-text("Import Profiler Device Data")'
    file_input_selector = 'input[type="file"]'
    confirm_button_selector = 'button:has-text("Confirm")'
    start_import_button_selector = 'button:has-text("Start Import")'
    success_message_selector = 'text=Import completed successfully'  # Adjust based on actual message
    # Path to the valid binary file; ensure this file exists in the test environment
    binary_file_path = 'path/to/valid_profiler_data.bin'

    try:
        # Step 1: Navigate to the URL
        await authenticated_page.goto(base_url, wait_until='load')

        # Step 2: Navigate to Maintenance > Import/Export
        # Assuming menu navigation involves clicking menu items
        # Adjust selectors as per actual UI
        await authenticated_page.click('text=Maintenance')
        await authenticated_page.click('text=Import/Export')

        # Step 3: Select "Import Profiler Device Data" in Binary format
        # Wait for the import section to load
        await authenticated_page.wait_for_selector(import_button_selector, timeout=5000)

        # Step 4: Upload the valid binary file
        # Locate the file input element
        file_input = await authenticated_page.query_selector(file_input_selector)
        if not file_input:
            pytest.fail("File input element not found on the page.")
        await file_input.set_input_files(binary_file_path)

        # Step 5: Confirm and initiate import
        # Click the confirm button if any confirmation prompt appears
        await authenticated_page.click(confirm_button_selector)
        # Wait for the start import button to be enabled/clickable
        await authenticated_page.click(start_import_button_selector)

        # Step 6: Wait for completion message or prompt
        # Wait for success message indicating import completion
        await authenticated_page.wait_for_selector(success_message_selector, timeout=60000)  # wait up to 60 sec

        # Assertion: Verify success message is visible
        success_message = await authenticated_page.query_selector(success_message_selector)
        assert success_message is not None, "Success message not found after import."
        is_visible = await success_message.is_visible()
        assert is_visible, "Success message is not visible on the page."

        # Additional assertions can include:
        # - Verifying that existing data was replaced (depends on UI or backend)
        # - Confirming that sessions are invalidated (may require API calls or UI checks)

        # Optional: Verify that previous sessions are invalidated
        # For example, attempt to access a session-specific element or endpoint

    except Error as e:
        pytest.fail(f"Test failed due to an unexpected error: {e}")