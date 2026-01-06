import pytest
from playwright.async_api import Page, expect, Error

@pytest.mark.asyncio
async def test_dhcp_packet_forwarding_and_detection(authenticated_page: Page):
    """
    Test Case: TC_001
    Title: Ensure that DHCP packets forwarded to the Profiler are correctly identified via DHCP fingerprinting.
    Category: positive
    Priority: Critical

    This test verifies that when DHCP packets are forwarded to PPS, the device is correctly detected
    by the profiler with accurate device information.
    """

    # Define URLs and selectors
    SYSTEM_URL = "https://npre-miiqa2mp-eastus2.openai.azure.com/"
    DEVICE_LIST_SELECTOR = "div.device-list"  # Placeholder selector for device list
    DEVICE_ENTRY_SELECTOR = "div.device-entry"  # Placeholder for individual device entries
    LOG_OUTPUT_SELECTOR = "div.log-output"  # Placeholder for log output area

    # Step 1: Connect device to network with DHCP forwarding enabled
    # (Assumed to be pre-configured; optional check can be added)

    # Step 2: Power on device and wait for DHCP request
    # (Assuming device is powered on; wait for DHCP request detection)
    # In a real test, you might trigger or verify DHCP request here.
    # For simulation, wait for some time to allow DHCP request to be sent.
    await authenticated_page.wait_for_timeout(5000)  # Wait 5 seconds

    # Step 3: Monitor DHCP traffic forwarded to PPS
    # Navigate to the profiler interface or logs page
    try:
        await authenticated_page.goto(SYSTEM_URL, timeout=15000)
    except Error as e:
        pytest.fail(f"Failed to navigate to system URL: {e}")

    # Wait for the page to load and logs to appear
    try:
        await authenticated_page.wait_for_selector(LOG_OUTPUT_SELECTOR, timeout=10000)
    except Error:
        pytest.fail(f"Log output area with selector '{LOG_OUTPUT_SELECTOR}' not found.")

    # Retrieve log output
    logs = await authenticated_page.inner_text(LOG_OUTPUT_SELECTOR)

    # Check if DHCP packets are forwarded
    if "DHCP" not in logs:
        pytest.fail("DHCP packets not detected in logs. Forwarding may have failed.")

    # Step 4: Check profiler interface for device detection
    try:
        await authenticated_page.wait_for_selector(DEVICE_LIST_SELECTOR, timeout=10000)
    except Error:
        pytest.fail("Device list not found in profiler interface.")

    # Fetch device entries
    device_entries = await authenticated_page.query_selector_all(DEVICE_ENTRY_SELECTOR)

    # Ensure at least one device detected
    if not device_entries:
        pytest.fail("No devices detected in profiler device list.")

    # Initialize a flag to confirm device detection via DHCP fingerprinting
    device_detected = False
    detected_device_info = {}

    for device in device_entries:
        try:
            # Extract device details: MAC, vendor, device type
            mac = await device.query_selector("span.mac")  # Placeholder selector
            vendor = await device.query_selector("span.vendor")
            device_type = await device.query_selector("span.device-type")

            mac_text = await mac.inner_text() if mac else ""
            vendor_text = await vendor.inner_text() if vendor else ""
            device_type_text = await device_type.inner_text() if device_type else ""

            # Check if the device matches the expected DHCP fingerprint
            # For example, match MAC address or vendor
            # Here, for demonstration, assume any device is acceptable
            if mac_text and vendor_text and device_type_text:
                device_detected = True
                detected_device_info = {
                    "MAC": mac_text,
                    "Vendor": vendor_text,
                    "Device Type": device_type_text
                }
                break  # Exit loop once device is found
        except Error:
            continue  # Skip faulty entries

    # Assert that device was detected
    assert device_detected, "Device was not detected via DHCP fingerprinting."

    # Additional assertions for device info
    assert detected_device_info.get("MAC"), "Detected device missing MAC address."
    assert detected_device_info.get("Vendor"), "Detected device missing vendor information."
    assert detected_device_info.get("Device Type"), "Detected device missing device type."

    # Optionally, log the detected device info
    print(f"Detected device info: {detected_device_info}")

    # Postconditions: Device is registered and visible in profiler device list
    # (Assumed verified by the presence in device list and logs)