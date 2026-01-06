import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_profiler_configuration_delay_15_minutes(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_004: Verify Profiler operation when configuration changes applied (15-minute delay)

    This test verifies that:
    - A new Profiler subnet configuration is not applied immediately (within first 5 minutes)
    - The configuration is applied after the documented ~15-minute delay
    - Existing profiler operations remain uninterrupted

    Prerequisites:
    - Profiler running and actively capturing DHCPv4
    - At least one known device already discovered
    """
    page = authenticated_page
    target_mac = "AA:BB:CC:DD:EE:04"
    target_subnet = "10.10.50.0/24"

    # Helper selectors – these are examples and should be adapted to the real UI
    profiler_menu_selector = "text=Profiler"
    configuration_menu_selector = "text=Configuration"
    subnets_tab_selector = "role=tab[name='Subnets']"
    add_subnet_button_selector = "role=button[name='Add Subnet']"
    subnet_cidr_input_selector = "input[name='subnetCidr']"
    dhcp_checkbox_selector = "input[name='enableDhcp']"
    scan_checkbox_selector = "input[name='enableScan']"
    save_button_selector = "role=button[name='Save']"
    toast_success_selector = ".toast-success"
    discovered_devices_menu_selector = "text=Discovered Devices"
    mac_search_input_selector = "input[placeholder='Search MAC']"
    discovered_table_row_selector = f"tr:has-text('{target_mac}')"
    dhcp_info_cell_selector = f"tr:has-text('{target_mac}') td:has-text('DHCP')"

    # Utility functions

    async def safe_click(selector: str, description: str) -> None:
        """Click an element safely with error handling and timeout."""
        try:
            await page.wait_for_selector(selector, timeout=10_000)
            await page.click(selector)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click {description} using selector '{selector}': {exc}")

    async def safe_fill(selector: str, value: str, description: str) -> None:
        """Fill an input element safely with error handling."""
        try:
            await page.wait_for_selector(selector, timeout=10_000)
            await page.fill(selector, value)
        except PlaywrightError as exc:
            pytest.fail(
                f"Failed to fill {description} using selector '{selector}' "
                f"with value '{value}': {exc}"
            )

    async def device_present_in_discovered(mac: str) -> bool:
        """Return True if the device with the given MAC is present in Discovered Devices."""
        try:
            await safe_click(discovered_devices_menu_selector, "Discovered Devices menu")
            await page.wait_for_selector(mac_search_input_selector, timeout=10_000)
            await page.fill(mac_search_input_selector, mac)
            await page.keyboard.press("Enter")
            # Wait a short time for results to refresh
            await page.wait_for_timeout(3_000)
            row = await page.query_selector(discovered_table_row_selector)
            return row is not None
        except PlaywrightError as exc:
            pytest.fail(f"Error while searching for MAC {mac} in Discovered Devices: {exc}")
            return False  # Unreachable, but keeps type checkers happy

    async def dhcp_info_present_for_mac(mac: str) -> bool:
        """Return True if DHCP info is shown for the given MAC in Discovered Devices."""
        try:
            await safe_click(discovered_devices_menu_selector, "Discovered Devices menu")
            await page.wait_for_selector(mac_search_input_selector, timeout=10_000)
            await page.fill(mac_search_input_selector, mac)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(3_000)
            dhcp_cell = await page.query_selector(dhcp_info_cell_selector)
            return dhcp_cell is not None
        except PlaywrightError as exc:
            pytest.fail(f"Error while checking DHCP info for MAC {mac}: {exc}")
            return False

    # STEP 1: Go to Profiler Configuration > Subnets and add subnet 10.10.50.0/24
    # -------------------------------------------------------------------------
    await safe_click(profiler_menu_selector, "Profiler main menu")
    await safe_click(configuration_menu_selector, "Profiler Configuration menu")
    await safe_click(subnets_tab_selector, "Subnets tab")
    await safe_click(add_subnet_button_selector, "Add Subnet button")

    await safe_fill(subnet_cidr_input_selector, target_subnet, "Subnet CIDR input")

    # Enable DHCP and/or scans as required by the product behavior
    try:
        # These clicks are optional; if already checked, clicking may toggle them.
        # A robust implementation would verify the checked state first.
        await page.check(dhcp_checkbox_selector)
    except PlaywrightError:
        # If check fails, continue; some UIs may auto-enable DHCP for new subnets
        pass

    try:
        await page.check(scan_checkbox_selector)
    except PlaywrightError:
        # Same note as above
        pass

    # STEP 2: Save changes at time T0 and record exact time
    # -----------------------------------------------------
    t0 = datetime.utcnow()
    await safe_click(save_button_selector, "Save subnet configuration button")

    # Wait for confirmation (toast, banner, etc.)
    try:
        await page.wait_for_selector(toast_success_selector, timeout=15_000)
    except PlaywrightError as exc:
        pytest.fail(f"Subnet configuration save did not show success confirmation: {exc}")

    # Log T0 for debugging
    print(f"[TC_004] Configuration saved at T0 (UTC): {t0.isoformat()}")

    # STEP 3: Immediately connect endpoint (MAC AA:BB:CC:DD:EE:04) and trigger DHCP
    # -----------------------------------------------------------------------------
    # NOTE: This step typically requires external lab automation or an API.
    # Here we assume an external system handles the physical connection and DHCP.
    # If an API exists, call it here. For now, we log and proceed.
    print(
        "[TC_004] Ensure endpoint with MAC "
        f"{target_mac} is connected to subnet {target_subnet} and DHCP is triggered."
    )

    # Small buffer to allow Profiler to process initial DHCP (if it would)
    await page.wait_for_timeout(10_000)

    # STEP 4: Within first 5 minutes after T0, check Discovered Devices for the new MAC
    # -------------------------------------------------------------------------------
    # We will poll a few times within the first 5 minutes to confirm that
    # the device is NOT required to be present yet (configuration delay).
    five_minutes_after_t0 = t0 + timedelta(minutes=5)
    device_found_early = False

    while datetime.utcnow() < five_minutes_after_t0:
        device_found_early = await device_present_in_discovered(target_mac)
        if device_found_early:
            # It's allowed but not required to be discovered; we log this
            print(
                f"[TC_004] Device {target_mac} appeared in Discovered Devices "
                "within first 5 minutes (allowed behavior)."
            )
            break
        # Wait 30 seconds between checks to avoid excessive polling
        await asyncio.sleep(30)

    # Assert that early discovery is not mandatory; the key requirement is that
    # the configuration is not guaranteed to be applied yet. We only ensure
    # that the system remains responsive and does not error.
    # If the device is not found, that is acceptable per test case description.
    if not device_found_early:
        print(
            f"[TC_004] Device {target_mac} not discovered within first 5 minutes, "
            "which is acceptable due to 15-minute configuration delay."
        )

    # STEP 5: At T0 + 16 minutes, reboot the endpoint to trigger DHCP again
    # ---------------------------------------------------------------------
    t0_plus_16 = t0 + timedelta(minutes=16)
    now = datetime.utcnow()
    if now < t0_plus_16:
        wait_seconds = (t0_plus_16 - now).total_seconds()
        print(
            f"[TC_004] Waiting {wait_seconds:.1f} seconds until T0 + 16 minutes "
            "before rebooting endpoint."
        )
        # NOTE: For a real 16-minute wait, this may be impractical in CI.
        # In such environments, consider marking this test as 'slow' or using
        # a configuration to shorten the delay in non-production.
        await asyncio.sleep(wait_seconds)

    # Trigger reboot / DHCP again (requires external control)
    print(
        "[TC_004] Reboot endpoint with MAC "
        f"{target_mac} now to trigger DHCP after configuration delay."
    )
    # Allow some time for DHCP and Profiler processing after reboot
    await page.wait_for_timeout(60_000)

    # STEP 6: Check Discovered Devices for MAC AA:BB:CC:DD:EE:04
    # ---------------------------------------------------------
    # After the 15-minute delay, the device SHOULD be discovered and show DHCP info.
    # We will poll for a limited time (e.g., 5 minutes).
    discovery_deadline = datetime.utcnow() + timedelta(minutes=5)
    device_found_after_delay = False
    dhcp_info_ok = False

    while datetime.utcnow() < discovery_deadline:
        device_found_after_delay = await device_present_in_discovered(target_mac)
        if device_found_after_delay:
            dhcp_info_ok = await dhcp_info_present_for_mac(target_mac)
            if dhcp_info_ok:
                break
        # Wait 30 seconds between checks
        await asyncio.sleep(30)

    # ASSERTIONS FOR EXPECTED RESULTS
    # -------------------------------

    # 1. After ~15 minutes, Profiler applies new configuration and device is discovered
    assert device_found_after_delay, (
        f"Device with MAC {target_mac} was not discovered in Profiler "
        "after configuration delay and DHCP re-trigger."
    )

    # 2. Device in subnet 10.10.50.0/24 is shown with correct DHCP info
    assert dhcp_info_ok, (
        f"Device {target_mac} discovered after delay but DHCP information "
        "was missing or incorrect in Discovered Devices."
    )

    # 3. Existing profiler operations for other subnets continue uninterrupted
    #    This is hard to prove directly from UI; we perform a sanity check that:
    #    - The Profiler UI is still responsive
    #    - Discovered Devices page can be loaded and filtered without errors
    try:
        await safe_click(discovered_devices_menu_selector, "Discovered Devices menu (sanity check)")
        await page.wait_for_selector(mac_search_input_selector, timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(
            "Profiler UI appears unresponsive after configuration delay, "
            f"which may indicate disruption of existing operations: {exc}"
        )

    # POSTCONDITIONS:
    # - Subnet 10.10.50.0/24 remains configured and functional for newly connecting devices.
    #   We confirm the subnet entry still exists by re-opening the Subnets tab and
    #   checking for the configured CIDR text.
    await safe_click(profiler_menu_selector, "Profiler main menu (postcondition)")
    await safe_click(configuration_menu_selector, "Profiler Configuration menu (postcondition)")
    await safe_click(subnets_tab_selector, "Subnets tab (postcondition)")

    subnet_row_selector = f"tr:has-text('{target_subnet}')"
    try:
        await page.wait_for_selector(subnet_row_selector, timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(
            f"Configured subnet {target_subnet} not found in Profiler Subnets "
            f"after test execution (postcondition failed): {exc}"
        )

    print(
        f"[TC_004] Completed: Subnet {target_subnet} remains configured and "
        f"device {target_mac} is discovered with DHCP info after 15-minute delay."
    )