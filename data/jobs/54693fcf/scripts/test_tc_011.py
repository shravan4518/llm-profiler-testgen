import asyncio
from datetime import datetime, timedelta
from typing import List

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_011_minimum_empty_snmp_trap_configuration(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_011: Verify minimum/empty SNMP trap configuration (no devices configured)

    Title:
        Verify minimum/empty SNMP trap configuration (no devices configured)

    Category:
        boundary

    Priority:
        Low

    Description:
        Validates Profiler behavior when no SNMP devices are configured while the
        trap listener is enabled, ensuring no errors when receiving stray traps.

    Preconditions:
        - Fresh Profiler deployment with zero SNMP devices configured.
        - User is authenticated and on the Profiler admin UI.

    Steps:
        1. Confirm in Profiler UI that no SNMP devices are configured in
           Network Infrastructure Device Collector.
        2. Confirm SNMP trap listener is enabled by default (if configurable).
        3. Send a valid linkUp trap from switch `10.10.40.40` to Profiler IP.
        4. Monitor Profiler logs and UI for any errors or new endpoints.

    Expected Results:
        - Profiler receives the trap but does not create endpoint or device
          entries (unless design says auto-add devices).
        - No errors or warnings about missing configuration beyond an
          informational log message.
        - Profiler remains stable.
        - Inventory unchanged; logs may contain an informational message about
          trap from unconfigured source.

    Notes:
        - This test assumes that:
          * The UI has identifiable selectors for:
            - Network Infrastructure Device Collector list
            - SNMP trap listener configuration
            - Endpoint/device inventory
            - System/log viewer
          * An external helper or fixture is available to send SNMP traps.
        - Where such selectors or helpers are not known, this test uses
          placeholder selectors and a stubbed trap-sending function that should
          be replaced with environment-specific implementations.
    """

    page: Page = authenticated_page

    # ----------------------------------------------------------------------
    # Helper functions (UI-level, no direct system access)
    # ----------------------------------------------------------------------

    async def wait_for_stable_ui(page: Page, timeout_ms: int = 10_000) -> None:
        """Wait for network to be idle and main UI to be stable."""
        try:
            await page.wait_for_load_state("networkidle", timeout=timeout_ms)
        except PlaywrightError:
            # Not fatal; continue with best-effort stability
            pass

    async def navigate_to_network_infrastructure_collector(page: Page) -> None:
        """
        Navigate to the Network Infrastructure Device Collector configuration
        page in the Profiler UI.

        NOTE: Replace selectors with real navigation paths.
        """
        try:
            # Example navigation via menu; selectors are placeholders
            await page.click("text=Configuration")
            await page.click("text=Network Infrastructure")
            await page.click("text=Device Collector")
            await wait_for_stable_ui(page)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to Network Infrastructure "
                        f"Device Collector page: {exc}")

    async def get_configured_snmp_devices(page: Page) -> List[str]:
        """
        Return a list of configured SNMP device identifiers (e.g., IPs or names).

        NOTE: Replace selectors with actual table/list locators.
        """
        try:
            # Example: table rows in a collector devices grid
            rows = await page.locator(
                "table#collector-devices-table tbody tr"
            ).all()
            device_ids: List[str] = []
            for row in rows:
                # Example: first column contains device IP/name
                cell = row.locator("td").first
                text = (await cell.text_content() or "").strip()
                if text:
                    device_ids.append(text)
            return device_ids
        except PlaywrightError as exc:
            pytest.fail(f"Failed to read SNMP devices from UI: {exc}")
            return []

    async def navigate_to_snmp_trap_listener_settings(page: Page) -> None:
        """
        Navigate to SNMP trap listener configuration page.

        NOTE: Replace selectors with real navigation paths.
        """
        try:
            await page.click("text=Configuration")
            await page.click("text=SNMP")
            await page.click("text=Trap Listener")
            await wait_for_stable_ui(page)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to SNMP trap listener settings: {exc}")

    async def is_trap_listener_enabled(page: Page) -> bool:
        """
        Check whether the SNMP trap listener is enabled.

        NOTE: Replace selector with the actual toggle/checkbox for the listener.
        """
        try:
            # Example: a checkbox or toggle for enabling trap listener
            toggle = page.locator("input#snmp-trap-listener-enabled")
            if not await toggle.is_visible():
                pytest.fail("SNMP trap listener enable control not visible")
            return await toggle.is_checked()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to check SNMP trap listener state: {exc}")
            return False

    async def navigate_to_inventory_page(page: Page) -> None:
        """
        Navigate to the main inventory/endpoints page.

        NOTE: Replace with real navigation path.
        """
        try:
            await page.click("text=Inventory")
            await page.click("text=Endpoints")
            await wait_for_stable_ui(page)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to Inventory/Endpoints page: {exc}")

    async def get_endpoint_count(page: Page) -> int:
        """
        Return the total number of endpoints currently displayed.

        NOTE: Replace selector logic with real pagination/summary controls.
        """
        try:
            # Example: a counter label "Total: X"
            counter = page.locator("span#endpoint-total-count")
            if await counter.is_visible():
                text = await counter.text_content()
                if text:
                    # Extract integer from text like "Total: 12"
                    digits = "".join(ch for ch in text if ch.isdigit())
                    return int(digits) if digits else 0

            # Fallback: count rows in a table
            rows = await page.locator("table#endpoint-table tbody tr").all()
            return len(rows)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to read endpoint count from UI: {exc}")
            return 0

    async def navigate_to_system_logs(page: Page) -> None:
        """
        Navigate to the system/log viewer page.

        NOTE: Replace with real navigation path.
        """
        try:
            await page.click("text=Monitoring")
            await page.click("text=System Logs")
            await wait_for_stable_ui(page)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to System Logs: {exc}")

    async def get_recent_log_entries(page: Page, lookback_minutes: int = 5) -> List[str]:
        """
        Return recent log entries as a list of strings.

        NOTE: Replace selectors and parsing with actual log table or viewer.
        """
        try:
            # Example: ensure the log view is set to a recent time window
            # This is a placeholder; adapt to your UI's filtering controls.
            now = datetime.utcnow()
            start_time = now - timedelta(minutes=lookback_minutes)

            # Example: apply a time filter if available (placeholder selectors)
            if await page.locator("input#log-filter-start-time").is_visible():
                await page.fill("input#log-filter-start-time", start_time.strftime("%Y-%m-%d %H:%M"))
                await page.fill("input#log-filter-end-time", now.strftime("%Y-%m-%d %H:%M"))
                await page.click("button#log-filter-apply")
                await wait_for_stable_ui(page)

            # Collect log lines from a table
            rows = await page.locator("table#system-log-table tbody tr").all()
            entries: List[str] = []
            for row in rows:
                text = (await row.text_content() or "").strip()
                if text:
                    entries.append(text)
            return entries
        except PlaywrightError as exc:
            pytest.fail(f"Failed to read system logs from UI: {exc}")
            return []

    async def send_linkup_trap_from_switch(
        source_ip: str,
        profiler_ip: str,
        snmp_community: str = "public",
    ) -> None:
        """
        Send a valid SNMP linkUp trap from the given source IP to the Profiler IP.

        This is a stub that should be replaced with environment-specific logic
        (e.g., calling a helper service, executing a CLI command, or invoking
        a REST API that triggers a trap).

        For safety and determinism, this function does not actually send a trap.
        Replace its body with the real implementation in your environment.
        """
        # TODO: Replace with real trap-sending logic (e.g., via external helper).
        # Example (conceptual, not executed here):
        #   await some_helper.send_trap(
        #       source_ip=source_ip,
        #       target_ip=profiler_ip,
        #       trap_oid="1.3.6.1.6.3.1.1.5.4",  # linkUp
        #       community=snmp_community,
        #   )
        await asyncio.sleep(1)  # Simulate call latency

    # ----------------------------------------------------------------------
    # Step 1: Confirm no SNMP devices are configured in Device Collector
    # ----------------------------------------------------------------------
    await navigate_to_network_infrastructure_collector(page)
    configured_devices = await get_configured_snmp_devices(page)

    # Boundary condition: expect zero devices in a fresh deployment
    assert (
        len(configured_devices) == 0
    ), f"Expected zero SNMP devices, found: {configured_devices}"

    # ----------------------------------------------------------------------
    # Step 2: Confirm SNMP trap listener is enabled by default (if configurable)
    # ----------------------------------------------------------------------
    await navigate_to_snmp_trap_listener_settings(page)
    trap_listener_enabled = await is_trap_listener_enabled(page)

    # If the listener is configurable, it should be enabled by default.
    # If design allows disabled-by-default, adjust this assertion accordingly.
    assert trap_listener_enabled is True, (
        "SNMP trap listener is not enabled by default. "
        "Update test expectations if this is the intended design."
    )

    # ----------------------------------------------------------------------
    # Step 3: Capture baseline inventory, then send linkUp trap
    # ----------------------------------------------------------------------
    await navigate_to_inventory_page(page)
    baseline_endpoint_count = await get_endpoint_count(page)

    # Capture baseline logs before sending trap
    await navigate_to_system_logs(page)
    baseline_logs = await get_recent_log_entries(page, lookback_minutes=10)
    baseline_log_set = set(baseline_logs)

    # Send a valid linkUp trap from switch 10.10.40.40 to Profiler IP
    # NOTE: Replace "10.34.50.201" with actual Profiler IP if different from UI URL.
    switch_ip = "10.10.40.40"
    profiler_ip = "10.34.50.201"

    await send_linkup_trap_from_switch(
        source_ip=switch_ip,
        profiler_ip=profiler_ip,
        snmp_community="public",
    )

    # Allow time for trap processing
    await asyncio.sleep(10)

    # ----------------------------------------------------------------------
    # Step 4: Verify no new endpoints/devices and no error logs
    # ----------------------------------------------------------------------
    # 4a. Verify inventory remains unchanged (no new endpoints created)
    await navigate_to_inventory_page(page)
    post_trap_endpoint_count = await get_endpoint_count(page)

    assert (
        post_trap_endpoint_count == baseline_endpoint_count
    ), (
        "Endpoint inventory changed after receiving a trap from an "
        "unconfigured device. "
        f"Before: {baseline_endpoint_count}, After: {post_trap_endpoint_count}"
    )

    # 4b. Verify logs contain no errors/warnings related to missing configuration
    await navigate_to_system_logs(page)
    post_trap_logs = await get_recent_log_entries(page, lookback_minutes=10)

    new_log_entries = [l for l in post_trap_logs if l not in baseline_log_set]

    # Define patterns that would indicate problematic behavior
    error_keywords = [
        "ERROR",
        "Exception",
        "Traceback",
        "failed to process trap",
        "missing configuration",
        "unhandled trap",
    ]
    warning_keywords = [
        "WARNING",
        "WARN",
        "no matching device configuration",
    ]

    # Detect error/warning entries
    error_entries = [
        entry
        for entry in new_log_entries
        if any(keyword.lower() in entry.lower() for keyword in error_keywords)
    ]
    warning_entries = [
        entry
        for entry in new_log_entries
        if any(keyword.lower() in entry.lower() for keyword in warning_keywords)
    ]

    # It is acceptable to have an informational message about trap from
    # unconfigured source; errors and warnings should not appear.
    assert not error_entries, (
        "Unexpected error log entries after receiving trap from unconfigured "
        f"device:\n" + "\n".join(error_entries)
    )

    # Depending on product design, warnings may or may not be acceptable.
    # Here we enforce that there should be no warnings either, beyond purely
    # informational messages.
    assert not warning_entries, (
        "Unexpected warning log entries after receiving trap from unconfigured "
        f"device:\n" + "\n".join(warning_entries)
    )

    # ----------------------------------------------------------------------
    # Final sanity: Profiler UI remains responsive/stable
    # ----------------------------------------------------------------------
    try:
        # Basic sanity check: can still navigate somewhere and back
        await navigate_to_network_infrastructure_collector(page)
        await navigate_to_inventory_page(page)
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001
        pytest.fail(
            "Profiler UI appears unstable or unresponsive after processing "
            f"trap from unconfigured device: {exc}"
        )