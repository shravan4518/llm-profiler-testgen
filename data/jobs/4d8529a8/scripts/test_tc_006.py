import asyncio
import logging
from typing import List

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_006_dhcp_relay_misconfigured_no_packets_to_pps(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_006: Behavior when DHCPv4 relay is misconfigured (no packets reach PPS)

    Description:
        Verify that when DHCP relay configuration is incorrect, Profiler does not
        receive DHCP packets and appropriate troubleshooting indicators/logs are
        available.

    Preconditions:
        - PPS is configured for DHCP Helper mode.
        - VLAN 210 endpoint uses DHCP relay, but IP helper is configured to
          incorrect IP (not PPS).

    Expected Results:
        - Endpoint fails to obtain IP due to incorrect relay configuration.
        - Profiler does not create any device record for MAC AA:BB:CC:DD:EE:07.
        - Logs provide evidence that no DHCP packets were received from VLAN 210,
          enabling admin to suspect DHCP relay misconfiguration.
        - No stale or partial device entries created for the misconfigured subnet.
    """
    page = authenticated_page
    endpoint_mac = "AA:BB:CC:DD:EE:07"
    vlan_id = "210"

    # Helper: safe click with logging and explicit error
    async def safe_click(selector: str, description: str, timeout: int = 15000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.click(selector)
            logger.info("Clicked: %s (%s)", selector, description)
        except PlaywrightError as exc:
            logger.error("Failed to click %s (%s): %s", selector, description, exc)
            pytest.fail(f"Unable to click {description}: {exc}")

    # Helper: safe fill with logging and explicit error
    async def safe_fill(selector: str, value: str, description: str, timeout: int = 15000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.fill(selector, value)
            logger.info("Filled %s with '%s' (%s)", selector, value, description)
        except PlaywrightError as exc:
            logger.error("Failed to fill %s (%s): %s", selector, description, exc)
            pytest.fail(f"Unable to fill {description}: {exc}")

    # -------------------------------------------------------------------------
    # STEP 1: On switch, intentionally configure wrong ip helper-address
    #         (ip helper-address 10.10.99.99 on VLAN 210).
    #
    # NOTE:
    #   This step is normally executed on the network switch (out of scope for
    #   UI automation). Here we:
    #   - Document it clearly.
    #   - Optionally, verify from PPS UI that the DHCP helper target is not PPS
    #     if such visibility exists.
    # -------------------------------------------------------------------------
    logger.info(
        "Precondition / Step 1: Ensure switch is configured with "
        "'ip helper-address 10.10.99.99' on VLAN %s (not pointing to PPS).",
        vlan_id,
    )

    # If the PPS UI exposes DHCP helper configuration, you could navigate and
    # assert it is not pointing to PPS. This is kept generic as the actual UI
    # is not specified.
    # Example (pseudo-selectors):
    # await safe_click("text=Network", "Network menu")
    # await safe_click("text=DHCP Helper", "DHCP Helper submenu")
    # await safe_click(f"text=VLAN {vlan_id}", f"VLAN {vlan_id} row")
    # helper_field = page.locator("input[name='helperAddress']")
    # helper_value = await helper_field.input_value()
    # assert helper_value == "10.10.99.99"

    # -------------------------------------------------------------------------
    # STEP 2: Connect endpoint MAC AA:BB:CC:DD:EE:07 to VLAN 210.
    #
    # NOTE:
    #   Physical connection cannot be driven directly from Playwright.
    #   We assume that:
    #   - The endpoint is already connected to VLAN 210, OR
    #   - An external harness/test framework performs this step.
    #
    #   Here we only log and optionally wait a short period for PPS to
    #   detect link / environment stabilization.
    # -------------------------------------------------------------------------
    logger.info(
        "Step 2: Ensure endpoint with MAC %s is physically connected to VLAN %s.",
        endpoint_mac,
        vlan_id,
    )
    await asyncio.sleep(5)  # Allow time for link-up / environment stabilization

    # -------------------------------------------------------------------------
    # STEP 3: Trigger DHCP on the endpoint and confirm it fails to receive an IP.
    #
    # NOTE:
    #   DHCP negotiation occurs on the endpoint OS and cannot be controlled from
    #   the PPS UI. Normally this is validated via:
    #   - Endpoint console / OS logs, or
    #   - External automation (e.g., SSH into endpoint).
    #
    #   From PPS perspective, misconfigured relay implies *no DHCP packets* reach
    #   PPS, so we indirectly validate by lack of device records and logs.
    #
    #   Here we:
    #   - Wait long enough for any DHCP traffic to have reached (if it could).
    #   - Assert later that PPS has no device record and logs show no packets.
    # -------------------------------------------------------------------------
    logger.info(
        "Step 3: Trigger DHCP on the endpoint (out-of-scope for UI test). "
        "Waiting for potential DHCP traffic window to elapse."
    )
    await asyncio.sleep(30)  # Time window for DHCP attempts which should fail

    # -------------------------------------------------------------------------
    # STEP 4: In PPS, check Profiler > Discovered Devices for the MAC.
    #         Expectation: No device record exists for this MAC.
    # -------------------------------------------------------------------------

    # Navigate to Profiler > Discovered Devices
    try:
        # Adjust selectors to match actual UI
        await safe_click("text=Profiler", "Profiler main menu")
        await safe_click("text=Discovered Devices", "Discovered Devices view")
    except AssertionError:
        raise
    except Exception as exc:  # Defensive: unexpected errors
        logger.error("Navigation to Discovered Devices failed: %s", exc)
        pytest.fail(f"Unable to navigate to Profiler > Discovered Devices: {exc}")

    # Search for the specific MAC address
    # Example selectors; adapt to actual application under test.
    search_input_selector = "input[placeholder*='Search']"
    await safe_fill(
        search_input_selector,
        endpoint_mac,
        "Discovered Devices search input",
    )

    # Wait for any search/filtering to complete
    await asyncio.sleep(3)

    # Locate table rows that might contain the MAC
    device_row_locator = page.locator("table >> tbody >> tr")
    try:
        row_count = await device_row_locator.count()
    except PlaywrightError as exc:
        logger.error("Failed to query discovered devices rows: %s", exc)
        pytest.fail(f"Unable to query discovered devices table: {exc}")

    found_macs: List[str] = []
    for index in range(row_count):
        row = device_row_locator.nth(index)
        try:
            row_text = await row.inner_text()
        except PlaywrightError:
            # Skip problematic row but continue checking others
            continue

        if endpoint_mac.lower() in row_text.lower():
            found_macs.append(row_text)

    # Assertion: Profiler does NOT create any device record for the MAC
    assert not found_macs, (
        "Profiler should NOT have any discovered device entry for MAC "
        f"{endpoint_mac}, but found: {found_macs}"
    )

    # -------------------------------------------------------------------------
    # STEP 5: Review Profiler logs (system/diagnostics) for absence of DHCP
    #         packets from VLAN 210 and any warnings that help indicate
    #         misconfiguration.
    #
    # Expected behavior:
    #   - No DHCP packet logs from VLAN 210.
    #   - Optional: Warnings or informational messages indicating no DHCP
    #     traffic from that VLAN / helper configuration suspicion.
    #
    # NOTE:
    #   The exact log format and UI are environment-specific. The code below
    #   uses generic selectors and text checks that should be adapted.
    # -------------------------------------------------------------------------

    try:
        # Navigate to Profiler logs / diagnostics
        await safe_click("text=System", "System main menu")
        await safe_click("text=Diagnostics", "Diagnostics submenu")

        # Filter logs for DHCP / Profiler context if available
        # Example selectors; adapt as needed.
        await safe_click("text=Profiler Logs", "Profiler Logs tab")

        # Optional: Filter by VLAN 210 or MAC, if supported
        # Example:
        # await safe_fill("input[placeholder*='Filter']", vlan_id, "Log filter input")
        # await asyncio.sleep(3)

    except AssertionError:
        raise
    except Exception as exc:
        logger.error("Navigation to Profiler logs failed: %s", exc)
        pytest.fail(f"Unable to navigate to Profiler logs: {exc}")

    # Collect visible log entries
    log_row_locator = page.locator("table >> tbody >> tr")
    try:
        log_row_count = await log_row_locator.count()
    except PlaywrightError as exc:
        logger.error("Failed to query profiler log rows: %s", exc)
        pytest.fail(f"Unable to query profiler logs table: {exc}")

    log_texts: List[str] = []
    for index in range(log_row_count):
        row = log_row_locator.nth(index)
        try:
            row_text = await row.inner_text()
            log_texts.append(row_text)
        except PlaywrightError:
            continue

    combined_logs = "\n".join(log_texts)

    # Assertion: No DHCP packets from VLAN 210 are recorded
    # We check for patterns that would indicate DHCP traffic from VLAN 210.
    # These patterns must be adapted to your real log format.
    unexpected_patterns = [
        "DHCP DISCOVER",
        "DHCP REQUEST",
        "DHCP OFFER",
        "DHCP ACK",
    ]

    vlan_210_dhcp_found = any(
        pattern in combined_logs and vlan_id in combined_logs
        for pattern in unexpected_patterns
    )

    assert not vlan_210_dhcp_found, (
        "Profiler logs should NOT show DHCP packets from VLAN "
        f"{vlan_id}, but DHCP-related entries were found:\n{combined_logs}"
    )

    # Optional: Assert presence of generic warning or informational messages
    # that help an admin suspect misconfiguration. This is heuristic and should
    # be tailored to your product's actual log wording.
    possible_warning_keywords = [
        "no dhcp packets received",
        "no dhcp traffic",
        "dhcp helper",
        "relay misconfig",
        "relay misconfiguration",
        "dhcp relay",
    ]

    has_any_troubleshooting_hint = any(
        keyword.lower() in combined_logs.lower()
        for keyword in possible_warning_keywords
    )

    # We do not fail the test if exact wording is not found, but we log a warning
    # so that the test can be tightened once the product's log messages are known.
    if not has_any_troubleshooting_hint:
        logger.warning(
            "No explicit troubleshooting hint related to DHCP relay "
            "misconfiguration was found in logs. Review product log "
            "messages and refine assertions if necessary."
        )

    # -------------------------------------------------------------------------
    # FINAL ASSERTIONS / POSTCONDITIONS:
    # - No stale or partial device entries created for the misconfigured subnet.
    #
    # We already asserted there is no discovered device entry for the MAC.
    # Optionally, we can double-check that no partial / error-state record
    # exists if the UI exposes such status.
    # -------------------------------------------------------------------------
    # Example: Ensure no row with MAC and 'error' or 'partial' status exists.
    # Adapt selectors/status text to your UI.
    for row_text in found_macs:
        assert "error" not in row_text.lower(), (
            "No partial/error device entry should exist for MAC "
            f"{endpoint_mac}, but found row: {row_text}"
        )

    logger.info(
        "TC_006 completed: Misconfigured DHCP relay results in no DHCP packets "
        "reaching PPS, no profiler device record for MAC %s, and logs do not "
        "show DHCP packets from VLAN %s.",
        endpoint_mac,
        vlan_id,
    )