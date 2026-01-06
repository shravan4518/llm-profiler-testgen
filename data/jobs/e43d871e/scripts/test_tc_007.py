import pytest
from playwright.async_api import Page, expect
import asyncio

@pytest.mark.asyncio
async def test_device_authentication_and_profiling(authenticated_page: Page):
    """
    Test TC_007: Confirm that devices authenticating through 802.1x are profiled correctly,
    including MAC and OS info, and linked to the session.
    
    Prerequisites:
    - Network with 802.1x enabled
    - Profiler configured to collect session info
    
    Steps:
    1. Connect device via 802.1x port.
    2. Complete authentication process.
    3. Check profiler device list for this endpoint.
    4. Review profile details for accuracy.
    
    Expectations:
    - Device info (MAC, vendor, OS) is correctly collected.
    - Profiling info is linked to the session.
    """
    page = authenticated_page

    # Define constants / selectors
    DEVICE_PORT_URL = "https://npre-miiqa2mp-eastus2.openai.azure.com/"
    PROFILE_LIST_SELECTOR = "#device-list"  # Placeholder selector for device list
    DEVICE_ENTRY_SELECTOR = ".device-entry"  # Placeholder for individual device entries
    SESSION_LINK_SELECTOR = ".session-link"  # Placeholder for session link within device details

    try:
        # Step 1: Connect device via 802.1x port
        # For testing purposes, we simulate this by navigating or triggering a test connection.
        # In real scenario, this might involve hardware or network setup.
        # Here, we assume the device is already connected, or simulate connection if possible.
        # For example, navigate to a page that shows connection status.
        await page.goto(DEVICE_PORT_URL)

        # Optional: Wait for network connection status to confirm device connection
        # For demonstration, wait for a specific element indicating connection
        await page.wait_for_selector("#connection-status.connected", timeout=10000)
        print("Device connected via 802.1x port.")

        # Step 2: Complete the 802.1x authentication process
        # This might involve interacting with login prompts or APIs.
        # Here, assuming automatic or mock authentication.
        # Alternatively, simulate login if required.
        # For example:
        # await page.fill("#username", "test_user")
        # await page.fill("#password", "test_pass")
        # await page.click("#login-button")
        # await page.wait_for_selector("#authentication-success", timeout=10000)

        # For demonstration, assume authentication completes automatically.
        # Wait for some indicator that authentication succeeded
        await page.wait_for_selector("#auth-status.success", timeout=10000)
        print("802.1x authentication completed.")

        # Step 3: Check Profiler device list for this endpoint
        await page.goto(f"{DEVICE_PORT_URL}/profiler/devices")
        await page.wait_for_selector(PROFILE_LIST_SELECTOR, timeout=10000)

        # Search for the device in the profile list
        device_entries = await page.query_selector_all(DEVICE_ENTRY_SELECTOR)
        assert device_entries, "No devices found in profiler device list."

        # Find the specific device (by MAC, IP, or unique identifier)
        # For simplicity, assume MAC address is displayed and known
        # For example, suppose we search by MAC address
        target_mac_address = "00:11:22:33:44:55"  # Replace with actual expected MAC
        target_device = None
        for device in device_entries:
            mac_element = await device.query_selector(".mac-address")
            if mac_element:
                mac_text = await mac_element.inner_text()
                if mac_text.strip() == target_mac_address:
                    target_device = device
                    break

        assert target_device is not None, f"Device with MAC {target_mac_address} not found in profiler list."

        # Step 4: Review profile details for accuracy
        # Extract details: MAC, vendor, OS info
        mac_info = await target_device.query_selector(".mac-address")
        vendor_info = await target_device.query_selector(".vendor")
        os_info = await target_device.query_selector(".os")
        session_link = await target_device.query_selector(SESSION_LINK_SELECTOR)

        # Validate that details exist
        assert mac_info, "MAC address info missing."
        assert vendor_info, "Vendor info missing."
        assert os_info, "OS info missing."
        assert session_link, "Session link missing."

        mac_text = await mac_info.inner_text()
        vendor_text = await vendor_info.inner_text()
        os_text = await os_info.inner_text()

        # Assertions for expected data
        assert mac_text.strip() == target_mac_address, "MAC address does not match expected."
        assert vendor_text.strip(), "Vendor info is empty."
        assert os_text.strip(), "OS info is empty."

        # Optional: Verify that OS info looks correct (e.g., contains known OS names)
        # For example:
        known_os_names = ["Windows", "macOS", "Linux", "Android", "iOS"]
        if not any(os_name in os_text for os_name in known_os_names):
            print(f"Warning: OS info '{os_text}' does not match known OS names.")

        # Check that profiling info is linked to session
        # For example, click on session link and verify session details
        await session_link.click()
        await page.wait_for_selector("#session-details", timeout=10000)
        session_details = await page.inner_text("#session-details")
        assert session_details, "Session details are empty or not linked properly."

        print("Device profiling details verified successfully.")

    except Exception as e:
        # Handle and log errors gracefully
        pytest.fail(f"Test failed due to error: {e}")