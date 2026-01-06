import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_004_snmp_trap_based_discovery_short_lived_endpoint(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_004: Verify SNMP trap-based discovery of endpoints connected briefly to the switch.

    Description:
        Ensures Profiler can detect endpoints that connect to a switch for a very short
        duration using linkUp/linkDown trap-based discovery, even without periodic SNMP
        polling in between.

    Preconditions (assumed configured outside this test):
        - Profiler configured for SNMP trap-based discovery for switch 10.10.20.11.
        - Switch configured to send linkUp/linkDown traps.
        - Polling interval for SNMP device collector set to a high value (e.g., 60 minutes).

    Steps:
        1. Confirm Profiler shows no endpoint with MAC 00:AA:00:AA:00:AA.
        2. Connect the endpoint to switch port Gi1/0/20. (performed externally)
        3. Wait until the interface goes up (verify on switch). (performed externally)
        4. After 10 seconds, disconnect the endpoint. (performed externally)
        5. Capture SNMP traps to ensure both linkUp and linkDown traps were sent.
           (validated here only via Profiler UI evidence)
        6. After 1–2 minutes, search for MAC 00:AA:00:AA:00:AA in Profiler.

    Expected Results:
        - Profiler receives linkUp and linkDown traps despite the short connection duration.
        - A new endpoint for MAC 00:AA:00:AA:00:AA is created.
        - Endpoint is visible in inventory, likely with disconnected status but with accurate
          last seen time and port Gi1/0/20.
        - Endpoint would not have been discoverable via polling alone due to the long polling
          interval.
        - Endpoint discovery source includes SNMP traps.
    """
    page: Page = authenticated_page
    target_mac = "00:AA:00:AA:00:AA"
    expected_switch_port = "Gi1/0/20"

    # Helper: safe locator getter with error context
    def safe_get(locator_str: str):
        return page.locator(locator_str)

    # -------------------------------------------------------------------------
    # Step 1: Confirm Profiler shows no endpoint with the target MAC address
    # -------------------------------------------------------------------------
    try:
        # Navigate to endpoint inventory / search page
        # NOTE: Adjust URL / navigation steps to match actual application routing
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/inventory/endpoints",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to endpoint inventory page: {exc}")

    try:
        # Clear any existing filters and search for the MAC
        search_input = safe_get("input[data-test='endpoint-search-input']")
        search_button = safe_get("button[data-test='endpoint-search-button']")

        await search_input.fill(target_mac)
        await search_button.click()

        # Wait for search results to load
        await page.wait_for_timeout(3_000)

        # Assume table rows have a test id; adjust selectors as needed
        result_rows = safe_get("table[data-test='endpoint-table'] tbody tr")

        # Assert no endpoint with this MAC exists initially
        row_count = await result_rows.count()
        for i in range(row_count):
            mac_cell = result_rows.nth(i).locator("td[data-test='endpoint-mac']")
            mac_text = (await mac_cell.inner_text()).strip().upper()
            assert (
                mac_text != target_mac
            ), f"Precondition failed: endpoint with MAC {target_mac} already exists."

    except PlaywrightError as exc:
        pytest.fail(f"Failed during initial endpoint absence verification: {exc}")

    # -------------------------------------------------------------------------
    # Steps 2–4 (External actions, not automated here)
    # -------------------------------------------------------------------------
    # 2. Connect the endpoint to switch port Gi1/0/20.
    # 3. Wait until the interface goes up (verify on switch).
    # 4. After 10 seconds, disconnect the endpoint.
    #
    # These steps are expected to be performed by the test harness / lab automation
    # or manually. We include a short wait to allow the operator to perform them.
    # Increase this timeout if needed to coordinate with external steps.
    external_action_timeout_sec = 30
    await page.wait_for_timeout(external_action_timeout_sec * 1000)

    # -------------------------------------------------------------------------
    # Step 5–6: Wait 1–2 minutes for traps to be processed and search again
    # -------------------------------------------------------------------------
    processing_wait_seconds = 90  # 1.5 minutes
    await page.wait_for_timeout(processing_wait_seconds * 1000)

    try:
        # Re-run search for the MAC address
        search_input = safe_get("input[data-test='endpoint-search-input']")
        search_button = safe_get("button[data-test='endpoint-search-button']")

        await search_input.fill(target_mac)
        await search_button.click()
        await page.wait_for_timeout(5_000)

        result_rows = safe_get("table[data-test='endpoint-table'] tbody tr")
        row_count = await result_rows.count()

        assert row_count > 0, (
            f"Endpoint with MAC {target_mac} was not discovered after SNMP trap window."
        )

        # ---------------------------------------------------------------------
        # Validate endpoint details from the first matching row
        # ---------------------------------------------------------------------
        discovered_row_index = None
        for i in range(row_count):
            mac_cell = result_rows.nth(i).locator("td[data-test='endpoint-mac']")
            mac_text = (await mac_cell.inner_text()).strip().upper()
            if mac_text == target_mac:
                discovered_row_index = i
                break

        assert (
            discovered_row_index is not None
        ), f"Endpoint with MAC {target_mac} not found in search results."

        endpoint_row = result_rows.nth(discovered_row_index)

        #  Expected: endpoint exists in inventory
        mac_cell = endpoint_row.locator("td[data-test='endpoint-mac']")
        mac_text = (await mac_cell.inner_text()).strip().upper()
        assert mac_text == target_mac, (
            f"Unexpected MAC in discovered endpoint row: {mac_text}, expected {target_mac}"
        )

        #  Expected: port Gi1/0/20
        port_cell = endpoint_row.locator("td[data-test='endpoint-port']")
        port_text = (await port_cell.inner_text()).strip()
        assert (
            expected_switch_port in port_text
        ), f"Endpoint port mismatch. Expected to contain '{expected_switch_port}', got '{port_text}'."

        #  Expected: disconnected or similar status (short-lived connection)
        status_cell = endpoint_row.locator("td[data-test='endpoint-status']")
        status_text = (await status_cell.inner_text()).strip().lower()
        # We allow multiple disconnected-type states; adjust as needed
        allowed_disconnected_states = {"disconnected", "inactive", "down"}
        assert (
            any(state in status_text for state in allowed_disconnected_states)
        ), f"Endpoint status not indicating disconnected state: '{status_text}'."

        # Open endpoint details to check discovery source and last seen time
        details_link = endpoint_row.locator("a[data-test='endpoint-details-link']")
        await details_link.click()

        # Wait for details panel / page to load
        await page.wait_for_timeout(3_000)

        # ---------------------------------------------------------------------
        # Validate discovery source includes SNMP traps
        # ---------------------------------------------------------------------
        discovery_source_field = safe_get(
            "[data-test='endpoint-discovery-source']"
        )
        discovery_source_text = (
            await discovery_source_field.inner_text()
        ).strip().lower()

        assert "snmp" in discovery_source_text and "trap" in discovery_source_text, (
            "Discovery source does not indicate SNMP trap-based discovery: "
            f"'{discovery_source_text}'"
        )

        # ---------------------------------------------------------------------
        # Validate last seen time is recent (correlated with the test window)
        # ---------------------------------------------------------------------
        last_seen_field = safe_get("[data-test='endpoint-last-seen']")
        last_seen_text = (await last_seen_field.inner_text()).strip()

        # NOTE: Parsing depends on the actual datetime format in the UI.
        # Example assumed format: "2026-01-06 14:23:10"
        last_seen_dt = None
        parse_formats = [
            "%Y-%m-%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%d/%m/%Y %H:%M:%S",
            "%d/%m/%Y %H:%M",
        ]
        for fmt in parse_formats:
            try:
                last_seen_dt = datetime.strptime(last_seen_text, fmt)
                break
            except ValueError:
                continue

        if last_seen_dt is None:
            pytest.fail(
                f"Unable to parse 'Last Seen' datetime from value: '{last_seen_text}'"
            )

        now = datetime.now()
        max_age_minutes = 10  # endpoint should have been seen recently
        assert last_seen_dt >= now - timedelta(
            minutes=max_age_minutes
        ), (
            f"'Last Seen' time ({last_seen_dt}) is older than {max_age_minutes} minutes, "
            "which is unexpected for this short-lived connection test."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed during SNMP trap-based endpoint verification: {exc}")
    except AssertionError:
        # Re-raise assertion errors so pytest reports them properly
        raise
    except Exception as exc:
        pytest.fail(f"Unexpected error during test execution: {exc}")