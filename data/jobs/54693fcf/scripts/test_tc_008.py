import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


async def send_malformed_snmp_trap(
    target_host: str,
    target_port: int,
    community: str = "public",
    count: int = 10,
    interval_seconds: float = 0.1,
) -> None:
    """
    Placeholder async helper that should send malformed SNMP traps to Profiler.

    NOTE:
        This implementation is intentionally a stub because the real mechanism
        (Scapy/custom script, network access, credentials) is environment-specific.
        Replace the body of this function with calls to your SNMP test tool.

    Args:
        target_host: Profiler trap listener IP or hostname.
        target_port: Profiler trap listener UDP port (e.g., 162).
        community: SNMP v2c community string.
        count: Number of malformed traps to send.
        interval_seconds: Delay between each malformed trap.
    """
    # TODO: Implement integration with your SNMP testing tool (e.g., Scapy).
    # Example (pseudo-code):
    #   for i in range(count):
    #       malformed_pdu = build_malformed_pdu()
    #       send_udp_packet(target_host, target_port, malformed_pdu)
    #       await asyncio.sleep(interval_seconds)

    logger.warning(
        "send_malformed_snmp_trap is a stub. Replace with real SNMP injection logic."
    )
    for _ in range(count):
        await asyncio.sleep(interval_seconds)


async def get_recent_log_entries(
    page: Page,
    since: datetime,
    max_entries: int = 200,
) -> List[str]:
    """
    Collect recent log entries from the Profiler UI.

    This function assumes:
        - There is a log viewer page or panel.
        - Log entries can be queried via a selector (e.g., table rows).
        - Each entry contains a timestamp and message.

    You must adapt selectors and parsing to your actual UI.

    Args:
        page: Authenticated Playwright page.
        since: Only log entries newer than this timestamp are returned.
        max_entries: Maximum number of log entries to return.

    Returns:
        A list of log message strings.
    """
    # Navigate to logs page if necessary. Adjust selector/URL as needed.
    # Example navigation – adapt to your application:
    try:
        # Open logs page or panel
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/logs.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        logger.error("Failed to navigate to logs page: %s", exc)
        return []

    # Wait for logs table or container
    # Replace with correct selector for your logs UI
    logs_container_selector = "table#logs-table, div.logs-container"
    try:
        await page.wait_for_selector(logs_container_selector, timeout=10_000)
    except PlaywrightError as exc:
        logger.error("Logs container not found: %s", exc)
        return []

    # Collect log rows/messages
    # Adapt selectors to actual DOM structure.
    log_row_selector = "table#logs-table tbody tr, div.log-entry"
    log_rows = await page.query_selector_all(log_row_selector)
    log_messages: List[str] = []

    for row in log_rows[:max_entries]:
        try:
            text = (await row.inner_text()).strip()
        except PlaywrightError:
            continue

        # Optional: filter by timestamp if the text contains it.
        # For now, we just collect recent items and let the caller interpret.
        log_messages.append(text)

    return log_messages


async def get_endpoint_inventory_snapshot(page: Page) -> List[str]:
    """
    Capture a snapshot of endpoint identifiers from the Profiler inventory UI.

    Assumptions:
        - There is an endpoint inventory page.
        - Endpoints are listed in a table or grid.
        - Each row contains a unique identifier (IP, MAC, hostname, etc.).

    You must adapt navigation and selectors to your actual UI.

    Args:
        page: Authenticated Playwright page.

    Returns:
        A list of endpoint identifier strings used for comparison.
    """
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/endpoints.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        logger.error("Failed to navigate to endpoints page: %s", exc)
        return []

    # Wait for endpoints table/grid
    endpoints_container_selector = "table#endpoints-table, div.endpoints-grid"
    try:
        await page.wait_for_selector(endpoints_container_selector, timeout=15_000)
    except PlaywrightError as exc:
        logger.error("Endpoints container not found: %s", exc)
        return []

    # Adapt selectors to your actual DOM structure
    endpoint_row_selector = "table#endpoints-table tbody tr, div.endpoint-row"
    endpoint_rows = await page.query_selector_all(endpoint_row_selector)
    endpoints: List[str] = []

    for row in endpoint_rows:
        try:
            # Example: assume first cell or a specific column contains unique ID
            # Adjust the selector/index to match your UI.
            cell = await row.query_selector("td:nth-child(1), span.endpoint-id")
            if not cell:
                continue
            identifier = (await cell.inner_text()).strip()
            if identifier:
                endpoints.append(identifier)
        except PlaywrightError:
            continue

    return endpoints


@pytest.mark.asyncio
async def test_malformed_snmp_trap_handling(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_008: Verify handling of malformed SNMP trap (corrupted PDU).

    Objective:
        Ensure Profiler robustly handles malformed SNMP trap PDUs without
        crashing, becoming unresponsive, or corrupting endpoint data.

    Preconditions:
        - Profiler is running with trap listener enabled.
        - An external SNMP testing tool is available to send malformed traps.
        - The authenticated_page fixture provides an already logged-in admin page.

    Steps:
        1. Capture baseline endpoint inventory and timestamp.
        2. Use SNMP testing tool to send multiple malformed v2c traps.
        3. Monitor logs and system behavior after injection.
        4. Verify UI remains responsive and endpoint inventory is unchanged.
        5. Verify logs contain indications of malformed/invalid SNMP messages.
    """
    page: Page = authenticated_page

    # ------------------------------------------------------------------ #
    # Step 0: Navigate to admin welcome page to ensure we start from a
    #         known, authenticated location.
    # ------------------------------------------------------------------ #
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open admin welcome page: {exc}")

    # ------------------------------------------------------------------ #
    # Step 1: Take baseline snapshot of endpoint inventory and timestamp.
    # ------------------------------------------------------------------ #
    baseline_timestamp = datetime.utcnow()
    baseline_endpoints = await get_endpoint_inventory_snapshot(page)

    # Sanity check: ensure we could read the inventory at all
    assert isinstance(
        baseline_endpoints, list
    ), "Baseline endpoint inventory must be a list."
    logger.info("Baseline endpoints count: %d", len(baseline_endpoints))

    # ------------------------------------------------------------------ #
    # Step 2 & 3: Send malformed SNMP v2c traps (10–20 in quick succession).
    #             This is done via an external tool or script.
    # ------------------------------------------------------------------ #
    malformed_trap_count = 15
    trap_target_host = "10.34.50.201"  # Profiler trap listener IP
    trap_target_port = 162             # Adjust if your listener uses a custom port

    # Record a slightly earlier timestamp to ensure we capture all logs
    log_start_time = datetime.utcnow() - timedelta(seconds=5)

    try:
        await send_malformed_snmp_trap(
            target_host=trap_target_host,
            target_port=trap_target_port,
            community="public",
            count=malformed_trap_count,
            interval_seconds=0.1,
        )
    except Exception as exc:
        # This should not fail the test for Profiler; it indicates an issue
        # with the test harness itself.
        pytest.fail(f"Failed to send malformed SNMP traps: {exc}")

    # Optional: small delay to allow Profiler to process incoming traps
    await asyncio.sleep(5)

    # ------------------------------------------------------------------ #
    # Step 4: Monitor logs and system behavior.
    #         Here we focus on log inspection via the UI.
    # ------------------------------------------------------------------ #
    recent_logs = await get_recent_log_entries(page, since=log_start_time)

    # ------------------------------------------------------------------ #
    # Step 5a: Verify UI is still responsive.
    #          We do a simple interaction: reload a key page and wait for
    #          a known element.
    # ------------------------------------------------------------------ #
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
        # Example: wait for some known element on the welcome page
        await page.wait_for_selector("body", timeout=10_000)
        ui_responsive = True
    except PlaywrightError as exc:
        logger.error("UI became unresponsive after malformed traps: %s", exc)
        ui_responsive = False

    assert ui_responsive, "Profiler UI must remain responsive after malformed traps."

    # ------------------------------------------------------------------ #
    # Step 5b: Verify endpoint data remains intact (no new/changed endpoints).
    #          This is a heuristic check: we ensure that the set of endpoint
    #          identifiers has not changed. If your UI exposes additional
    #          metadata (e.g., last-seen timestamp), you can add stronger
    #          assertions here.
    # ------------------------------------------------------------------ #
    post_injection_endpoints = await get_endpoint_inventory_snapshot(page)

    assert (
        sorted(baseline_endpoints) == sorted(post_injection_endpoints)
    ), (
        "Endpoint inventory changed after receiving malformed traps. "
        "Profiler must not create or update endpoints based on malformed PDUs."
    )

    # ------------------------------------------------------------------ #
    # Step 5c: Verify logs contain errors or warnings indicating malformed
    #          or invalid SNMP messages, and that there are no unhandled
    #          exceptions.
    # ------------------------------------------------------------------ #
    # Heuristic patterns to look for – adjust to match your actual log format.
    error_indicators = [
        "malformed SNMP",
        "invalid SNMP",
        "invalid PDU",
        "decode error",
        "parsing error",
        "invalid length",
        "bad ASN.1",
    ]
    unhandled_exception_indicators = [
        "Traceback (most recent call last)",
        "UnhandledException",
        "unhandled exception",
        "panic:",
        "fatal error",
    ]

    log_text_combined = "\n".join(recent_logs).lower() if recent_logs else ""

    has_malformed_error_log = any(
        indicator in log_text_combined for indicator in error_indicators
    )
    has_unhandled_exception_log = any(
        indicator.lower() in log_text_combined
        for indicator in unhandled_exception_indicators
    )

    # It is strongly expected that malformed traps produce some explicit
    # log entry. If your product logs differently, adjust the patterns above.
    assert has_malformed_error_log, (
        "Logs should contain errors or warnings indicating malformed/invalid "
        "SNMP messages after sending malformed traps."
    )

    assert not has_unhandled_exception_log, (
        "Logs contain indications of unhandled exceptions or fatal errors "
        "after processing malformed traps."
    )

    # ------------------------------------------------------------------ #
    # Step 5d: Verify process stability, no crash or restart.
    #          From a UI-only perspective, we can assert that:
    #            - The session remains valid.
    #            - There is no forced re-login or 'system restarting' banner.
    #          For deeper validation (PID, uptime), you would need an API
    #          or OS-level check outside Playwright.
    # ------------------------------------------------------------------ #
    # Check that we are still logged in (e.g., presence of admin menu).
    # Adjust selector to match your application.
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
        admin_menu = await page.query_selector("nav.admin-menu, #adminMenu")
        still_logged_in = admin_menu is not None
    except PlaywrightError:
        still_logged_in = False

    assert still_logged_in, (
        "Profiler appears to have restarted or invalidated the session after "
        "receiving malformed traps; admin session should remain active."
    )

    # Optional: capture a screenshot for post-test analysis
    screenshots_dir = Path("artifacts") / "screenshots"
    screenshots_dir.mkdir(parents=True, exist_ok=True)
    screenshot_path = screenshots_dir / "tc_008_malformed_snmp_trap.png"
    try:
        await page.screenshot(path=str(screenshot_path), full_page=True)
    except PlaywrightError as exc:
        logger.warning("Failed to capture screenshot: %s", exc)