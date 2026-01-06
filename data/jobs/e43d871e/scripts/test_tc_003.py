import pytest
from playwright.async_api import Page, expect, Error

@pytest.mark.asyncio
async def test_dhcp_relay_profiling(
    authenticated_page: Page
):
    """
    Test Case: TC_003
    Title: Validate that DHCP requests relayed using DHCP relay are captured and used for device profiling.
    Category: positive
    Priority: Critical

    Description:
    Validates that when DHCP relay is configured and a device connects via DHCP,
    the PPS system detects and profiles the device based on DHCP fingerprinting.

    Prerequisites:
    - DHCP relay configured on network device
    - DHCP server active

    Test Steps:
    1. Configure DHCP relay on the network device to forward DHCP requests to PPS.
    2. Connect device and obtain DHCP IP.
    3. Verify PPS has received and parsed the DHCP request.
    4. Check device detection log in Profiler interface.

    Expected Results:
    - PPS detects the DHCP request forwarded via relay.
    - Device is profiled with MAC, vendor, and possibly OS info.

    Postconditions:
    Device appears in Profiler with correct profile info.
    """

    page = authenticated_page

    try:
        # Step 1: Ensure DHCP relay is configured
        # (Assumed to be pre-configured as per prerequisites)
        # Optional: Verify configuration if UI/API available
        # For demonstration, we assume it's set up correctly.

        # Step 2: Connect device and obtain DHCP IP
        # In real test, this step is performed outside automation.
        # For simulation, we may wait for the device to appear in the profiler.

        # Step 3: Verify PPS has received and parsed DHCP request
        # Navigate to the Profiler interface to check device detection logs
        await page.goto("https://npre-miiqa2mp-eastus2.openai.azure.com/profiler")
        await page.wait_for_load_state("networkidle")

        # Locate the device list or detection log table
        device_list_selector = "table#device-detection-log"  # Adjust selector as needed
        await page.wait_for_selector(device_list_selector, timeout=10000)

        # Search for the device by MAC address or other identifier
        # Assuming the device's MAC address is known for test
        test_mac_address = "00:11:22:33:44:55"  # Replace with actual test MAC if available

        # Find the row with the test MAC address
        device_row_selector = f"{device_list_selector} >> text={test_mac_address}"

        # Verify the device appears in the detection log
        device_row = await page.query_selector(device_row_selector)
        assert device_row, f"Device with MAC {test_mac_address} not found in detection log."

        # Step 4: Check device profile details (MAC, vendor, OS)
        # Click or expand the device profile if needed
        # For example, click on the device row to view details
        await device_row.click()

        # Wait for profile details panel to appear
        profile_panel_selector = "div#device-profile-details"
        await page.wait_for_selector(profile_panel_selector, timeout=5000)

        # Extract profile information
        mac_info = await page.locator(f"{profile_panel_selector} >> text=MAC Address").inner_text()
        vendor_info = await page.locator(f"{profile_panel_selector} >> text=Vendor").inner_text()
        os_info = await page.locator(f"{profile_panel_selector} >> text=OS").inner_text()

        # Assertions to verify profile info is present and plausible
        assert test_mac_address in mac_info, "MAC address in profile does not match expected."
        assert vendor_info, "Vendor info missing in device profile."
        # OS info may be optional; check if available
        # Log or print the OS info if needed
        print(f"Device OS info: {os_info}")

        # Additional assertions can include vendor name presence, OS fingerprint, etc.

    except Error as e:
        pytest.fail(f"Test encountered an error: {e}")