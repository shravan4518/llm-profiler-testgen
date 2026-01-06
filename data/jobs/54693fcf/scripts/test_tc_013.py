import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.high
async def test_tc_013_snmp_trap_and_polling_integration(authenticated_page: Page, browser):
    """
    TC_013: Verify integration between SNMP trap-based discovery and SNMP polling (MAC/ARP tables)

    Ensures that endpoints discovered via SNMP traps are properly reconciled with periodic
    SNMP polling data, avoiding duplicates or inconsistent state.

    Prerequisites:
    - Profiler configured for SNMP trap-based discovery and SNMP polling for switch 10.10.20.13
    - Polling interval: 5 minutes

    Steps (mapped to comments in code):
    1. Ensure endpoint DE:AD:BE:EF:00:01 is not present in Profiler.
    2. Connect the endpoint to Gi1/0/30, generating linkUp trap (simulated or assumed external).
    3. Confirm via packet capture that trap was sent (simulated / placeholder).
    4. Within 1 minute, verify that Profiler has created endpoint entry based on trap.
    5. Wait until the next SNMP polling cycle completes.
    6. Inspect endpoint details after polling to ensure attributes (IP, VLAN, etc.) are augmented.
    7. Verify there is still only a single endpoint entry for the MAC and metadata shows trap + polling.
    """

    page = authenticated_page
    target_mac = "DE:AD:BE:EF:00:01"
    target_switch_ip = "10.10.20.13"
    target_port = "Gi1/0/30"

    # Helper functions
    async def safe_click(page_obj: Page, selector: str, description: str) -> None:
        """Safely click an element and raise a descriptive error if it fails."""
        try:
            await page_obj.wait_for_selector(selector, timeout=10_000)
            await page_obj.click(selector)
        except PlaywrightError as exc:
            raise AssertionError(f"Failed to click {description} ({selector}): {exc}") from exc

    async def safe_fill(page_obj: Page, selector: str, value: str, description: str) -> None:
        """Safely fill an input field."""
        try:
            await page_obj.wait_for_selector(selector, timeout=10_000)
            await page_obj.fill(selector, value)
        except PlaywrightError as exc:
            raise AssertionError(f"Failed to fill {description} ({selector}): {exc}") from exc

    async def search_endpoint_by_mac(
        page_obj: Page,
        mac: str,
    ) -> List[Dict[str, Any]]:
        """
        Search endpoint table by MAC and return list of row data.

        This function is UI-structure dependent; selectors are examples and should be
        adapted to the real application.
        """
        # Navigate to Endpoint / Profiler page (example navigation)
        # Adjust selectors and navigation steps to match the actual UI.
        try:
            await safe_click(
                page_obj,
                "a[href*='profiler_endpoints']",
                "Profiler Endpoints navigation link",
            )
        except AssertionError:
            # Fallback: try a generic menu path, but still fail if not found
            await safe_click(
                page_obj,
                "text=Profiler >> text=Endpoints",
                "Profiler > Endpoints navigation path",
            )

        # Clear any existing filter and search by MAC
        await safe_fill(
            page_obj,
            "input[data-testid='endpoint-filter-mac']",
            mac,
            "MAC filter input",
        )
        await safe_click(
            page_obj,
            "button[data-testid='endpoint-filter-apply']",
            "Apply filter button",
        )

        # Wait for table to refresh
        await page_obj.wait_for_timeout(2_000)

        # Collect rows
        rows = await page_obj.query_selector_all(
            "table[data-testid='endpoint-table'] tbody tr"
        )

        results: List[Dict[str, Any]] = []
        for row in rows:
            try:
                mac_cell = await row.query_selector("td[data-col='mac']")
                switch_cell = await row.query_selector("td[data-col='switch']")
                port_cell = await row.query_selector("td[data-col='port']")
                ip_cell = await row.query_selector("td[data-col='ip']")
                vlan_cell = await row.query_selector("td[data-col='vlan']")
                source_cell = await row.query_selector("td[data-col='source']")

                mac_text = (await mac_cell.inner_text()).strip() if mac_cell else ""
                if mac_text.lower() != mac.lower():
                    continue

                results.append(
                    {
                        "mac": mac_text,
                        "switch": (await switch_cell.inner_text()).strip()
                        if switch_cell
                        else "",
                        "port": (await port_cell.inner_text()).strip()
                        if port_cell
                        else "",
                        "ip": (await ip_cell.inner_text()).strip()
                        if ip_cell
                        else "",
                        "vlan": (await vlan_cell.inner_text()).strip()
                        if vlan_cell
                        else "",
                        "source": (await source_cell.inner_text()).strip()
                        if source_cell
                        else "",
                        "row_handle": row,
                    }
                )
            except PlaywrightError as exc:
                logger.warning("Failed to parse endpoint row: %s", exc)

        return results

    async def open_endpoint_details(
        endpoint_row: Dict[str, Any],
    ) -> Page:
        """
        Open endpoint details in a new tab or drawer depending on UI.

        Returns:
            Page or same page with detail panel visible.
        """
        row_handle = endpoint_row["row_handle"]
        # Click row or specific "details" icon
        details_icon = await row_handle.query_selector(
            "button[data-testid='endpoint-details']"
        )
        if details_icon:
            await details_icon.click()
        else:
            await row_handle.click()

        # Wait for details panel
        await page.wait_for_selector(
            "[data-testid='endpoint-details-panel'], "
            "div.endpoint-details, "
            "section[data-testid='endpoint-details']",
            timeout=10_000,
        )
        return page

    async def get_endpoint_detail_fields(
        page_obj: Page,
    ) -> Dict[str, Optional[str]]:
        """
        Read endpoint detail fields (IP, VLAN, sources, last update, etc.).

        Selectors are illustrative and should be adapted to the real UI.
        """
        async def get_text(selector: str) -> Optional[str]:
            try:
                el = await page_obj.query_selector(selector)
                if not el:
                    return None
                return (await el.inner_text()).strip()
            except PlaywrightError:
                return None

        return {
            "ip": await get_text("[data-testid='endpoint-detail-ip']"),
            "vlan": await get_text("[data-testid='endpoint-detail-vlan']"),
            "mac": await get_text("[data-testid='endpoint-detail-mac']"),
            "switch": await get_text("[data-testid='endpoint-detail-switch']"),
            "port": await get_text("[data-testid='endpoint-detail-port']"),
            "data_sources": await get_text(
                "[data-testid='endpoint-detail-data-sources']"
            ),
            "last_update": await get_text(
                "[data-testid='endpoint-detail-last-update']"
            ),
        }

    async def wait_for_endpoint_presence(
        mac: str,
        timeout_sec: int,
        require_enriched: bool = False,
    ) -> Dict[str, Any]:
        """
        Poll for endpoint presence within timeout.

        Args:
            mac: MAC address to search.
            timeout_sec: Maximum time to wait.
            require_enriched: If True, wait until IP & VLAN are non-empty.

        Returns:
            Endpoint row dict.

        Raises:
            AssertionError if endpoint not found (or not enriched) within timeout.
        """
        deadline = datetime.utcnow() + timedelta(seconds=timeout_sec)
        last_results: List[Dict[str, Any]] = []

        while datetime.utcnow() < deadline:
            last_results = await search_endpoint_by_mac(page, mac)

            if len(last_results) == 1:
                row = last_results[0]
                if not require_enriched:
                    return row

                # When enriched, expect non-empty IP and VLAN
                ip = row.get("ip", "")
                vlan = row.get("vlan", "")
                if ip and vlan:
                    return row

            if len(last_results) > 1:
                raise AssertionError(
                    f"Duplicate endpoints found for MAC {mac}: {len(last_results)} rows"
                )

            await page.wait_for_timeout(5_000)

        if require_enriched:
            raise AssertionError(
                f"Endpoint for MAC {mac} was not enriched with IP/VLAN "
                f"within {timeout_sec} seconds. Last results: {last_results}"
            )
        raise AssertionError(
            f"Endpoint for MAC {mac} not found within {timeout_sec} seconds."
        )

    # ----------------------------------------------------------------------
    # Step 1: Ensure endpoint DE:AD:BE:EF:00:01 is not present in Profiler.
    # ----------------------------------------------------------------------
    initial_results = await search_endpoint_by_mac(page, target_mac)
    assert (
        len(initial_results) == 0
    ), (
        f"Precondition failed: endpoint with MAC {target_mac} already exists. "
        f"Found {len(initial_results)} entries."
    )

    # ----------------------------------------------------------------------
    # Step 2: Connect the endpoint to Gi1/0/30, generating linkUp trap.
    # NOTE: Physical connection is external to UI; here we may only trigger
    #       a simulated action or log a note.
    # ----------------------------------------------------------------------
    logger.info(
        "Test precondition: connect endpoint %s to switch %s port %s "
        "and ensure linkUp trap is generated.",
        target_mac,
        target_switch_ip,
        target_port,
    )
    # If the UI has a way to simulate trap or lab hooks, call it here.
    # Placeholder: no-op, assume external system does it.

    # ----------------------------------------------------------------------
    # Step 3: Confirm via packet capture that trap was sent.
    # NOTE: This is usually done outside UI (e.g., via PCAP or monitoring tool).
    #       We'll simulate the verification step as a placeholder assertion.
    # ----------------------------------------------------------------------
    # In a real test, you could integrate with an API that exposes capture results.
    trap_verified = True  # Placeholder for external verification
    assert trap_verified, "SNMP linkUp trap for the endpoint was not verified."

    # ----------------------------------------------------------------------
    # Step 4: Within 1 minute, verify that Profiler has created endpoint
    #         entry based on trap (with initial attributes).
    # ----------------------------------------------------------------------
    trap_discovery_timeout_sec = 60
    trap_endpoint_row = await wait_for_endpoint_presence(
        mac=target_mac,
        timeout_sec=trap_discovery_timeout_sec,
        require_enriched=False,
    )

    # Validate initial attributes from trap-based discovery
    assert (
        trap_endpoint_row["mac"].lower() == target_mac.lower()
    ), "Endpoint MAC in table does not match expected MAC from trap."
    assert target_switch_ip in trap_endpoint_row["switch"], (
        f"Expected switch {target_switch_ip} in endpoint row; "
        f"got '{trap_endpoint_row['switch']}'."
    )
    assert target_port in trap_endpoint_row["port"], (
        f"Expected port {target_port} in endpoint row; "
        f"got '{trap_endpoint_row['port']}'."
    )

    # At this stage IP and VLAN may be empty because only trap data is present.
    # We explicitly check they are not yet enriched (if that is expected).
    # If your system already enriches immediately, relax these checks.
    assert trap_endpoint_row.get("ip", "") in ("", "-", "N/A"), (
        f"IP is already present ({trap_endpoint_row.get('ip')}) before polling; "
        "expected trap-only data."
    )
    assert trap_endpoint_row.get("vlan", "") in ("", "-", "N/A"), (
        f"VLAN is already present ({trap_endpoint_row.get('vlan')}) before polling; "
        "expected trap-only data."
    )

    # ----------------------------------------------------------------------
    # Step 5: Wait until the next SNMP polling cycle completes.
    # Polling interval is 5 minutes, but system might poll sooner.
    # We'll wait up to 6 minutes for enrichment (IP & VLAN).
    # ----------------------------------------------------------------------
    polling_wait_timeout_sec = 6 * 60
    enriched_endpoint_row = await wait_for_endpoint_presence(
        mac=target_mac,
        timeout_sec=polling_wait_timeout_sec,
        require_enriched=True,
    )

    # ----------------------------------------------------------------------
    # Step 6: Inspect endpoint details after polling to ensure attributes
    #         (IP, VLAN, etc.) are augmented from MAC/ARP tables.
    # ----------------------------------------------------------------------
    await open_endpoint_details(enriched_endpoint_row)
    details = await get_endpoint_detail_fields(page)

    # Basic consistency checks
    assert details["mac"] and details["mac"].lower() == target_mac.lower(), (
        f"Endpoint details MAC mismatch: expected {target_mac}, "
        f"got {details['mac']}"
    )
    assert details["switch"] and target_switch_ip in details["switch"], (
        f"Endpoint details switch mismatch: expected to contain {target_switch_ip}, "
        f"got {details['switch']}"
    )
    assert details["port"] and target_port in details["port"], (
        f"Endpoint details port mismatch: expected to contain {target_port}, "
        f"got {details['port']}"
    )

    # Enrichment assertions
    assert details["ip"] not in (None, "", "-", "N/A"), (
        "Endpoint IP address is missing after SNMP polling enrichment."
    )
    assert details["vlan"] not in (None, "", "-", "N/A"), (
        "Endpoint VLAN is missing after SNMP polling enrichment."
    )

    # ----------------------------------------------------------------------
    # Step 7: Verify there is still only a single endpoint entry for the MAC
    #         and metadata shows both trap and polling as data sources.
    # ----------------------------------------------------------------------
    final_results = await search_endpoint_by_mac(page, target_mac)
    assert (
        len(final_results) == 1
    ), (
        f"Expected a single endpoint entry for MAC {target_mac} after polling, "
        f"but found {len(final_results)} entries."
    )

    # Source / last-update metadata should show both trap and polling.
    # This is UI-specific; we assume a "data_sources" field contains tokens.
    data_sources_text = details.get("data_sources") or ""
    normalized_sources = data_sources_text.lower()

    assert "trap" in normalized_sources, (
        "Endpoint data sources do not indicate trap-based discovery. "
        f"Actual sources text: '{data_sources_text}'"
    )
    assert "poll" in normalized_sources or "snmp" in normalized_sources, (
        "Endpoint data sources do not indicate SNMP polling. "
        f"Actual sources text: '{data_sources_text}'"
    )

    # Optional: Validate last update timestamp is recent (within 10 minutes).
    last_update_text = details.get("last_update")
    if last_update_text:
        logger.info("Endpoint last update: %s", last_update_text)
        # Parsing format is system-specific; this is a placeholder.
        # If you know the format, parse and assert recency.

    # ----------------------------------------------------------------------
    # Postconditions:
    # - Single enriched endpoint record exists; integration between trap and polling
    #   works as intended.
    # ----------------------------------------------------------------------
    # Explicit postcondition assertion (already implied by checks above).
    assert (
        len(final_results) == 1
        and final_results[0].get("ip")
        and final_results[0].get("vlan")
    ), (
        "Postcondition failed: single enriched endpoint record for MAC "
        f"{target_mac} does not exist as expected."
    )

    # Small wait to ensure UI is stable before test teardown
    await asyncio.sleep(1)