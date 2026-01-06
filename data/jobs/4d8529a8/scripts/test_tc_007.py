import asyncio
import logging
from datetime import datetime, timedelta
from typing import List

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


async def send_malformed_dhcp_packets(
    target_vlan_interface: str,
    target_broadcast_ip: str,
    packet_count: int = 50,
    mac_address: str = "AA:BB:CC:DD:EE:08",
) -> None:
    """
    Placeholder async helper to inject malformed DHCP packets (e.g., via Scapy).

    In a real environment, this function should:
      - Run on the test machine that has access to the PPS VLAN.
      - Use Scapy or a similar tool to craft malformed DHCP DISCOVER packets
        with missing required fields or corrupted options length.
      - Send a burst of 'packet_count' packets to the broadcast address.

    This stub is provided so the test remains syntactically complete and
    executable. Implement the actual packet injection logic in your environment.
    """
    logger.info(
        "Simulating sending %d malformed DHCP packets from MAC %s "
        "to broadcast %s on interface %s",
        packet_count,
        mac_address,
        target_broadcast_ip,
        target_vlan_interface,
    )
    # Simulate network delay / packet transmission time
    await asyncio.sleep(2)


async def fetch_profiler_logs_since(
    page: Page,
    since_timestamp: datetime,
    log_filter_text: str = "DHCP",
) -> List[str]:
    """
    Fetch Profiler logs from the UI or an embedded log viewer since a given time.

    The actual implementation depends on the Profiler UI. This is a generic
    example that assumes:
      - There is a logs page reachable via a navigation menu.
      - Logs are listed in a table or text area.
      - There is an optional filter box to narrow results (e.g., by "DHCP").

    Adjust selectors and navigation steps to match your real application.
    """
    logs: List[str] = []

    try:
        # Navigate to logs page (adjust selectors/URLs as needed)
        # Step A: Open navigation menu
        await page.click("nav >> text=Logs")

        # Optional: Wait for logs view to load
        await page.wait_for_selector("data-test-id=profiler-logs-container", timeout=15000)

        # Optional: Filter logs for DHCP-related entries
        filter_selector = "input[data-test-id=logs-filter-input]"
        if await page.locator(filter_selector).is_visible():
            await page.fill(filter_selector, log_filter_text)
            await page.keyboard.press("Enter")
            await page.wait_for_timeout(1000)

        # Example: logs displayed as rows in a table
        log_rows = page.locator("tbody[data-test-id=logs-table-body] tr")
        row_count = await log_rows.count()

        for i in range(row_count):
            row = log_rows.nth(i)
            # Adjust selectors depending on actual DOM structure
            timestamp_text = await row.locator("td:nth-child(1)").inner_text()
            message_text = await row.locator("td:nth-child(2)").inner_text()

            # Parse timestamp if format is known; here we just collect all logs
            # and let the caller filter by 'since_timestamp' if needed.
            log_entry = f"{timestamp_text} {message_text}"
            logs.append(log_entry)

    except PlaywrightError as exc:
        logger.error("Error while fetching profiler logs: %s", exc)

    return logs


@pytest.mark.asyncio
async def test_invalid_dhcpv4_packet_structure_handling(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_007: Invalid DHCPv4 packet structure handling

    Objective:
        Confirm that Profiler safely handles malformed DHCPv4 packets without
        crashing or misclassifying devices.

    Steps:
        1. Craft malformed DHCP DISCOVER packets (missing required fields
           or corrupted options length).
        2. Send a burst of 50 malformed DHCP packets to broadcast address
           on VLAN connected to PPS.
        3. Monitor PPS Profiler logs for parsing errors.
        4. In Profiler UI, search for MAC AA:BB:CC:DD:EE:08.

    Expected:
        - Profiler logs indicate parsing errors or discarded malformed packets.
        - No device record is created based solely on malformed DHCP packets.
        - Profiler service remains stable with no crash or restart.
    """
    page: Page = authenticated_page
    test_mac = "AA:BB:CC:DD:EE:08"
    vlan_interface = "eth-test-vlan"  # Adjust to your test interface
    broadcast_ip = "255.255.255.255"  # Or VLAN-specific broadcast IP

    # Record the time before sending packets so we can correlate logs
    test_start_time = datetime.utcnow()

    # -------------------------------------------------------------------------
    # Step 1 & 2: Send malformed DHCP DISCOVER packets
    # -------------------------------------------------------------------------
    try:
        await send_malformed_dhcp_packets(
            target_vlan_interface=vlan_interface,
            target_broadcast_ip=broadcast_ip,
            packet_count=50,
            mac_address=test_mac,
        )
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to send malformed DHCP packets: {exc}")

    # Allow some time for Profiler to process incoming packets and log results
    await asyncio.sleep(5)

    # -------------------------------------------------------------------------
    # Step 3: Monitor PPS Profiler logs for parsing errors
    # -------------------------------------------------------------------------
    logs = await fetch_profiler_logs_since(page, since_timestamp=test_start_time)

    # Basic sanity check: logs should not be empty after test start
    assert logs, "No logs were retrieved after sending malformed DHCP packets."

    # Look for evidence of parsing errors or discarded packets
    error_keywords = [
        "DHCP",
        "malformed",
        "invalid",
        "parse error",
        "parsing error",
        "discarded packet",
        "bad options length",
    ]
    logs_joined = "\n".join(logs).lower()

    has_parsing_error_log = any(keyword in logs_joined for keyword in error_keywords)

    assert has_parsing_error_log, (
        "Profiler logs do not indicate parsing errors or discarded malformed "
        "DHCP packets. Logs inspected:\n"
        f"{logs_joined}"
    )

    # -------------------------------------------------------------------------
    # Step 4: In Profiler UI, search for MAC AA:BB:CC:DD:EE:08
    # -------------------------------------------------------------------------
    try:
        # Navigate to Profiler / Devices view
        await page.click("nav >> text=Profiler")
        await page.click("nav >> text=Devices")

        # Wait for devices page to load
        await page.wait_for_selector("data-test-id=devices-table", timeout=15000)

        # Enter MAC in search/filter box
        search_input_selector = "input[data-test-id=device-search-input]"
        await page.fill(search_input_selector, test_mac)
        await page.keyboard.press("Enter")

        # Wait briefly for search results to update
        await page.wait_for_timeout(2000)

        # Check if any device rows are present
        device_rows = page.locator(
            "tbody[data-test-id=devices-table-body] tr"
        )
        device_count = await device_rows.count()
    except PlaywrightError as exc:
        pytest.fail(f"Error while searching for MAC in Profiler UI: {exc}")

    # -------------------------------------------------------------------------
    # Assertions for expected results
    # -------------------------------------------------------------------------

    # 1) No device record is created based solely on malformed DHCP packets.
    #    We expect zero records for the test MAC.
    assert device_count == 0, (
        f"Profiler incorrectly created {device_count} device record(s) for MAC "
        f"{test_mac} based solely on malformed DHCP packets."
    )

    # 2) Profiler service remains stable with no crash or restart.
    #    We cannot directly detect process crashes from the UI, but we can:
    #      - Verify the UI is still responsive.
    #      - Optionally check for 'service restart' or similar log entries.
    try:
        # Simple UI health check: ensure a known element is still interactable
        await page.click("nav >> text=Dashboard")
        await page.wait_for_selector("data-test-id=dashboard-root", timeout=15000)
    except PlaywrightError as exc:
        pytest.fail(
            "Profiler UI became unresponsive after sending malformed DHCP "
            f"packets, indicating a potential service crash or restart: {exc}"
        )

    # Optional: check logs for restart indicators within a short window
    restart_keywords = ["service restarted", "profiler restarted", "crash"]
    recent_window_start = datetime.utcnow() - timedelta(minutes=5)
    recent_logs = await fetch_profiler_logs_since(
        page, since_timestamp=recent_window_start
    )
    recent_logs_joined = "\n".join(recent_logs).lower()

    has_restart_indication = any(
        keyword in recent_logs_joined for keyword in restart_keywords
    )

    assert not has_restart_indication, (
        "Profiler logs indicate a service restart or crash after malformed DHCP "
        f"packet injection. Logs inspected:\n{recent_logs_joined}"
    )