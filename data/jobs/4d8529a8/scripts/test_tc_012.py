import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_012_integration_dhcp_helper_cdp_lldp_profiler(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_012: Integration – Switch configuration for DHCP Helper and CDP/LLDP
    does not break DHCP fingerprinting.

    This test verifies that enabling additional switch features (CDP/LLDP and
    SNMP for Profiler) does not interfere with DHCP packet forwarding and
    fingerprinting, and that DHCP-based fingerprint data coexists with
    SNMP/CDP/LLDP-based data in the device record.

    Prerequisites (assumed satisfied outside UI where needed):
    - Switch configured with IP helper to PPS, CDP/LLDP enabled, and SNMP to PPS.
    - Profiler SNMP collector enabled.
    """

    page: Page = authenticated_page
    endpoint_mac = "AA:BB:CC:DD:EE:11"

    # Helper functions
    async def safe_click(selector: str, description: str, timeout: int = 10000) -> None:
        """Safely click an element and raise a clear error if it fails."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.click(selector)
            logger.info("Clicked: %s (%s)", selector, description)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to click {description} using selector '{selector}': {exc}"
            ) from exc

    async def safe_fill(selector: str, value: str, description: str, timeout: int = 10000) -> None:
        """Safely fill an input element."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.fill(selector, value)
            logger.info("Filled %s with '%s' (%s)", selector, value, description)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to fill {description} using selector '{selector}': {exc}"
            ) from exc

    async def safe_text_content(
        selector: str,
        description: str,
        timeout: int = 10000,
    ) -> Optional[str]:
        """Safely get text content of an element."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            text = await page.text_content(selector)
            logger.info("Read text from %s (%s): %s", selector, description, text)
            return text.strip() if text else None
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to read text for {description} using selector '{selector}': {exc}"
            ) from exc

    # ----------------------------------------------------------------------
    # Step 1: Configure switch according to documentation (UI side for SNMP/NID)
    # ----------------------------------------------------------------------
    # Note: Physical switch configuration (IP helper, CDP/LLDP on ports, SNMP
    # on the switch) is assumed to be done outside this test. Here we only
    # validate and configure the PPS-side settings that relate to the switch.

    # Navigate to Network Infrastructure Devices (NID) / Switch configuration page
    # (Selectors are placeholders and should be updated to match the real UI.)
    await page.goto("https://npre-miiqa2mp-eastus2.openai.azure.com/pps/network-devices")

    # Verify that the NID page loaded
    nid_page_header_selector = "h1:has-text('Network Infrastructure Devices')"
    await page.wait_for_selector(nid_page_header_selector, state="visible", timeout=15000)

    # ----------------------------------------------------------------------
    # Step 2: In PPS, configure Network Infrastructure Device entry for the switch
    # ----------------------------------------------------------------------
    # Create or edit the switch entry with SNMP settings pointing to PPS.
    # This assumes a typical "Add Device" or "Edit" flow.

    switch_name = "TC012_Test_Switch"
    switch_ip = "192.0.2.10"  # Example IP, adjust to real lab value
    snmp_community = "pps-profiler-community"

    # Try to locate existing switch row by name; if not present, add new.
    switch_row_selector = f"tr:has(td:text-is('{switch_name}'))"

    try:
        await page.wait_for_selector(switch_row_selector, state="visible", timeout=5000)
        # Switch exists – click Edit
        await safe_click(
            f"{switch_row_selector} button:has-text('Edit')",
            "Edit existing switch entry",
        )
    except PlaywrightError:
        # Switch does not exist – add new
        await safe_click("button:has-text('Add Device')", "Add Device button")

    # Fill in switch details in the modal/form
    await safe_fill("input[name='name']", switch_name, "Switch name")
    await safe_fill("input[name='ipAddress']", switch_ip, "Switch IP address")

    # SNMP configuration for PPS Profiler
    await safe_fill("input[name='snmpCommunity']", snmp_community, "SNMP community")
    await safe_click("select[name='role']", "Switch role dropdown")
    await safe_click("option[value='switch']", "Switch role option")

    # Enable CDP/LLDP and SNMP for Profiler if such toggles exist in the UI
    # (These are example selectors and must be aligned with actual UI.)
    try:
        await safe_click("input[name='enableCdp']", "Enable CDP checkbox")
    except AssertionError:
        logger.warning("CDP enable control not found; skipping CDP enable step.")

    try:
        await safe_click("input[name='enableLldp']", "Enable LLDP checkbox")
    except AssertionError:
        logger.warning("LLDP enable control not found; skipping LLDP enable step.")

    try:
        await safe_click("input[name='enableProfilerSnmp']", "Enable Profiler SNMP checkbox")
    except AssertionError:
        logger.warning(
            "Profiler SNMP enable control not found; "
            "assuming Profiler SNMP collector already enabled."
        )

    # Save the switch configuration
    await safe_click("button:has-text('Save')", "Save switch configuration")

    # Confirm the switch appears in the list with correct name and IP
    await page.wait_for_selector(switch_row_selector, state="visible", timeout=15000)
    ip_cell_selector = f"{switch_row_selector} td:nth-of-type(2)"
    ip_text = await safe_text_content(ip_cell_selector, "Switch IP cell")
    assert ip_text == switch_ip, (
        f"Configured switch IP '{switch_ip}' not reflected in UI; got '{ip_text}'."
    )

    # ----------------------------------------------------------------------
    # Step 3: Connect endpoint MAC to switch access port
    # ----------------------------------------------------------------------
    # This is a physical action and cannot be performed via UI. We assume the
    # endpoint is connected externally. Here we just log and optionally wait
    # a short period to allow link-up.
    logger.info(
        "Ensure endpoint with MAC %s is physically connected to switch access port.",
        endpoint_mac,
    )
    await asyncio.sleep(5)  # Allow some time for link to come up

    # ----------------------------------------------------------------------
    # Step 4: Trigger DHCP and allow device to be discovered
    # ----------------------------------------------------------------------
    # DHCP trigger is also external. We allow time for DHCP exchange and
    # profiler discovery to complete.
    logger.info("Trigger DHCP on endpoint with MAC %s (external action).", endpoint_mac)
    discovery_wait_seconds = 60
    logger.info("Waiting %s seconds for DHCP and Profiler discovery.", discovery_wait_seconds)
    await asyncio.sleep(discovery_wait_seconds)

    # ----------------------------------------------------------------------
    # Step 5: In Profiler, view the device details for the endpoint MAC
    # ----------------------------------------------------------------------

    # Navigate to Profiler / Devices page
    await page.goto("https://npre-miiqa2mp-eastus2.openai.azure.com/pps/profiler/devices")

    profiler_header_selector = "h1:has-text('Profiler Devices')"
    await page.wait_for_selector(profiler_header_selector, state="visible", timeout=15000)

    # Search for the device by MAC address
    await safe_fill("input[placeholder='Search devices']", endpoint_mac, "Profiler device search")
    await page.keyboard.press("Enter")

    # Wait for search results to load and select the device row
    device_row_selector = f"tr:has(td:text-is('{endpoint_mac}'))"
    await page.wait_for_selector(device_row_selector, state="visible", timeout=30000)

    # Ensure there is exactly one matching row (no duplicates)
    device_rows = await page.query_selector_all(device_row_selector)
    assert len(device_rows) == 1, (
        f"Expected exactly one device record for MAC {endpoint_mac}, "
        f"found {len(device_rows)}."
    )

    # Open device details
    await safe_click(device_row_selector, "Open device details")

    # ----------------------------------------------------------------------
    # Step 6: Confirm DHCP-based fingerprint data coexists with SNMP/CDP/LLDP data
    # ----------------------------------------------------------------------

    # 6a. Assert DHCP fingerprinting data is present
    # Example selectors: adjust to match actual Profiler UI.
    dhcp_fingerprint_selector = "section#dhcp-fingerprint .fingerprint-value"
    dhcp_fingerprint_text = await safe_text_content(
        dhcp_fingerprint_selector,
        "DHCP fingerprint data",
        timeout=30000,
    )

    assert dhcp_fingerprint_text, (
        "DHCP fingerprint data is missing from device record; "
        "DHCP-based profiling may not be working."
    )

    # 6b. Assert additional device attributes from SNMP/CDP/LLDP are present
    # Switch port information
    switch_port_selector = "section#network-location .switch-port"
    switch_port_text = await safe_text_content(
        switch_port_selector,
        "Switch port attribute",
        timeout=30000,
    )
    assert switch_port_text, (
        "Switch port attribute is missing from device record; "
        "SNMP/CDP/LLDP-based location data may not be present."
    )

    # CDP/LLDP information
    cdp_lldp_selector = "section#network-location .cdp-lldp-info"
    try:
        cdp_lldp_text = await safe_text_content(
            cdp_lldp_selector,
            "CDP/LLDP information",
            timeout=15000,
        )
    except AssertionError:
        cdp_lldp_text = None
        logger.warning("CDP/LLDP info section not found in UI; skipping strict assertion.")

    assert cdp_lldp_text is not None and len(cdp_lldp_text) > 0, (
        "CDP/LLDP information is missing from device record; "
        "CDP/LLDP-based profiling data may not be present."
    )

    # 6c. Assert no duplicate or conflicting device records
    # We already asserted that only one row exists in the search results.
    # Here we add a sanity check that MAC address in details matches search key.
    details_mac_selector = "section#device-summary .mac-address"
    details_mac_text = await safe_text_content(
        details_mac_selector,
        "Device details MAC address",
        timeout=15000,
    )

    assert details_mac_text == endpoint_mac, (
        f"Device details MAC '{details_mac_text}' does not match expected '{endpoint_mac}'."
    )

    # 6d. Assert DHCP data and SNMP/CDP/LLDP data both present and not conflicting
    # Simple consistency check: ensure we have both DHCP fingerprint and
    # switch port/CDP/LLDP information simultaneously.
    assert dhcp_fingerprint_text and switch_port_text and cdp_lldp_text, (
        "DHCP fingerprinting and SNMP/CDP/LLDP data are not all present together "
        "in the device record."
    )

    # Optional: additional heuristic checks can be added here if the UI exposes
    # more structured attributes indicating data sources (e.g., 'source: DHCP',
    # 'source: SNMP', etc.).

    # ----------------------------------------------------------------------
    # Expected Results Summary Assertions
    # ----------------------------------------------------------------------

    # DHCP fingerprinting continues to work without packet loss:
    # Represented by the presence of DHCP fingerprint data for the device.
    assert dhcp_fingerprint_text, "DHCP fingerprinting appears to be broken or missing."

    # Additional device attributes (switch port, CDP/LLDP info) appear:
    assert switch_port_text, "Switch port attribute missing from device record."
    assert cdp_lldp_text, "CDP/LLDP attributes missing from device record."

    # No duplicate or conflicting device records:
    assert len(device_rows) == 1, (
        f"Found {len(device_rows)} device records for MAC {endpoint_mac}; "
        "duplicates indicate conflicting profiling data."
    )

    # Postconditions:
    # Integrated profiling with DHCP + SNMP/CDP/LLDP remains enabled.
    # This is implied by the configuration and the presence of all attributes.
    logger.info(
        "TC_012 passed: DHCP fingerprinting coexists with SNMP/CDP/LLDP data "
        "without duplicates or conflicts for MAC %s.",
        endpoint_mac,
    )