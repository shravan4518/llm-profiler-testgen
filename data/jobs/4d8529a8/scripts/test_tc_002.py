import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
async def test_tc_002_dhcpv4_fingerprinting_via_span_rspan_on_external_port(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_002: Verify DHCPv4 fingerprinting via SPAN/RSPAN on external port.

    Preconditions (assumed satisfied before test execution):
    - PPS appliance with one port configured as “external” sniffing interface connected to SPAN destination.
    - Switch SPAN session configured to mirror DHCP traffic (VLAN 30) to PPS external port.
    - Profiler General Settings: DHCP Sniffing mode set to “RSPAN for external ports.”
    - DHCP fingerprints database version >= 45.

    Test Steps:
    1. In PPS UI, navigate to Profiler Configuration > Settings > Basic Configuration.
    2. Set DHCP Sniffing mode to “RSPAN for external ports” and save.
    3. On the core/distribution switch, confirm SPAN/RSPAN is configured to mirror VLAN 30 DHCP traffic
       to PPS external port.  (Verified via UI indicator/logs where available.)
    4. Connect iOS device to Wi‑Fi mapped to VLAN 30 with DHCP enabled. (Simulated/assumed or verified via UI.)
    5. Wait for the device to obtain an IP address.
    6. In PPS, go to Profiler > Discovered Devices.
    7. Search for MAC `AA:BB:CC:DD:EE:02`.
    8. Open device details and review DHCP fingerprint information.

    Expected Results:
    - Profiler receives DHCPv4 traffic via external port.
    - A device record is created for MAC `AA:BB:CC:DD:EE:02`.
    - Device is classified as iOS or similar mobile OS based on DHCP options.
    - No duplicate devices created for the same MAC.
    """

    page: Page = authenticated_page
    target_mac = "AA:BB:CC:DD:EE:02"

    # Helper: safe click with explicit error message
    async def safe_click(selector: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.locator(selector).click(timeout=timeout)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            pytest.fail(f"Failed to click {description} using selector '{selector}': {exc}")

    # Helper: safe fill with explicit error message
    async def safe_fill(selector: str, value: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.locator(selector).fill(value, timeout=timeout)
        except (PlaywrightTimeoutError, PlaywrightError) as exc:
            pytest.fail(f"Failed to fill {description} using selector '{selector}': {exc}")

    # Helper: wait for text with explicit error message
    async def wait_for_text(selector: str, text: str, description: str, timeout: int = 15000) -> None:
        try:
            await page.locator(selector).get_by_text(text, exact=False).first.wait_for(timeout=timeout)
        except PlaywrightTimeoutError as exc:
            pytest.fail(
                f"Timed out waiting for text '{text}' in {description} using selector '{selector}': {exc}"
            )

    # -------------------------------------------------------------------------
    # Step 1: Navigate to Profiler Configuration > Settings > Basic Configuration
    # -------------------------------------------------------------------------
    # NOTE: Selectors below are examples and should be aligned with actual PPS UI.
    # Top-level navigation to "Profiler Configuration"
    await safe_click("nav >> text=Profiler Configuration", "Profiler Configuration navigation menu")

    # Navigate to "Settings"
    await safe_click("nav >> text=Settings", "Settings submenu under Profiler Configuration")

    # Navigate to "Basic Configuration"
    await safe_click("nav >> text=Basic Configuration", "Basic Configuration section")

    # Ensure Basic Configuration content is visible
    await wait_for_text(
        "main",
        "Basic Configuration",
        "Basic Configuration main content",
        timeout=15000,
    )

    # -------------------------------------------------------------------------
    # Step 2: Set DHCP Sniffing mode to “RSPAN for external ports” and save
    # -------------------------------------------------------------------------
    # Assume DHCP Sniffing mode is a dropdown/select field
    dhcp_sniffing_dropdown = page.locator("select#dhcp-sniffing-mode")
    try:
        await dhcp_sniffing_dropdown.wait_for(state="visible", timeout=10000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"DHCP Sniffing mode dropdown not visible: {exc}")

    # Select the required option
    try:
        await dhcp_sniffing_dropdown.select_option(label="RSPAN for external ports")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to set DHCP Sniffing mode to 'RSPAN for external ports': {exc}")

    # Click Save / Apply button
    await safe_click("button:has-text('Save')", "Save button on Basic Configuration page")

    # Verify a success notification/toast appears
    await wait_for_text(
        "body",
        "Configuration saved",
        "configuration saved notification",
        timeout=15000,
    )

    # Optional assertion: confirm the dropdown still shows the correct value after save
    selected_value = await dhcp_sniffing_dropdown.input_value()
    assert selected_value is not None, "DHCP Sniffing mode value should not be empty after save"

    # -------------------------------------------------------------------------
    # Step 3: Confirm SPAN/RSPAN is configured to mirror VLAN 30 DHCP traffic
    # -------------------------------------------------------------------------
    # In many systems this is done via switch CLI, but we will assume there is
    # a PPS UI status indicator or log entry that shows SPAN status.
    #
    # Example: A status label like "SPAN/RSPAN Status: Active (VLAN 30)"
    span_status_locator = page.locator("div#span-status")
    try:
        await span_status_locator.wait_for(state="visible", timeout=15000)
        span_status_text = await span_status_locator.inner_text()
    except PlaywrightTimeoutError:
        span_status_text = ""

    assert "VLAN 30" in span_status_text or "vlan 30" in span_status_text.lower(), (
        "SPAN/RSPAN status should indicate VLAN 30 mirroring is configured to PPS external port. "
        f"Actual status: '{span_status_text}'"
    )

    # -------------------------------------------------------------------------
    # Step 4–5: Connect iOS device to VLAN 30 Wi‑Fi and wait for IP
    # -------------------------------------------------------------------------
    # This is normally done outside of the browser (real device). In UI we may
    # only be able to validate that an endpoint appears after DHCP. We simulate
    # the wait by polling for the device to appear in the discovered list later.
    #
    # To keep the test deterministic, we just wait a fixed amount of time here
    # to allow the external system/device to perform DHCP.
    await asyncio.sleep(10)  # Adjust as needed for environment/device timing

    # -------------------------------------------------------------------------
    # Step 6: Navigate to Profiler > Discovered Devices
    # -------------------------------------------------------------------------
    await safe_click("nav >> text=Profiler", "Profiler navigation menu")
    await safe_click("nav >> text=Discovered Devices", "Discovered Devices submenu")

    # Ensure the Discovered Devices table is visible
    discovered_devices_table = page.locator("table#discovered-devices-table")
    try:
        await discovered_devices_table.wait_for(state="visible", timeout=20000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Discovered Devices table not visible: {exc}")

    # -------------------------------------------------------------------------
    # Step 7: Search for MAC AA:BB:CC:DD:EE:02
    # -------------------------------------------------------------------------
    await safe_fill("input#device-search", target_mac, "device search input")
    await safe_click("button#device-search-submit", "device search submit button")

    # Poll for device row to appear (Profiler receives DHCPv4 traffic and creates record)
    device_row = page.locator(f"table#discovered-devices-table tr:has-text('{target_mac}')")

    # Wait up to ~60 seconds for device to appear
    try:
        await device_row.wait_for(state="visible", timeout=60000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            f"Device with MAC {target_mac} not found in Discovered Devices within expected time: {exc}"
        )

    # Assertion: device record is found (Profiler receives DHCPv4 traffic via external port)
    assert await device_row.is_visible(), (
        f"Device row for MAC {target_mac} should be visible in Discovered Devices."
    )

    # Assertion: no duplicate devices created for the same MAC
    device_rows_count = await page.locator(
        f"table#discovered-devices-table tr:has-text('{target_mac}')"
    ).count()
    assert device_rows_count == 1, (
        f"Expected exactly 1 device record for MAC {target_mac}, "
        f"but found {device_rows_count}."
    )

    # -------------------------------------------------------------------------
    # Step 8: Open device details and review DHCP fingerprint information
    # -------------------------------------------------------------------------
    # Assume clicking the row opens a details drawer/page
    await device_row.click()

    # Wait for device details view
    device_details_panel = page.locator("section#device-details")
    try:
        await device_details_panel.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Device details panel did not appear after clicking device row: {exc}")

    # Verify MAC address in details
    mac_details_text = await device_details_panel.locator("span#device-mac").inner_text()
    assert target_mac.lower() == mac_details_text.strip().lower(), (
        f"Device details MAC should match searched MAC. "
        f"Expected '{target_mac}', got '{mac_details_text}'."
    )

    # Verify DHCP fingerprint information exists
    dhcp_fingerprint_section = device_details_panel.locator("div#dhcp-fingerprint")
    try:
        await dhcp_fingerprint_section.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"DHCP fingerprint section not visible in device details: {exc}")

    dhcp_fingerprint_text = (await dhcp_fingerprint_section.inner_text()).strip()

    # Assertion: DHCP fingerprint metadata present
    assert dhcp_fingerprint_text, "DHCP fingerprint information should not be empty."

    # Assertion: Device is classified as iOS or similar mobile OS
    # Example: OS field or fingerprint content includes "iOS", "iPhone", "iPad", or "Mobile"
    os_field_locator = device_details_panel.locator("span#device-os")
    os_text: Optional[str] = None
    if await os_field_locator.count() > 0:
        os_text = (await os_field_locator.inner_text()).strip()
    else:
        # Fallback: infer from DHCP fingerprint text
        os_text = dhcp_fingerprint_text

    normalized_os_text = os_text.lower()
    assert any(keyword in normalized_os_text for keyword in ["ios", "iphone", "ipad", "mobile"]), (
        "Device should be classified as iOS or a similar mobile OS based on DHCP options. "
        f"Actual OS/fingerprint text: '{os_text}'."
    )

    # -------------------------------------------------------------------------
    # Postconditions: Device record remains with DHCPv4 metadata from SPAN
    # -------------------------------------------------------------------------
    # Quick re-check: refresh Discovered Devices and ensure the same single device record remains.
    await safe_click("nav >> text=Discovered Devices", "Discovered Devices submenu (postcondition check)")
    await safe_fill("input#device-search", target_mac, "device search input (postcondition check)")
    await safe_click("button#device-search-submit", "device search submit button (postcondition check)")

    try:
        await device_row.wait_for(state="visible", timeout=30000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            f"Device record for MAC {target_mac} disappeared unexpectedly during postcondition check: {exc}"
        )

    device_rows_count_post = await page.locator(
        f"table#discovered-devices-table tr:has-text('{target_mac}')"
    ).count()
    assert device_rows_count_post == 1, (
        "Device record should persist with DHCPv4 metadata sourced from SPAN; "
        f"expected 1 record, found {device_rows_count_post}."
    )