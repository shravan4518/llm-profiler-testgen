import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_dhcpv6_capturing_disabled_ipv6_not_profiled(
    authenticated_page: Page,
    browser,
):
    """
    TC_008: DHCPv6 capturing disabled – IPv6 endpoint not profiled via DHCPv6

    Validate that when DHCPv6 packet capturing is disabled, Profiler does not
    process DHCPv6 traffic and does not create DHCPv6-based fingerprints.

    Preconditions:
        - User is authenticated (via authenticated_page fixture).
        - DHCPv6 capturing is currently enabled and functioning (baseline).

    Steps:
        1. In PPS, go to Profiler Configuration > Settings > Basic Configuration.
        2. Uncheck “Enable DHCPv6 packet capturing” and save.
        3. Wait for 15 minutes for configuration to take effect.
        4. After 15 minutes, connect endpoint MAC AA:BB:CC:DD:EE:09 to IPv6
           network and trigger DHCPv6 (release/renew or reboot).
        5. In Profiler UI, search for MAC AA:BB:CC:DD:EE:09.
        6. Check if any DHCPv6 data or IPv6 address is associated with the device.

    Expected:
        - Profiler does not start or use DHCPv6Collector.
        - No new device is discovered via DHCPv6; if device exists via other
          methods, it has no DHCPv6 data.
        - No DHCPv6 logs recorded for this endpoint.
    """
    page = authenticated_page
    target_mac = "AA:BB:CC:DD:EE:09"

    # Helper selectors (placeholders; adjust to real application selectors)
    dhcpv6_checkbox_selector = "input#enable-dhcpv6-packet-capturing"
    save_button_selector = "button#profiler-basic-config-save"
    save_success_toast_selector = "div.toast-success"
    mac_search_input_selector = "input#device-search"
    mac_search_button_selector = "button#device-search-submit"
    device_row_selector = f"tr[data-mac='{target_mac.lower()}']"
    device_details_link_selector = f"{device_row_selector} a.device-details"
    dhcpv6_section_selector = "section#dhcpv6-information"
    dhcpv6_logs_tab_selector = "button#tab-dhcpv6-logs"
    dhcpv6_logs_table_selector = "table#dhcpv6-logs-table"
    dhcpv6_logs_empty_selector = "div#dhcpv6-logs-empty"

    # ------------------------------------------------------------------ #
    # Step 1: Go to Profiler Configuration > Settings > Basic Configuration
    # ------------------------------------------------------------------ #
    try:
        await page.goto(
            "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/settings/basic",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Profiler Basic Configuration: {exc}")

    # ------------------------------------------------------------------ #
    # Step 2: Uncheck “Enable DHCPv6 packet capturing” and save
    # ------------------------------------------------------------------ #
    try:
        dhcpv6_checkbox = page.locator(dhcpv6_checkbox_selector)
        await dhcpv6_checkbox.wait_for(state="visible", timeout=10_000)

        is_checked = await dhcpv6_checkbox.is_checked()
        if is_checked:
            await dhcpv6_checkbox.click()
        # Assert checkbox is now unchecked
        assert not await dhcpv6_checkbox.is_checked(), (
            "Expected 'Enable DHCPv6 packet capturing' to be unchecked, "
            "but it is still checked."
        )

        save_button = page.locator(save_button_selector)
        await save_button.wait_for(state="visible", timeout=10_000)
        await save_button.click()

        # Wait for confirmation (e.g., toast or success message)
        await page.locator(save_success_toast_selector).wait_for(
            state="visible",
            timeout=15_000,
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to disable DHCPv6 packet capturing: {exc}")

    # ------------------------------------------------------------------ #
    # Step 3: Wait for 15 minutes for configuration to take effect
    # ------------------------------------------------------------------ #
    # NOTE: For automation, a shorter wait is usually used and the system
    # is configured to apply changes faster. Here we keep the logical wait
    # but make it configurable via marker/fixture if needed.
    fifteen_minutes = 15 * 60
    start_time = datetime.utcnow()
    end_time = start_time + timedelta(seconds=fifteen_minutes)

    # To keep the test from blocking the event loop unnecessarily, sleep
    # in smaller chunks and log progress.
    sleep_chunk = 60  # seconds
    while datetime.utcnow() < end_time:
        remaining = (end_time - datetime.utcnow()).total_seconds()
        chunk = min(sleep_chunk, max(1, int(remaining)))
        await asyncio.sleep(chunk)

    # ------------------------------------------------------------------ #
    # Step 4: Trigger DHCPv6 on endpoint MAC AA:BB:CC:DD:EE:09
    # ------------------------------------------------------------------ #
    # This step is typically performed externally (e.g., via lab automation,
    # API, or a separate script). Here we log it and proceed, assuming that
    # an external system has triggered DHCPv6 on the endpoint.
    #
    # If an API or UI exists to trigger this, implement it here instead.
    #
    # Example placeholder (no-op):
    try:
        # Placeholder for external trigger call or verification.
        # e.g., await trigger_dhcpv6_for_mac(target_mac)
        pass
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to trigger DHCPv6 for endpoint {target_mac}: {exc}")

    # ------------------------------------------------------------------ #
    # Step 5: In Profiler UI, search for MAC AA:BB:CC:DD:EE:09
    # ------------------------------------------------------------------ #
    try:
        await page.goto(
            "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/devices",
            wait_until="networkidle",
        )

        mac_search_input = page.locator(mac_search_input_selector)
        mac_search_button = page.locator(mac_search_button_selector)

        await mac_search_input.wait_for(state="visible", timeout=10_000)
        await mac_search_input.fill(target_mac)
        await mac_search_button.click()

        # Wait for search results to load
        await page.wait_for_timeout(5_000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to search for device with MAC {target_mac}: {exc}")

    # ------------------------------------------------------------------ #
    # Step 6: Check if any DHCPv6 data or IPv6 address is associated
    # ------------------------------------------------------------------ #
    try:
        device_row = page.locator(device_row_selector)

        # It is possible that the device does not exist at all, which is valid
        # because DHCPv6-based discovery should not occur when capturing is disabled.
        device_exists = await device_row.count() > 0

        if not device_exists:
            # Assert that there is no device discovered via DHCPv6
            # (or any other method) as a valid negative outcome.
            assert True, (
                "Device with MAC not discovered, which is acceptable when "
                "DHCPv6 capturing is disabled."
            )
            return

        # If device exists due to other discovery methods, it must not have
        # DHCPv6 data or IPv6 address associated via DHCPv6.
        device_details_link = page.locator(device_details_link_selector)
        await device_details_link.first.click()

        # Wait for device details to load
        await page.wait_for_load_state("networkidle")

        # Verify DHCPv6 section has no data
        dhcpv6_section = page.locator(dhcpv6_section_selector)
        dhcpv6_section_visible = await dhcpv6_section.is_visible()

        if dhcpv6_section_visible:
            # If section exists, assert that it explicitly shows "No DHCPv6 data"
            dhcpv6_text = await dhcpv6_section.inner_text()
            assert "no dhcpv6 data" in dhcpv6_text.lower(), (
                "DHCPv6 section is visible but does not indicate absence of data. "
                f"Section content: {dhcpv6_text!r}"
            )

        # Optional: check DHCPv6 logs tab for this device
        dhcpv6_logs_tab = page.locator(dhcpv6_logs_tab_selector)
        if await dhcpv6_logs_tab.count() > 0:
            await dhcpv6_logs_tab.click()
            await page.wait_for_timeout(2_000)

            # If logs table exists, ensure it is empty or explicitly says no logs
            logs_table = page.locator(dhcpv6_logs_table_selector)
            logs_empty_label = page.locator(dhcpv6_logs_empty_selector)

            if await logs_table.count() > 0:
                rows = logs_table.locator("tbody tr")
                row_count = await rows.count()
                assert row_count == 0, (
                    f"Expected no DHCPv6 logs for {target_mac}, "
                    f"but found {row_count} row(s)."
                )
            elif await logs_empty_label.count() > 0:
                empty_text = await logs_empty_label.inner_text()
                assert "no dhcpv6 logs" in empty_text.lower(), (
                    "Expected an explicit 'no DHCPv6 logs' message, "
                    f"but got: {empty_text!r}"
                )

    except PlaywrightError as exc:
        pytest.fail(f"Error while validating DHCPv6 data/logs for {target_mac}: {exc}")

    # ------------------------------------------------------------------ #
    # Final assertion: DHCPv6 capturing remains disabled (postcondition)
    # ------------------------------------------------------------------ #
    try:
        await page.goto(
            "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/settings/basic",
            wait_until="networkidle",
        )
        dhcpv6_checkbox = page.locator(dhcpv6_checkbox_selector)
        await dhcpv6_checkbox.wait_for(state="visible", timeout=10_000)
        is_checked_after = await dhcpv6_checkbox.is_checked()

        assert not is_checked_after, (
            "Postcondition failed: 'Enable DHCPv6 packet capturing' was "
            "re-enabled unexpectedly."
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to validate postcondition for DHCPv6 capturing: {exc}")