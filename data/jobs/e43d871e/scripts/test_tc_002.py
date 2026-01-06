import pytest
from playwright.async_api import Page, expect, Error

@pytest.mark.asyncio
async def test_static_ip_device_detection(authenticated_page: Page):
    """
    Test Case: TC_002
    Title: Confirm that endpoints with static IP addresses are detected via ARP or SNMP data fetch.
    Category: positive
    Priority: High

    Description:
    Verify that a device with a static IP (e.g., 192.168.100.50) connected to the network
    appears in the Profiler with correct MAC, IP, vendor info, and status as "Active".
    """

    # Define the target URL
    target_url = "https://npre-miiqa2mp-eastus2.openai.azure.com/"

    # Define static device details (based on test prerequisites)
    static_device_ip = "192.168.100.50"
    expected_mac_address = "00:11:22:33:44:55"
    expected_vendor = "SampleVendor"  # Replace with actual expected vendor info if known
    expected_status = "Active"

    # Step 1: Navigate to the system's main page
    try:
        await authenticated_page.goto(target_url, timeout=60000)
    except Error as e:
        pytest.fail(f"Navigation to {target_url} failed: {e}")

    # Step 2: Ensure SNMP polling is active
    # (Assuming there's a dashboard or status indicator; adjust selectors accordingly)
    try:
        snmp_status_selector = "text=SNMP Polling Status"  # Placeholder selector
        snmp_status_element = await authenticated_page.wait_for_selector(snmp_status_selector, timeout=15000)
        snmp_status_text = await snmp_status_element.inner_text()

        assert "Active" in snmp_status_text, "SNMP polling is not active."
    except Error:
        pytest.fail("SNMP polling status indicator not found or not active.")

    # Step 3: Connect the static IP device to the network
    # (Assumed already connected as per prerequisites; optionally, verify connection)
    # Placeholder for verification step if needed

    # Step 4: Wait for the polling cycle to fetch ARP/SNMP tables
    # Wait for a reasonable period (e.g., 2 minutes) to allow data fetch
    polling_wait_seconds = 120
    print(f"Waiting {polling_wait_seconds} seconds for polling cycle to complete...")
    await authenticated_page.wait_for_timeout(polling_wait_seconds * 1000)

    # Step 5: Observe Profiler logs or device list for detection
    # Navigate or refresh the device list view
    try:
        device_list_button_selector = "button:has-text('Device List')"  # Adjust as needed
        await authenticated_page.click(device_list_button_selector)
        await authenticated_page.wait_for_load_state("networkidle")
    except Error:
        pytest.fail("Failed to navigate to Device List view.")

    # Search for the device with the expected IP address
    try:
        device_row_selector = f"tr:has(td:text('{static_device_ip}'))"
        device_row = await authenticated_page.wait_for_selector(device_row_selector, timeout=30000)
    except Error:
        pytest.fail(f"Device with IP {static_device_ip} not found in device list after polling.")

    # Step 6: Verify device details
    try:
        # Extract MAC address from the device row
        mac_cell_selector = f"{device_row_selector} td:has-text('{expected_mac_address}')"
        mac_cell = await authenticated_page.query_selector(mac_cell_selector)
        assert mac_cell is not None, f"MAC address {expected_mac_address} not found for device with IP {static_device_ip}."

        # Verify vendor info
        vendor_cell_selector = f"{device_row_selector} td:has-text('{expected_vendor}')"
        vendor_cell = await authenticated_page.query_selector(vendor_cell_selector)
        assert vendor_cell is not None, f"Vendor info '{expected_vendor}' not found for device with IP {static_device_ip}."

        # Verify device status
        status_cell_selector = f"{device_row_selector} td:has-text('{expected_status}')"
        status_cell = await authenticated_page.query_selector(status_cell_selector)
        assert status_cell is not None, f"Device status '{expected_status}' not found for device with IP {static_device_ip}."

    except AssertionError as ae:
        pytest.fail(str(ae))
    except Error:
        pytest.fail("Failed to verify device details in device list.")

    # Postconditions: (Optional) Verify device profiling details if accessible
    # For example, open device details panel and check info
    # (Implement if such UI exists)

    print("Device with static IP successfully detected and verified.")