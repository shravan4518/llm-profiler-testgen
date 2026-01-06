import pytest
from playwright.async_api import Page, expect, Error

@pytest.mark.asyncio
async def test_static_ip_device_not_detected_via_dhcp_fingerprinting(authenticated_page: Page):
    """
    TC_004 - Ensure static IP devices without DHCP requests are not wrongly detected via DHCP fingerprinting.

    Prerequisites:
    - Static IP device connected
    - DHCP relay off
    - No DHCP request sent

    Steps:
    1. Connect static IP device without initiating DHCP request.
    2. Turn on Profiler and observe device list.
    3. Confirm no DHCP fingerprinting detection occurs for this device.

    Expected Results:
    - Device with static IP does not appear in DHCP fingerprinting detection logs.
    - Device profile is only created if detected via ARP/SNMP.
    """

    page = authenticated_page  # Use the fixture for an authenticated page

    try:
        # Step 1: Navigate to the system dashboard or relevant page
        await page.goto("https://npre-miiqa2mp-eastus2.openai.azure.com/")

        # Optional: Wait for the page to load necessary elements
        await page.wait_for_load_state("networkidle")

        # Step 2: Turn on Profiler
        # Assuming there's a toggle or button to enable profiler
        # Replace selectors with actual ones from your application
        profiler_toggle_selector = "button#profiler-toggle"  # example selector
        await page.click(profiler_toggle_selector)

        # Wait for profiler to be active
        # For example, wait for a status indicator or specific element
        profiler_status_selector = "div#profiler-status"  # example selector
        await expect(page.locator(profiler_status_selector)).to_have_text("Active", timeout=5000)

        # Step 3: Observe device list
        device_list_selector = "div#device-list"  # replace with actual selector
        device_list = page.locator(device_list_selector)

        # Wait for device list to load
        await expect(device_list).to_be_visible()

        # Search for the static IP device in the device list
        # Assuming devices are listed with identifiable info, e.g., IP address or hostname
        static_ip_address = "192.168.1.100"  # Replace with actual static IP
        device_entry_selector = f"div.device-entry:has-text('{static_ip_address}')"
        device_entry = page.locator(device_entry_selector)

        # Check if device is present
        device_present = await device_entry.count() > 0

        # Assertion: Device should NOT appear in DHCP fingerprinting detection logs
        assert not device_present, (
            f"Static IP device {static_ip_address} was detected in device list, which is unexpected."
        )

        # Additional verification:
        # Confirm that no detection logs mention DHCP fingerprinting for this device
        detection_logs_selector = "div#detection-logs"  # replace with actual selector
        detection_logs = page.locator(detection_logs_selector)

        # Wait for logs to load
        await expect(detection_logs).to_be_visible()

        logs_text = await detection_logs.inner_text()

        # Assert that logs do not contain DHCP fingerprinting detection for the device
        assert static_ip_address not in logs_text, (
            f"DHCP fingerprinting detection found for static IP {static_ip_address}, which should not occur."
        )

    except Error as e:
        pytest.fail(f"Test encountered an error: {e}")