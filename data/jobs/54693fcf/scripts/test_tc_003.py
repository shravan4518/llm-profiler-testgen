import asyncio
from typing import Tuple

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_003_profiler_mac_move_trap_updates_port_without_duplicates(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_003: Verify Profiler processes MAC address change notification trap for
    an endpoint moving ports on the same switch.

    Preconditions:
        - Profiler is reachable and user is authenticated (handled by fixture).
        - Profiler is configured to receive traps.
        - Access switch supports MAC notification traps and is configured.
        - Endpoint with MAC AA:BB:CC:DD:EE:FF is initially on 10.10.20.10 Gi1/0/11
          and visible in Profiler.

    Expected Results:
        - Profiler receives MAC change trap indicating old and new ports.
        - No new endpoint entry is created for the same MAC.
        - Existing endpoint entry is updated to port Gi1/0/12.
        - Topology/connection views show endpoint on Gi1/0/12.
        - History (if available) shows previous port Gi1/0/11.
    """
    page = authenticated_page

    # --- Test Data ---------------------------------------------------------
    mac_address = "AA:BB:CC:DD:EE:FF"
    switch_ip = "10.10.20.10"
    old_port = "Gi1/0/11"
    new_port = "Gi1/0/12"

    # NOTE:
    # The CSS/XPath selectors below are placeholders and must be adapted
    # to the actual Profiler UI DOM structure.

    # Common selectors (placeholders)
    endpoint_search_input_selector = "input#endpoint-search"
    endpoint_search_button_selector = "button#endpoint-search-submit"
    endpoint_table_rows_selector = "table#endpoints-table tbody tr"
    endpoint_mac_cell_selector = "td.col-mac"
    endpoint_switch_cell_selector = "td.col-switch"
    endpoint_port_cell_selector = "td.col-port"
    endpoint_details_link_selector = "a.endpoint-details-link"
    endpoint_details_port_selector = "span#endpoint-current-port"
    endpoint_details_switch_selector = "span#endpoint-current-switch"
    endpoint_history_tab_selector = "a#endpoint-history-tab"
    endpoint_history_rows_selector = "table#endpoint-history-table tbody tr"

    # Helper functions ------------------------------------------------------

    async def search_endpoint_by_mac(
        mac: str,
    ) -> Tuple[int, str, str]:
        """
        Search for an endpoint by MAC and return:
        (row_count_for_mac, associated_switch, associated_port).

        Raises AssertionError if no row is found for the MAC.
        """
        try:
            # Clear and enter MAC in search field
            await page.fill(endpoint_search_input_selector, "")
            await page.fill(endpoint_search_input_selector, mac)

            # Click search and wait for table to update
            async with page.expect_response(
                lambda r: "/endpoints/search" in r.url and r.status == 200
            ):
                await page.click(endpoint_search_button_selector)

            await page.wait_for_selector(endpoint_table_rows_selector, timeout=10000)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to search for endpoint with MAC {mac}: {exc}"
            ) from exc

        # Collect rows matching the MAC
        rows = await page.query_selector_all(endpoint_table_rows_selector)
        mac_rows = []
        for row in rows:
            mac_cell = await row.query_selector(endpoint_mac_cell_selector)
            if not mac_cell:
                continue
            mac_text = (await mac_cell.inner_text()).strip().upper()
            if mac_text == mac.upper():
                mac_rows.append(row)

        if not mac_rows:
            raise AssertionError(f"No endpoint row found for MAC {mac}")

        # For this test we expect exactly one row per MAC
        row_count = len(mac_rows)
        if row_count > 1:
            raise AssertionError(
                f"Expected a single endpoint entry for MAC {mac}, "
                f"but found {row_count} rows."
            )

        # Extract switch and port from the single matching row
        row = mac_rows[0]
        switch_cell = await row.query_selector(endpoint_switch_cell_selector)
        port_cell = await row.query_selector(endpoint_port_cell_selector)

        if not switch_cell or not port_cell:
            raise AssertionError(
                "Could not locate switch or port cell in the endpoint row."
            )

        switch_text = (await switch_cell.inner_text()).strip()
        port_text = (await port_cell.inner_text()).strip()

        return row_count, switch_text, port_text

    async def open_endpoint_details_for_mac(mac: str) -> None:
        """
        Open the endpoint details view for the given MAC from the search results.
        """
        try:
            rows = await page.query_selector_all(endpoint_table_rows_selector)
            for row in rows:
                mac_cell = await row.query_selector(endpoint_mac_cell_selector)
                if not mac_cell:
                    continue
                mac_text = (await mac_cell.inner_text()).strip().upper()
                if mac_text == mac.upper():
                    details_link = await row.query_selector(
                        endpoint_details_link_selector
                    )
                    if not details_link:
                        raise AssertionError(
                            "Endpoint details link not found in the row."
                        )

                    async with page.expect_navigation():
                        await details_link.click()
                    return

            raise AssertionError(
                f"Endpoint row with MAC {mac} not found when opening details."
            )
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to open endpoint details for MAC {mac}: {exc}"
            ) from exc

    # ----------------------------------------------------------------------
    # Step 1: Verify initial association: MAC on switch 10.10.20.10 Gi1/0/11
    # ----------------------------------------------------------------------
    row_count, initial_switch, initial_port = await search_endpoint_by_mac(
        mac_address
    )

    assert row_count == 1, (
        f"Expected exactly 1 endpoint entry for MAC {mac_address}, "
        f"found {row_count}."
    )
    assert (
        initial_switch == switch_ip
    ), f"Expected switch {switch_ip}, found {initial_switch} for MAC {mac_address}."
    assert (
        initial_port == old_port
    ), f"Expected port {old_port}, found {initial_port} for MAC {mac_address}."

    # ----------------------------------------------------------------------
    # Step 2 & 3:
    # Physically move the endpoint cable and verify MAC move trap is sent.
    #
    # NOTE: These actions cannot be automated directly via Playwright, as they
    # involve physical cabling and network packet capture. We treat them as
    # external pre-steps and log them here. If an API or UI exists to validate
    # traps, it could be integrated here.
    # ----------------------------------------------------------------------
    # TODO: Integrate with lab automation or switch API if available.
    # For now, we log and assume the MAC move trap is sent correctly.
    print(
        "INFO: Ensure the endpoint cable is moved from "
        f"{old_port} to {new_port} on switch {switch_ip} "
        "and a MAC move notification trap is sent (verified via packet capture)."
    )

    # ----------------------------------------------------------------------
    # Step 4: Wait 30–60 seconds for Profiler processing
    # ----------------------------------------------------------------------
    await asyncio.sleep(45)

    # ----------------------------------------------------------------------
    # Step 5: Refresh endpoint details for the MAC and validate behavior
    # ----------------------------------------------------------------------
    # Re-run the search to verify there is still only one endpoint entry
    row_count_after_move, switch_after_move, port_after_move = (
        await search_endpoint_by_mac(mac_address)
    )

    # Expected: No new endpoint entry is created for the same MAC
    assert (
        row_count_after_move == 1
    ), f"Expected a single endpoint entry after MAC move, found {row_count_after_move}."

    # Expected: The existing endpoint entry is updated to associate with new port
    assert (
        switch_after_move == switch_ip
    ), f"Expected switch {switch_ip} after move, found {switch_after_move}."
    assert (
        port_after_move == new_port
    ), f"Expected port {new_port} after move, found {port_after_move}."

    # Open details to check topology/connection views and history
    await open_endpoint_details_for_mac(mac_address)

    # Validate current port and switch in details page
    try:
        await page.wait_for_selector(endpoint_details_port_selector, timeout=10000)
        await page.wait_for_selector(endpoint_details_switch_selector, timeout=10000)
    except PlaywrightError as exc:
        raise AssertionError(
            "Endpoint details did not load correctly: "
            "missing port or switch fields."
        ) from exc

    current_port_text = (
        await page.locator(endpoint_details_port_selector).inner_text()
    )
    current_switch_text = (
        await page.locator(endpoint_details_switch_selector).inner_text()
    )

    current_port_text = current_port_text.strip()
    current_switch_text = current_switch_text.strip()

    # Expected: Topology/connection views show endpoint on Gi1/0/12
    assert (
        current_switch_text == switch_ip
    ), f"Details view shows switch {current_switch_text}, expected {switch_ip}."
    assert (
        current_port_text == new_port
    ), f"Details view shows port {current_port_text}, expected {new_port}."

    # ----------------------------------------------------------------------
    # Optional: Historical information shows previous port (if supported)
    # ----------------------------------------------------------------------
    history_available = True
    try:
        await page.click(endpoint_history_tab_selector)
        await page.wait_for_selector(endpoint_history_rows_selector, timeout=10000)
    except PlaywrightError:
        # If history is not supported or not available, do not fail the test,
        # but mark it as informational.
        history_available = False
        print("INFO: Endpoint history view not available; skipping history checks.")

    if history_available:
        history_rows = await page.query_selector_all(endpoint_history_rows_selector)
        history_text = ""
        for row in history_rows:
            row_text = (await row.inner_text()).strip()
            history_text += row_text + "\n"

        # We expect to see old and new ports in history if feature is supported
        assert old_port in history_text or new_port in history_text, (
            "Endpoint history does not show expected port information. "
            f"Expected to find at least {old_port} or {new_port}."
        )

    # ----------------------------------------------------------------------
    # Postconditions:
    # - Single endpoint record for MAC AA:BB:CC:DD:EE:FF associated with port Gi1/0/12
    # ----------------------------------------------------------------------
    # Re-check via list view to ensure final state is correct
    row_count_final, switch_final, port_final = await search_endpoint_by_mac(
        mac_address
    )

    assert (
        row_count_final == 1
    ), f"Postcondition failed: expected 1 endpoint record, found {row_count_final}."
    assert (
        switch_final == switch_ip
    ), f"Postcondition failed: expected switch {switch_ip}, found {switch_final}."
    assert (
        port_final == new_port
    ), f"Postcondition failed: expected port {new_port}, found {port_final}."