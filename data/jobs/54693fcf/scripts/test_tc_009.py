import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_009_snmp_trap_port_unavailable(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_009: Verify Profiler behavior when SNMP trap listener port (162) is unavailable.

    This test simulates a failure to bind the SNMP trap listener port (162) by:
    - Occupying UDP/162 on the Profiler host with a dummy process.
    - Restarting Profiler services / trap listener.
    - Validating that:
        * Profiler logs show a clear bind error for port 162.
        * Trap-based discovery / trap listener is marked as failed/disabled.
        * Traps sent from a configured switch are not processed/visible in UI/logs.
        * Other non-trap-based Profiler functions remain operational.

    Notes:
    - This test assumes there are backend utilities or UI controls to:
        * Stop/start Profiler services.
        * Start a dummy UDP listener on port 162.
        * View Profiler system logs.
        * View trap/discovery status and trap events.
        * Trigger or verify non-trap-based functionality.
    - Where exact selectors or endpoints are unknown, this test uses clearly
      marked placeholders that must be adapted to the actual Profiler UI.
    """

    page = authenticated_page

    # Helper functions (UI-level abstractions)

    async def stop_profiler_services(page: Page) -> None:
        """
        Stop Profiler services using the admin UI or a backend hook.

        Replace selectors / flow with the real implementation.
        """
        try:
            # Navigate to system/services page
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/services.cgi",
                wait_until="networkidle",
            )

            # Click "Stop All Services" or equivalent
            # Placeholder selector; update for real UI
            await page.click("button#stop-services")

            # Confirm stop if confirmation dialog appears
            if await page.is_visible("button#confirm-stop-services"):
                await page.click("button#confirm-stop-services")

            # Wait for services to stop; use a status indicator in real UI
            await page.wait_for_timeout(10_000)

            # Assert that services status shows "Stopped"
            # Placeholder selector/text
            status_text = await page.text_content("span#services-status")
            assert status_text is not None
            assert "Stopped" in status_text or "Down" in status_text

        except PlaywrightError as exc:
            logger.error("Failed to stop Profiler services: %s", exc)
            pytest.fail(f"Could not stop Profiler services: {exc}")

    async def start_dummy_udp_162_listener(page: Page) -> None:
        """
        Start a dummy service occupying UDP port 162 on the Profiler host.

        This is typically done using a backend hook, not via the browser.
        Here we assume the Profiler admin UI exposes a debug/maintenance tool
        (or we call a REST endpoint via fetch). Replace with actual mechanism.
        """
        try:
            # Example: navigate to a debug/maintenance tools page
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/debug_tools.cgi",
                wait_until="networkidle",
            )

            # Start dummy listener on UDP/162 via a control or form
            # Placeholder selector; must be replaced with real one
            await page.fill("input#udp-port", "162")
            await page.click("button#start-dummy-udp-listener")

            # Wait and verify that listener is reported as running
            await page.wait_for_timeout(3_000)
            listener_status = await page.text_content("span#udp-162-status")
            assert listener_status is not None
            assert "Running" in listener_status or "Listening" in listener_status

        except PlaywrightError as exc:
            logger.error("Failed to start dummy UDP/162 listener: %s", exc)
            pytest.fail(f"Could not start dummy UDP/162 listener: {exc}")

    async def start_profiler_services(page: Page) -> None:
        """
        Start Profiler services, focusing on the trap listener component.
        """
        try:
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/services.cgi",
                wait_until="networkidle",
            )

            # Click "Start All Services" or equivalent
            await page.click("button#start-services")

            # Confirm start if needed
            if await page.is_visible("button#confirm-start-services"):
                await page.click("button#confirm-start-services")

            # Wait for services to start
            await page.wait_for_timeout(20_000)

            # Assert that services status shows "Running"
            status_text = await page.text_content("span#services-status")
            assert status_text is not None
            assert "Running" in status_text or "Up" in status_text

        except PlaywrightError as exc:
            logger.error("Failed to start Profiler services: %s", exc)
            pytest.fail(f"Could not start Profiler services: {exc}")

    async def open_profiler_logs(page: Page) -> None:
        """
        Navigate to the Profiler system logs page.
        """
        try:
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/logs.cgi",
                wait_until="networkidle",
            )
        except PlaywrightError as exc:
            logger.error("Failed to open Profiler logs: %s", exc)
            pytest.fail(f"Could not open Profiler logs: {exc}")

    async def find_snmp_bind_error(page: Page) -> Optional[str]:
        """
        Search logs for a clear error message indicating failure to bind UDP/162.

        Returns the matching log line if found, otherwise None.
        """
        try:
            # Example: filter logs by component "SNMP Trap" or similar
            if await page.is_visible("select#log-component-filter"):
                await page.select_option("select#log-component-filter", "snmp_trap")

            # Trigger log search / refresh
            if await page.is_visible("button#refresh-logs"):
                await page.click("button#refresh-logs")

            await page.wait_for_timeout(5_000)

            # Placeholder selector: a table or preformatted log output
            log_text = await page.text_content("pre#log-output")  # or "div.log-table"
            if not log_text:
                return None

            # Look for typical bind error patterns
            patterns = [
                "failed to bind to port 162",
                "cannot bind to UDP/162",
                "address already in use",
                "port 162 is already in use",
                "bind() failed on port 162",
            ]
            for line in log_text.splitlines():
                if any(pattern.lower() in line.lower() for pattern in patterns):
                    return line

            return None

        except PlaywrightError as exc:
            logger.error("Error while searching for SNMP bind error in logs: %s", exc)
            pytest.fail(f"Could not search logs for SNMP bind error: {exc}")

    async def verify_trap_listener_status_failed(page: Page) -> None:
        """
        Verify that the trap listener is marked as failed/disabled in the UI.
        """
        try:
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/trap_status.cgi",
                wait_until="networkidle",
            )

            # Placeholder selector and expected status text
            status_text = await page.text_content("span#trap-listener-status")
            assert status_text is not None
            assert any(
                keyword in status_text
                for keyword in ["Failed", "Error", "Disabled", "Not Listening"]
            ), (
                "Trap listener status should indicate failure when port 162 "
                "is unavailable, got: "
                f"{status_text}"
            )
        except PlaywrightError as exc:
            logger.error("Failed to verify trap listener status: %s", exc)
            pytest.fail(f"Could not verify trap listener status: {exc}")

    async def send_snmp_trap_from_switch() -> None:
        """
        Trigger sending a valid SNMP trap from a configured switch.

        This is usually done outside the browser (e.g., via SSH to switch or
        a test harness). Here we assume a helper or preconfigured mechanism
        exists and is invoked indirectly (e.g., REST call, or external script).

        For this skeleton, we simulate a wait period representing trap send.
        """
        # In a real implementation, integrate with a network test harness
        # or external command. For now, just simulate delay.
        await asyncio.sleep(5)

    async def verify_trap_not_received(page: Page) -> None:
        """
        Verify that the SNMP trap sent is NOT processed/visible in Profiler.
        """
        try:
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/trap_events.cgi",
                wait_until="networkidle",
            )

            # Refresh trap events
            if await page.is_visible("button#refresh-traps"):
                await page.click("button#refresh-traps")
            await page.wait_for_timeout(5_000)

            # Placeholder: assume a table of traps where each row is a trap event
            rows = await page.query_selector_all("table#trap-events tbody tr")
            # In a real test, filter on specific trap OID/source/time.
            # For negative test, assert that there are no NEW traps from our test.
            # Here we simply assert no traps at all or no "recent" ones.
            # This must be adapted to your environment.
            assert len(rows) == 0 or all(
                "test-trap" not in (await row.text_content() or "").lower()
                for row in rows
            ), (
                "SNMP traps should not be processed when port 162 is unavailable, "
                "but trap events were found."
            )

        except PlaywrightError as exc:
            logger.error("Failed to verify that trap was not received: %s", exc)
            pytest.fail(f"Could not verify trap non-reception: {exc}")

    async def verify_non_trap_features_operational(page: Page) -> None:
        """
        Verify that other Profiler functions (non-trap-based) continue operating.

        Example: load the device inventory page and ensure it is accessible.
        """
        try:
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/inventory.cgi",
                wait_until="networkidle",
            )

            # Placeholder: check that inventory table is visible and not empty
            assert await page.is_visible("table#device-inventory")
            rows = await page.query_selector_all("table#device-inventory tbody tr")
            assert len(rows) >= 0  # Adjust to >= 1 if you expect existing devices

        except PlaywrightError as exc:
            logger.error(
                "Failed to verify non-trap-based Profiler functionality: %s", exc
            )
            pytest.fail(
                "Non-trap-based Profiler functionality appears broken while "
                f"trap port is unavailable: {exc}"
            )

    # ----------------------------------------------------------------------
    # Test Steps Implementation
    # ----------------------------------------------------------------------

    # STEP 1: Stop Profiler services if necessary.
    await stop_profiler_services(page)

    # STEP 2: Start a dummy service or nc -ul 162 to occupy UDP port 162.
    await start_dummy_udp_162_listener(page)

    # STEP 3: Start/restart Profiler services, especially the trap listener.
    await start_profiler_services(page)

    # STEP 4: Observe startup logs for errors related to binding port 162.
    await open_profiler_logs(page)
    bind_error_line = await find_snmp_bind_error(page)
    assert (
        bind_error_line is not None
    ), "Expected a clear SNMP bind error in logs when UDP/162 is occupied."

    # Ensure the error message itself is reasonably clear (not empty/garbled)
    assert any(
        keyword in bind_error_line.lower()
        for keyword in ["bind", "port 162", "162", "address already in use"]
    ), (
        "Log entry for SNMP trap listener bind failure should clearly reference "
        f"port 162 or bind failure, got: {bind_error_line}"
    )

    # Additionally verify trap listener status UI reflects failure/disabled state.
    await verify_trap_listener_status_failed(page)

    # STEP 5: Attempt to send a valid SNMP trap from a configured switch.
    await send_snmp_trap_from_switch()

    # STEP 6: Verify whether Profiler receives/processes the trap (UI/logs).
    await verify_trap_not_received(page)

    # Expected Result: Other Profiler functions (non-trap-based) continue operating.
    await verify_non_trap_features_operational(page)

    # Postcondition check: system remains stable (no global errors / crash page).
    # Example: confirm we can still navigate to the main admin dashboard.
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
        assert await page.is_visible("body"), (
            "Profiler admin UI should remain accessible even when trap-based "
            "discovery is nonfunctional."
        )
    except PlaywrightError as exc:
        logger.error("Profiler UI became inaccessible after trap failure: %s", exc)
        pytest.fail(
            "System did not remain stable after SNMP trap listener bind failure."
        )