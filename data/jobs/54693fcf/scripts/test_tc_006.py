import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_006_snmp_trap_from_unknown_switch(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_006: Verify handling of SNMP trap from non-configured (unknown) switch.

    This test validates that when Profiler receives an SNMP trap from a switch
    that is not configured as an SNMP device, it:
      - Does not create a new endpoint based solely on the trap.
      - Logs a clear message about the trap from an unknown device.
      - Does not crash or throw unhandled exceptions.

    Prerequisites:
      - Profiler running with trap listener enabled.
      - Switch 10.10.30.30 is NOT configured as an SNMP device in Profiler.
      - External environment is responsible for:
          * Configuring the switch to send linkUp/linkDown traps.
          * Connecting endpoint 11:22:33:44:55:66 to Gi1/0/10.
          * Ensuring traps reach Profiler (packet capture / network setup).
    """
    page = authenticated_page

    # Test data
    unknown_switch_ip = "10.10.30.30"
    endpoint_mac = "11:22:33:44:55:66"
    wait_for_trap_seconds = 120  # 2 minutes
    log_poll_interval_seconds = 10
    log_poll_timeout_seconds = 180  # 3 minutes for log availability

    # Helper function: wait for log message indicating unknown device trap
    async def wait_for_unknown_device_log() -> bool:
        """
        Polls the Profiler logs UI for a message indicating that a trap
        was received from an unconfigured/unknown device.

        Returns:
            bool: True if expected log message is found within timeout,
                  False otherwise.
        """
        deadline = datetime.utcnow() + timedelta(seconds=log_poll_timeout_seconds)

        while datetime.utcnow() < deadline:
            try:
                # Navigate to logs page (adjust URL / navigation as needed)
                # Example: click "Logs" in main navigation
                await page.goto("https://10.34.50.201/dana-na/auth/url_admin/logs.cgi")

                # If there is a filter/search field for logs, use it
                # Adjust selectors to your actual UI
                search_input = page.locator("input[name='logSearch']")
                if await search_input.is_visible():
                    await search_input.fill(unknown_switch_ip)
                    await search_input.press("Enter")

                # Wait for logs to refresh
                await page.wait_for_timeout(2000)

                # Look for a row / message that indicates trap from unknown device
                # These selectors and text are examples and should be adjusted
                log_row_locator = page.locator(
                    "table#logsTable tr",
                    has_text="trap",
                ).filter(has_text=unknown_switch_ip)

                if await log_row_locator.count() > 0:
                    # Optionally, assert the log text contains a warning/error message
                    # about unconfigured device
                    log_text = await log_row_locator.nth(0).inner_text()
                    assert "unconfigured" in log_text.lower() or \
                        "unknown" in log_text.lower(), (
                            "Log entry found for trap from unknown device, but "
                            "message does not clearly indicate unknown/unconfigured device."
                        )
                    return True

            except PlaywrightError as exc:
                # Log and continue polling until timeout
                print(f"[WARN] Error while polling logs: {exc}")

            await asyncio.sleep(log_poll_interval_seconds)

        return False

    # -------------------------------------------------------------------------
    # Step 1: Verify via Profiler UI that 10.10.30.30 is not present
    #         in the SNMP device list.
    # -------------------------------------------------------------------------
    try:
        # Navigate to SNMP devices configuration page
        # Adjust navigation as appropriate for your application
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/snmp_devices.cgi"
        )

        # If there is a search/filter for SNMP devices, use it
        snmp_search_input = page.locator("input[name='snmpDeviceSearch']")
        if await snmp_search_input.is_visible():
            await snmp_search_input.fill(unknown_switch_ip)
            await snmp_search_input.press("Enter")
            await page.wait_for_timeout(2000)

        # Locate the SNMP devices table and check that the IP is not present
        snmp_table_rows = page.locator("table#snmpDevicesTable tr")
        row_count = await snmp_table_rows.count()

        device_found = False
        for row_index in range(row_count):
            row_text = await snmp_table_rows.nth(row_index).inner_text()
            if unknown_switch_ip in row_text:
                device_found = True
                break

        assert device_found is False, (
            f"Switch {unknown_switch_ip} is present in SNMP devices list, "
            "but test requires it to be absent."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed while verifying SNMP device list: {exc!r}")

    # -------------------------------------------------------------------------
    # Step 2: Configure switch 10.10.30.30 to send traps to Profiler IP.
    # NOTE: This is assumed to be done externally (via CLI / automation).
    #       Here we only document and optionally log the step.
    # -------------------------------------------------------------------------
    print(
        "[INFO] Ensure switch 10.10.30.30 is configured to send "
        "linkUp/linkDown traps to Profiler IP (external step)."
    )

    # -------------------------------------------------------------------------
    # Step 3: Connect endpoint 11:22:33:44:55:66 to switch port Gi1/0/10.
    # NOTE: Also assumed to be done externally. We log the step here.
    # -------------------------------------------------------------------------
    print(
        "[INFO] Connect endpoint 11:22:33:44:55:66 to switch port Gi1/0/10 "
        "to generate linkUp trap (external step)."
    )

    # -------------------------------------------------------------------------
    # Step 4: Confirm via packet capture that trap reaches Profiler.
    # NOTE: External network validation. We cannot verify pcap from UI
    #       unless your system exposes it. We assume this is validated
    #       as part of environment setup.
    # -------------------------------------------------------------------------
    print(
        "[INFO] Confirm via packet capture that SNMP trap from 10.10.30.30 "
        "reaches Profiler (external verification)."
    )

    # -------------------------------------------------------------------------
    # Step 5: After 2 minutes, search for MAC 11:22:33:44:55:66 in Profiler.
    # -------------------------------------------------------------------------
    print(
        f"[INFO] Waiting {wait_for_trap_seconds} seconds for Profiler "
        "to process incoming trap."
    )
    await page.wait_for_timeout(wait_for_trap_seconds * 1000)

    try:
        # Navigate to endpoint / inventory page
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/endpoints.cgi"
        )

        # Search for the MAC address
        endpoint_search_input = page.locator("input[name='endpointSearch']")
        assert await endpoint_search_input.is_visible(), (
            "Endpoint search input not visible; cannot verify inventory."
        )

        await endpoint_search_input.fill(endpoint_mac)
        await endpoint_search_input.press("Enter")

        # Wait for results to refresh
        await page.wait_for_timeout(3000)

        # Check if any endpoint row with this MAC exists
        endpoint_rows = page.locator("table#endpointsTable tr")
        endpoint_row_count = await endpoint_rows.count()

        endpoint_found = False
        for row_index in range(endpoint_row_count):
            row_text = await endpoint_rows.nth(row_index).inner_text()
            if endpoint_mac.lower() in row_text.lower():
                endpoint_found = True
                break

        # Expected: No new endpoint created based solely on trap
        assert endpoint_found is False, (
            "Endpoint with MAC "
            f"{endpoint_mac} was found in inventory, but it should not be "
            "created based solely on a trap from an unknown device."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed while verifying endpoint inventory: {exc!r}")

    # -------------------------------------------------------------------------
    # Additional Expected Behavior:
    #  - Profiler logs should contain a clear message about trap from unknown
    #    SNMP device 10.10.30.30.
    #  - No errors/exceptions indicating crash or unhandled exception.
    # -------------------------------------------------------------------------
    try:
        log_message_found = await wait_for_unknown_device_log()
        assert log_message_found, (
            "Did not find a log entry indicating that a trap from unknown/"
            f"unconfigured device {unknown_switch_ip} was received. "
            "Ensure logging is enabled and selectors/text are correct."
        )

        # Optional: also verify that there are no critical/unhandled exceptions
        # in the logs around the same time. This assumes a log severity column.
        # Adjust selectors and text as appropriate.
        critical_logs = page.locator(
            "table#logsTable tr",
            has_text="critical",
        )
        assert await critical_logs.count() == 0, (
            "Critical/unhandled exception logs detected after receiving trap "
            "from unknown device."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed while verifying logs for unknown device trap: {exc!r}")