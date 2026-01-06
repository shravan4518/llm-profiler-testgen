import pytest
from playwright.async_api import Page, expect, Error

@pytest.mark.asyncio
async def test_device_profile_with_user_agent(authenticated_page: Page):
    """
    Test Case: TC_010
    Title: Confirm that devices not relying on DHCP are profiled via user agent analysis.
    Category: positive
    Priority: Medium

    Description:
    Connect a device with identifiable user agent data, generate network activity,
    and verify that the device profile is correctly identified as an iOS device
    based on user agent analysis, even without DHCP data.
    """
    # Define the target URL
    target_url = "https://npre-miiqa2mp-eastus2.openai.azure.com/"

    # Step 1: Connect device and generate network activity with identifiable user agent
    # For simulation purposes, we'll navigate to the URL with a specific user agent
    # (In real scenarios, this could be done by setting the user agent or simulating device traffic)
    user_agent_string = "Mozilla/5.0 (iPhone; CPU iPhone OS 15_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/15.0 Mobile/15E148 Safari/604.1"

    try:
        # Launch a new context with the specific user agent
        context = authenticated_page.context
        # Create a new page with the custom user agent
        device_page = await context.new_page(user_agent=user_agent_string)

        # Navigate to the target URL to generate network traffic
        await device_page.goto(target_url, wait_until="networkidle")
        # Additional network activity can be simulated here if necessary
    except Error as e:
        pytest.fail(f"Failed to generate network activity with user agent: {e}")

    # Step 2: Profiler captures HTTP traffic and extracts user agent info
    # For the purpose of this test, assume there's a mechanism or API to retrieve the latest device profile
    # For example, accessing a specific page or API endpoint that shows device profile info
    # Here, we'll assume there's a page or element that displays the device profile data
    profile_url = "https://npre-miiqa2mp-eastus2.openai.azure.com/device-profile"  # hypothetical endpoint

    try:
        profile_page = await authenticated_page.context.new_page()
        await profile_page.goto(profile_url, wait_until="networkidle")

        # Extract profile data - assuming the profile info is within a specific element
        # For example, a JSON block or a specific DOM element
        profile_data_element = await profile_page.query_selector("#device-profile-data")
        if not profile_data_element:
            pytest.fail("Device profile data element not found on the profile page.")

        profile_json_text = await profile_data_element.inner_text()
        import json
        profile_data = json.loads(profile_json_text)
    except Error as e:
        pytest.fail(f"Error retrieving device profile data: {e}")

    # Step 3: Verify profile for recognition of device as an iOS device
    try:
        # Check that the profile indicates an iOS device
        device_type = profile_data.get("device_type")
        user_agent_info = profile_data.get("user_agent")
        dhcp_data_present = profile_data.get("dhcp_data", False)

        # Assertions:
        assert device_type == "iOS", f"Expected device_type 'iOS', but got '{device_type}'"
        assert user_agent_info and "iPhone" in user_agent_info, \
            "User agent info does not indicate an iPhone device."
        # DHCP data may be absent; ensure profile still recognizes device
        # For this test, we focus on user agent info filling profile gaps
        # So we do not assert DHCP presence, but note its absence
        # Example:
        if dhcp_data_present:
            print("DHCP data is present, which is acceptable.")
        else:
            print("DHCP data is absent, profile recognition relies on user agent info.")
    except AssertionError as ae:
        pytest.fail(f"Device profile verification failed: {ae}")
    finally:
        # Cleanup: close the profile page
        await profile_page.close()
        await device_page.close()