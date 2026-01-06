import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_dhcpv4_fingerprinting_via_dhcp_helper_internal_port(
    authenticated_page: Page,
    browser,
):
    """
    TC_001: Verify DHCPv4 fingerprinting via DHCP Helper (Relay) on internal port.

    This test validates that Profiler correctly captures and fingerprints DHCPv4
    traffic received via DHCP relay (IP helper) to the PPS internal interface and
    creates a device record.

    Assumptions / Notes:
    - Low-level network actions (powering endpoint, switch configuration) are
      assumed to be handled by testbed automation or pre-test setup.
    - This UI test focuses on verifying Profiler configuration and resulting
      device record / fingerprinting via the PPS web UI.
    """

    page: Page = authenticated_page

    # Test data
    endpoint_mac = "AA:BB:CC:DD:EE:01"
    expected_vlan = "20"
    expected_ip_helper = "10.10.10.10"
    device_search_timeout_sec = 300  # up to 5 minutes for device to appear
    poll_interval_sec = 10

    # Helper function: safe click with explicit error context
    async def safe_click(selector: str, description: str) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=15000)
            await page.click(selector)
        except PlaywrightError as exc:
            raise AssertionError(f"Failed to click {description} using selector '{selector}': {exc}") from exc

    # Helper function: wait for text on page with timeout
    async def wait_for_text(text: str, timeout_ms: int = 30000) -> None:
        try:
            await page.wait_for_timeout(500)  # small delay to allow rendering
            await page.wait_for_function(
                """(t) => document.body && document.body.innerText.includes(t)""",
                text,
                timeout=timeout_ms,
            )
        except PlaywrightError as exc:
            raise AssertionError(f"Text '{text}' not found within {timeout_ms} ms: {exc}") from exc

    # -------------------------------------------------------------------------
    # Step 1: Log in to PPS admin UI as admin.
    # -------------------------------------------------------------------------
    # This is handled by the `authenticated_page` fixture from conftest.py.
    # We still verify that we are on an authenticated page by checking for a
    # known element in the admin UI (e.g., header or navigation).
    try:
        await page.wait_for_selector("nav[role='navigation'], header", timeout=20000)
    except PlaywrightError as exc:
        raise AssertionError(
            "Admin UI did not load correctly or user is not authenticated."
        ) from exc

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler Configuration > Settings > Basic Configuration.
    # -------------------------------------------------------------------------
    # The actual selectors will depend on the UI; here we assume menu structure.
    # Replace selectors/texts with the real ones in your environment.

    # Open Profiler Configuration menu
    await safe_click(
        "text=Profiler Configuration, text=Profiler >> Configuration, #profiler-config-menu",
        "Profiler Configuration menu",
    )

    # Click Settings
    await safe_click(
        "text=Settings, #profiler-settings-link",
        "Profiler Settings menu item",
    )

    # Click Basic Configuration
    await safe_click(
        "text=Basic Configuration, #profiler-basic-config-link",
        "Profiler Basic Configuration",
    )

    # Confirm we are on Basic Configuration page
    await wait_for_text("Basic Configuration")

    # -------------------------------------------------------------------------
    # Step 3: Confirm DHCP Sniffing mode is set to
    #         “DHCP Helper for internal ports” and applied.
    # -------------------------------------------------------------------------
    # Assume there is a select or radio group for DHCP Sniffing mode.
    # Adjust selectors as per actual DOM.

    dhcp_sniffing_selector = "select#dhcp-sniffing-mode, [name='dhcpSniffingMode']"
    try:
        dhcp_sniffing_element = await page.wait_for_selector(
            dhcp_sniffing_selector, timeout=15000
        )
    except PlaywrightError as exc:
        raise AssertionError(
            "DHCP Sniffing mode control not found on Basic Configuration page."
        ) from exc

    dhcp_sniffing_value = await dhcp_sniffing_element.input_value()
    expected_sniffing_value = "DHCP Helper for internal ports"

    # Some UIs store a code in value attribute and show readable text elsewhere.
    # Try to read visible text if the value doesn't match directly.
    if expected_sniffing_value not in dhcp_sniffing_value:
        # Try reading the selected option's text
        selected_option_text = await page.eval_on_selector(
            dhcp_sniffing_selector,
            """el => el.options[el.selectedIndex] && el.options[el.selectedIndex].text""",
        )
        assert (
            selected_option_text == expected_sniffing_value
        ), (
            "DHCP Sniffing mode is not set to "
            f"'{expected_sniffing_value}'. Actual: '{selected_option_text or dhcp_sniffing_value}'"
        )

    # Optionally verify an "Applied" / "Saved" status indicator.
    # This depends on implementation; we use a generic check.
    try:
        await page.wait_for_selector(
            "text=Configuration Applied, text=Settings saved successfully",
            timeout=10000,
        )
    except PlaywrightError:
        # Not fatal if UI does not show such a banner; log as soft check.
        pass

    # -------------------------------------------------------------------------
    # Step 4: On the access switch, verify ip helper-address is configured.
    # -------------------------------------------------------------------------
    # This is typically not verifiable via PPS UI. If PPS exposes switch config
    # or logs via UI, you could add UI checks here. For now, we treat this as
    # an external prerequisite and log it as an informational assertion.

    # Soft assertion / note: in real implementation, replace with API/CLI check.
    # Here we just ensure the expected IP helper address string is present in
    # some configuration/log view if available.
    # If there is no such view, comment this block out or adapt it.

    # Example (optional) UI check:
    # await safe_click("text=Network Devices, #network-devices-menu", "Network Devices menu")
    # await safe_click("text=Access Switches", "Access Switches list")
    # await safe_click("text=VLAN 20", "VLAN 20 row")
    # await wait_for_text(expected_ip_helper)

    # -------------------------------------------------------------------------
    # Step 5-6: Power cycle the test endpoint to trigger DHCP.
    # -------------------------------------------------------------------------
    # These are physical/network actions and assumed to be done by external
    # automation or pre-step. We add a wait window to allow DHCP traffic to be
    # seen and processed by Profiler.

    # Wait a bit to give the endpoint time to boot and complete DHCP.
    await page.wait_for_timeout(30000)  # 30 seconds initial wait

    # -------------------------------------------------------------------------
    # Step 7: In PPS, navigate to Profiler > Discovered Devices.
    # -------------------------------------------------------------------------
    await safe_click("text=Profiler, #profiler-main-menu", "Profiler main menu")
    await safe_click(
        "text=Discovered Devices, text=Devices, #profiler-discovered-devices-link",
        "Profiler Discovered Devices",
    )

    await wait_for_text("Discovered Devices")

    # -------------------------------------------------------------------------
    # Step 8: Search for the endpoint MAC or obtained IP.
    #         We primarily search by MAC here.
    # -------------------------------------------------------------------------
    search_input_selector = "input[name='deviceSearch'], #device-search-input"
    search_button_selector = "button:has-text('Search'), #device-search-button"

    try:
        search_input = await page.wait_for_selector(search_input_selector, timeout=15000)
    except PlaywrightError as exc:
        raise AssertionError(
            "Device search input not found on Discovered Devices page."
        ) from exc

    # Poll until the device appears or timeout expires
    device_row_selector = (
        f"tr:has-text('{endpoint_mac}') "
        f", tr[data-mac='{endpoint_mac}']"
    )

    end_time = datetime.utcnow() + timedelta(seconds=device_search_timeout_sec)
    device_found = False

    while datetime.utcnow() < end_time and not device_found:
        # Clear previous search text
        await search_input.fill("")
        await search_input.fill(endpoint_mac)

        try:
            await safe_click(search_button_selector, "Device search button")
        except AssertionError:
            # Some UIs search on type; ignore if button missing
            pass

        # Wait briefly for search results to update
        await page.wait_for_timeout(poll_interval_sec * 1000)

        try:
            await page.wait_for_selector(device_row_selector, timeout=5000)
            device_found = True
        except PlaywrightError:
            # Device not found yet; continue polling
            continue

    assert device_found, (
        f"Device with MAC '{endpoint_mac}' did not appear in Discovered Devices "
        f"within {device_search_timeout_sec} seconds."
    )

    # -------------------------------------------------------------------------
    # Step 9: Open the device details page.
    # -------------------------------------------------------------------------
    try:
        await page.click(device_row_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            f"Failed to open device details for MAC '{endpoint_mac}'."
        ) from exc

    # Confirm that device details page is loaded
    await wait_for_text("Device Details")

    # -------------------------------------------------------------------------
    # Expected Result 1:
    # DHCP DISCOVER/OFFER/REQUEST/ACK exchange is seen in Profiler logs/packet capture.
    # -------------------------------------------------------------------------
    # We assume the device details page has a DHCP or Activity/Logs tab.
    # Adjust selectors and text according to actual UI.

    # Navigate to DHCP / Activity tab
    await safe_click(
        "text=DHCP, text=Activity, #device-dhcp-tab",
        "Device DHCP/Activity tab",
    )

    # Verify all four DHCP message types are recorded for this device.
    dhcp_events = ["DISCOVER", "OFFER", "REQUEST", "ACK"]
    for event in dhcp_events:
        try:
            await wait_for_text(event, timeout_ms=60000)
        except AssertionError as exc:
            raise AssertionError(
                f"DHCP event '{event}' not found in device DHCP logs."
            ) from exc

    # -------------------------------------------------------------------------
    # Expected Result 2:
    # A new device record is created with the specified MAC address.
    # -------------------------------------------------------------------------
    # Confirm MAC on the details page matches the expected MAC.

    mac_label_selector = "text=MAC Address, .device-mac, #device-mac"
    try:
        mac_text = await page.inner_text(mac_label_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            "Could not read MAC address from device details page."
        ) from exc

    assert endpoint_mac.lower() in mac_text.lower(), (
        f"Device MAC on details page does not match expected MAC. "
        f"Expected: {endpoint_mac}, Actual text: {mac_text}"
    )

    # -------------------------------------------------------------------------
    # Expected Result 3:
    # Device classification shows a Windows desktop/laptop based on DHCP fingerprint.
    # -------------------------------------------------------------------------
    classification_selector = "text=Device Type, .device-type, #device-type"
    try:
        classification_text = await page.inner_text(classification_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            "Could not read device classification from device details page."
        ) from exc

    # Accept any classification indicating Windows desktop/laptop
    classification_text_lower = classification_text.lower()
    assert any(
        keyword in classification_text_lower
        for keyword in ["windows", "desktop", "laptop", "win10", "win 10"]
    ), (
        "Device classification does not indicate a Windows desktop/laptop. "
        f"Actual classification text: '{classification_text}'"
    )

    # -------------------------------------------------------------------------
    # Expected Result 4:
    # Device IP, VLAN, and first-seen timestamp are correctly populated.
    # -------------------------------------------------------------------------
    ip_selector = "text=IP Address, .device-ip, #device-ip"
    vlan_selector = "text=VLAN, .device-vlan, #device-vlan"
    first_seen_selector = "text=First Seen, .device-first-seen, #device-first-seen"

    try:
        device_ip_text = await page.inner_text(ip_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            "Could not read device IP address from device details page."
        ) from exc

    try:
        device_vlan_text = await page.inner_text(vlan_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            "Could not read device VLAN from device details page."
        ) from exc

    try:
        first_seen_text = await page.inner_text(first_seen_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            "Could not read device first-seen timestamp from device details page."
        ) from exc

    # Basic IP sanity check
    assert any(char.isdigit() for char in device_ip_text), (
        f"Device IP appears empty or invalid: '{device_ip_text}'"
    )

    # VLAN check
    assert expected_vlan in device_vlan_text, (
        f"Device VLAN is not '{expected_vlan}'. Actual VLAN text: '{device_vlan_text}'"
    )

    # First-seen timestamp non-empty check
    assert first_seen_text.strip(), "First-seen timestamp is empty."

    # Optionally, validate timestamp format or recency if format is known.
    # Example (soft check): ensure it's not a placeholder like "N/A".
    assert "n/a" not in first_seen_text.lower(), (
        f"First-seen timestamp is not populated correctly: '{first_seen_text}'"
    )

    # -------------------------------------------------------------------------
    # Postconditions:
    # Device entry for the test endpoint remains in Profiler database with
    # correct classification and DHCPv4 metadata.
    #
    # This is inherently long-lived; here we only ensure that the device entry
    # is still visible after a short delay as a minimal persistence check.
    # -------------------------------------------------------------------------
    await page.wait_for_timeout(5000)

    # Refresh the page and re-validate MAC presence
    await page.reload(wait_until="networkidle")

    try:
        mac_text_after_reload = await page.inner_text(mac_label_selector)
    except PlaywrightError as exc:
        raise AssertionError(
            "After reload, could not read MAC address from device details page."
        ) from exc

    assert endpoint_mac.lower() in mac_text_after_reload.lower(), (
        "Device entry for the test endpoint did not persist after page reload."
    )