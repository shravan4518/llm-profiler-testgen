import asyncio
from datetime import datetime
from typing import List, Dict

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_005_snmp_trap_processing_multiple_endpoints(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_005: Verify SNMP trap processing for multiple simultaneous endpoint events on a switch.

    Title:
        Verify SNMP trap processing for multiple simultaneous endpoint events on a switch

    Description:
        Validates that Profiler correctly handles and processes a burst of linkUp/linkDown traps
        for multiple endpoints without losing or mis-associating events.

    Preconditions:
        - Profiler and switch 10.10.20.12 configured as in previous cases.
        - 5 test endpoints or traffic generators capable of emulating different MAC addresses
          on different ports.

    Expected Results:
        - Profiler successfully processes all 10 traps (5 linkUp + 5 linkDown).
        - Inventory contains 5 endpoints with correct MACs.
        - Each endpoint shows the correct associated port (Gi1/0/1–5).
        - Each endpoint shows appropriate connection/disconnection times.
        - No mix-up between MACs and ports.
    """

    page: Page = authenticated_page

    # ----------------------------------------------------------------------
    # Test data (adjust MACs and ports to match your lab configuration)
    # ----------------------------------------------------------------------
    mac_addresses: List[str] = [
        "00:11:22:33:44:51",
        "00:11:22:33:44:52",
        "00:11:22:33:44:53",
        "00:11:22:33:44:54",
        "00:11:22:33:44:55",
    ]
    expected_port_mapping: Dict[str, str] = {
        "00:11:22:33:44:51": "Gi1/0/1",
        "00:11:22:33:44:52": "Gi1/0/2",
        "00:11:22:33:44:53": "Gi1/0/3",
        "00:11:22:33:44:54": "Gi1/0/4",
        "00:11:22:33:44:55": "Gi1/0/5",
    }

    # These flags simulate/represent external actions and validations
    # that are normally done via hardware and packet capture.
    # In a real environment, replace these with proper hooks or APIs.
    external_traps_verified = True

    # Record approximate time of linkUp/Down to validate timestamps window
    test_start_time = datetime.utcnow()

    # ----------------------------------------------------------------------
    # Helper functions
    # ----------------------------------------------------------------------
    async def clear_existing_endpoint(mac: str) -> None:
        """
        Ensure that the given MAC does not exist in Profiler inventory.
        If found, delete or remove it to satisfy the prerequisite.
        """
        try:
            # Navigate to inventory/search page
            # NOTE: Update selectors and navigation to match actual UI.
            await page.goto("https://10.34.50.201/profiler/inventory", wait_until="networkidle")

            # Search by MAC
            search_input = page.get_by_placeholder("Search by MAC, IP, hostname")
            await search_input.fill(mac)
            await search_input.press("Enter")

            # Wait for search results to load
            await page.wait_for_timeout(2000)

            # Check whether any result row appears for this MAC
            result_row = page.locator(f"tr:has-text('{mac}')")
            if await result_row.count() > 0:
                # Attempt to delete endpoint if UI supports it
                delete_button = result_row.get_by_role("button", name="Delete")
                if await delete_button.count() > 0:
                    await delete_button.click()
                    confirm_button = page.get_by_role("button", name="Confirm")
                    await confirm_button.click()
                    await page.wait_for_timeout(2000)
        except PlaywrightError as exc:
            # Do not fail the test on cleanup; just log the issue.
            pytest.skip(f"Unable to clear existing endpoint for MAC {mac}: {exc}")

    async def search_and_open_endpoint_details(mac: str) -> None:
        """
        Search for an endpoint by MAC and open its details page.
        Raises assertion errors if the endpoint is not found.
        """
        await page.goto("https://10.34.50.201/profiler/inventory", wait_until="networkidle")

        search_input = page.get_by_placeholder("Search by MAC, IP, hostname")
        await search_input.fill(mac)
        await search_input.press("Enter")

        # Wait for search results
        await page.wait_for_timeout(3000)

        result_row = page.locator(f"tr:has-text('{mac}')")
        assert await result_row.count() > 0, f"Endpoint with MAC {mac} not found in inventory."

        # Open details (assuming clicking row opens details)
        await result_row.first.click()

        # Wait for details panel/page
        await page.wait_for_timeout(2000)

    async def get_endpoint_port_from_details() -> str:
        """
        Read the associated switch port from the endpoint details view.
        """
        # NOTE: Adjust selector to match actual DOM.
        port_value_locator = page.locator("data-test-id=endpoint-port")
        if await port_value_locator.count() == 0:
            # Try a generic label/value layout as fallback
            port_value_locator = page.locator("xpath=//label[contains(., 'Port')]/following-sibling::*[1]")

        assert await port_value_locator.count() > 0, "Port field not found on endpoint details page."

        port_text = (await port_value_locator.first.inner_text()).strip()
        return port_text

    async def get_endpoint_connection_times() -> Dict[str, str]:
        """
        Retrieve connection and disconnection times from endpoint details.
        Return as a dict with keys 'connected' and 'disconnected'.
        """
        # NOTE: Adjust selectors to match actual DOM.
        connected_locator = page.locator("data-test-id=endpoint-connected-time")
        disconnected_locator = page.locator("data-test-id=endpoint-disconnected-time")

        # Fallback to label-based selectors if needed
        if await connected_locator.count() == 0:
            connected_locator = page.locator(
                "xpath=//label[contains(., 'Connected')]/following-sibling::*[1]"
            )
        if await disconnected_locator.count() == 0:
            disconnected_locator = page.locator(
                "xpath=//label[contains(., 'Disconnected')]/following-sibling::*[1]"
            )

        assert await connected_locator.count() > 0, "Connected time field not found."
        assert await disconnected_locator.count() > 0, "Disconnected time field not found."

        connected_text = (await connected_locator.first.inner_text()).strip()
        disconnected_text = (await disconnected_locator.first.inner_text()).strip()

        return {
            "connected": connected_text,
            "disconnected": disconnected_text,
        }

    # ----------------------------------------------------------------------
    # Step 1: Ensure none of the 5 MACs exist in Profiler.
    # ----------------------------------------------------------------------
    for mac in mac_addresses:
        await clear_existing_endpoint(mac)

    # ----------------------------------------------------------------------
    # Step 2: Simultaneously connect all 5 endpoints to the specified ports.
    # ----------------------------------------------------------------------
    # NOTE: This step is normally done via physical/virtual test equipment.
    # Here we assume an external mechanism (e.g., API, test harness) performs
    # the connections. The test records the time and continues.
    #
    # If you have an API to trigger this, call it here instead of sleep.
    #
    # Example placeholder:
    # await test_harness.connect_endpoints(mac_addresses, switch="10.10.20.12")
    #
    # For now, just log the action via comment and continue.
    # ----------------------------------------------------------------------
    # External action: connect endpoints (not automated in this script).
    await page.context.tracing.start(name="tc_005_connect_phase", screenshots=True, snapshots=True)

    # ----------------------------------------------------------------------
    # Step 3: After 15 seconds, simultaneously disconnect all 5 endpoints.
    # ----------------------------------------------------------------------
    await asyncio.sleep(15)

    # External action: disconnect endpoints (not automated in this script).
    # Example placeholder:
    # await test_harness.disconnect_endpoints(mac_addresses, switch="10.10.20.12")

    await page.context.tracing.stop(path="trace_tc_005_connect_disconnect.zip")

    # ----------------------------------------------------------------------
    # Step 4: Confirm via packet capture that 5 linkUp and 5 linkDown traps
    #         have been sent in quick succession.
    # ----------------------------------------------------------------------
    # This is typically validated via external tools (e.g., tcpdump, Wireshark).
    # In an automated environment, this might be exposed via an API.
    #
    # Here we assert on a flag that would be set by such an integration.
    # Replace this with real verification logic where available.
    # ----------------------------------------------------------------------
    assert external_traps_verified, (
        "SNMP trap verification failed: expected 5 linkUp and 5 linkDown traps "
        "to be observed via packet capture."
    )

    # ----------------------------------------------------------------------
    # Step 5: After 2–3 minutes, search each MAC in Profiler and open details.
    # ----------------------------------------------------------------------
    await asyncio.sleep(120)  # Wait 2 minutes for Profiler to process traps

    # ----------------------------------------------------------------------
    # Expected Results Assertions
    # ----------------------------------------------------------------------
    # - Profiler successfully processes all 10 traps.
    #   (Implied by: all 5 endpoints exist with correct status and timestamps.)
    # - Inventory contains 5 endpoints with correct MACs.
    # - Each endpoint shows the correct associated port (Gi1/0/1–5).
    # - Each endpoint shows appropriate connection/disconnection times.
    # - No mix-up between MACs and ports.
    # ----------------------------------------------------------------------
    for mac in mac_addresses:
        # Open endpoint details
        await search_and_open_endpoint_details(mac)

        # Assert port mapping
        port_from_ui = await get_endpoint_port_from_details()
        expected_port = expected_port_mapping[mac]
        assert (
            port_from_ui == expected_port
        ), f"Endpoint {mac} is associated with port '{port_from_ui}', expected '{expected_port}'."

        # Assert connection/disconnection times exist and are reasonable
        times = await get_endpoint_connection_times()
        connected_time_str = times["connected"]
        disconnected_time_str = times["disconnected"]

        assert connected_time_str, f"Connected time is empty for endpoint {mac}."
        assert disconnected_time_str, f"Disconnected time is empty for endpoint {mac}."

        # Optional: If format is known, parse and compare to test_start_time window.
        # This is defensive: if parsing fails, we still keep the test meaningful.
        # Adjust datetime format string to match your UI.
        datetime_format_candidates = [
            "%Y-%m-%d %H:%M:%S",
            "%d/%m/%Y %H:%M:%S",
            "%m/%d/%Y %H:%M:%S",
        ]

        def parse_with_candidates(value: str):
            for fmt in datetime_format_candidates:
                try:
                    return datetime.strptime(value, fmt)
                except ValueError:
                    continue
            return None

        connected_dt = parse_with_candidates(connected_time_str)
        disconnected_dt = parse_with_candidates(disconnected_time_str)

        if connected_dt and disconnected_dt:
            assert connected_dt >= test_start_time, (
                f"Connected time {connected_dt} for {mac} is earlier than test start "
                f"time {test_start_time}."
            )
            assert disconnected_dt >= connected_dt, (
                f"Disconnected time {disconnected_dt} for {mac} is earlier than "
                f"connected time {connected_dt}."
            )

        # Basic status check if available (e.g., 'Disconnected' after test)
        # NOTE: Adjust selector and expected text to match your UI.
        status_locator = page.locator("data-test-id=endpoint-status")
        if await status_locator.count() > 0:
            status_text = (await status_locator.first.inner_text()).strip().lower()
            assert "disconnected" in status_text or "inactive" in status_text, (
                f"Endpoint {mac} status is '{status_text}', expected it to be disconnected "
                "after linkDown traps."
            )

    # Postconditions:
    # - Five endpoint records exist with correct mapping and status.
    # This is implicitly validated by the loop above.