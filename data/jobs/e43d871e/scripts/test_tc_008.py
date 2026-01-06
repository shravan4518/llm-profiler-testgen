import pytest
import asyncio
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_profiler_extracts_os_or_device_info_from_cdp_llpd(authenticated_page: Page):
    """
    Test Case: TC_008
    Title: Validate that the Profiler can extract OS or device info from CDP/LLDP data sent by switches or network devices.
    Category: positive
    Priority: Medium

    This test verifies that when a device is connected to a switch with CDP/LLDP enabled,
    the Profiler receives the announcements, processes the data, and updates the device profile
    with detailed OS/vendor info, beyond what DHCP alone can provide.
    """
    page = authenticated_page

    # Define the URL of the target system
    target_url = "https://npre-miiqa2mp-eastus2.openai.azure.com/"

    try:
        # Step 1: Connect to the target web application
        await page.goto(target_url)

        # Optional: Wait for the main page to load and verify page load
        await expect(page).to_have_title(re.compile(".*"))  # Adjust if specific title is known

        # Step 2: Wait for the network devices to be recognized and for announcements
        # Assuming there's a device list or logs section to monitor
        # Replace selectors with actual ones from the application

        # Example: wait for device list to load
        device_list_selector = "#device-list"  # Placeholder selector
        await page.wait_for_selector(device_list_selector, timeout=30000)

        # Optionally, wait for a specific device entry to appear
        # For example, device with hostname or MAC address
        device_entry_selector = "//div[contains(@class, 'device-entry') and contains(text(), 'DeviceName')]"
        device_entry = await page.wait_for_selector(device_entry_selector, timeout=60000)

        # Step 3: Check Profiler logs or device details for detection info
        # Assuming there's a detail view or logs section to verify info
        # Navigate or click to device details if necessary
        # Example: click on device to view details
        await device_entry.click()

        # Wait for device profile details to load
        device_profile_selector = "#device-profile-details"  # Placeholder
        await page.wait_for_selector(device_profile_selector, timeout=30000)

        # Extract OS and vendor info from the profile
        os_info_selector = "#device-profile-os"  # Placeholder
        vendor_info_selector = "#device-profile-vendor"  # Placeholder

        os_info_element = await page.query_selector(os_info_info_selector)
        vendor_info_element = await page.query_selector(vendor_info_selector)

        # Retrieve text content
        os_info = await os_info_element.inner_text() if os_info_element else ""
        vendor_info = await vendor_info_element.inner_text() if vendor_info_element else ""

        # Assert that the OS and vendor info are not empty
        assert os_info.strip() != "", "OS information should be detected and displayed."
        assert vendor_info.strip() != "", "Vendor information should be detected and displayed."

        # Additional assertion: OS detection is more granular than DHCP alone
        # For example, check if OS info contains specific expected substrings
        # (This depends on known data; adjust as needed)
        # For illustration:
        expected_os_substrings = ["Windows", "Linux", "macOS", "iOS", "Android"]
        assert any(substr in os_info for substr in expected_os_substrings), \
            "OS detection does not appear granular enough."

    except asyncio.TimeoutError:
        pytest.fail("Timed out waiting for device announcements or profile updates.")
    except Exception as e:
        pytest.fail(f"An unexpected error occurred: {e}")