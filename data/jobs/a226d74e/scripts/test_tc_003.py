import pytest
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_import_csv_profiler_database_with_valid_data(
    authenticated_page: Page,
    tmp_path: "pathlib.Path",
):
    """
    TC_003: Verify import of CSV formatted profiler database with valid data adding new endpoints.

    Steps:
    - Log in as admin (assumed done via fixture)
    - Navigate to Maintenance > Import/Export
    - Select "Import Profiler Device Data" in CSV format
    - Upload valid CSV file with new endpoint data
    - Initiate import and wait for completion
    - Verify success message and new endpoints are visible in the system

    Prerequisites:
    - Valid CSV file with endpoint data exists at a known location
    - Admin access assumed via fixture
    """

    # Path to the CSV file with new endpoint data
    csv_file_path = tmp_path / "new_endpoints.csv"
    # Create a sample CSV file with endpoint data
    csv_content = (
        "endpoint_id,endpoint_name,ip_address\n"
        "endpoint_001,New Endpoint 1,192.168.1.10\n"
        "endpoint_002,New Endpoint 2,192.168.1.11\n"
    )
    csv_file_path.write_text(csv_content)

    page = authenticated_page

    try:
        # Step 1: Log in as admin (assumed already done via fixture)

        # Step 2: Navigate to Maintenance > Import/Export
        # Adjust selectors as per actual UI
        await page.goto("https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi")
        # Example navigation - replace with actual selectors
        await page.click("text=Maintenance")
        await page.click("text=Import/Export")
        # Wait for page to load
        await page.wait_for_load_state("networkidle")

        # Step 3: Select "Import Profiler Device Data" in CSV format
        # Assuming a dropdown or button exists
        await page.click("text=Import Profiler Device Data")
        # Wait for import modal or section to appear
        await page.wait_for_selector("input[type='file']")

        # Step 4: Upload valid CSV file
        csv_input = await page.query_selector("input[type='file']")
        if not csv_input:
            pytest.fail("CSV file upload input not found.")
        await csv_input.set_input_files(str(csv_file_path))

        # Step 5: Initiate import and wait for completion
        # Assume there's a button to start import
        await page.click("text=Start Import")
        # Wait for success message or completion indicator
        success_message_selector = "text=Import completed successfully"
        await page.wait_for_selector(success_message_selector, timeout=60000)  # wait up to 60s

        # Assert the success message is visible
        success_message = await page.query_selector(success_message_selector)
        assert success_message is not None, "Success message not displayed after import."

        # Step 6: Verify that new endpoints are visible in the endpoint list
        # Navigate to the endpoint list page or refresh current page
        # For example, refresh the page
        await page.reload()
        await page.wait_for_load_state("networkidle")

        # Search for the new endpoints in the list
        for endpoint_name in ["New Endpoint 1", "New Endpoint 2"]:
            locator = page.locator(f"text={endpoint_name}")
            # Expect each new endpoint to be visible
            expect(locator).to_be_visible()

    except Exception as e:
        pytest.fail(f"Test failed due to unexpected error: {e}")