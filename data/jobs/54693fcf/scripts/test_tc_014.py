import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


MAC_ADDRESS = "FE:ED:FA:CE:12:34"
EXPECTED_HOSTNAME = "lab-win10-01"
EXPECTED_OS = "Windows 10"

# Adjust these selectors/URLs to match the actual Profiler UI
DEVICE_ATTRIBUTE_SERVER_URL = "https://10.34.50.201/device-attribute-server"
INVENTORY_URL = "https://10.34.50.201/inventory/endpoints"
ENDPOINT_SEARCH_INPUT = "input[data-testid='endpoint-search']"
ENDPOINT_TABLE_ROW = "tr[data-testid='endpoint-row']"
ENDPOINT_DETAILS_LINK = "a[data-testid='endpoint-details']"
ENDPOINT_HOSTNAME_FIELD = "[data-testid='endpoint-hostname']"
ENDPOINT_OS_FIELD = "[data-testid='endpoint-os']"
ENDPOINT_DATASOURCES_FIELD = "[data-testid='endpoint-datasources']"

# Polling configuration
ATTRIBUTE_POLL_INTERVAL_MINUTES = 15
ATTRIBUTE_POLL_BUFFER_MINUTES = 5
ENDPOINT_CREATION_TIMEOUT_SECONDS = 180  # time to wait for trap-based discovery
ATTRIBUTE_ENRICHMENT_TIMEOUT_SECONDS = (
    ATTRIBUTE_POLL_INTERVAL_MINUTES + ATTRIBUTE_POLL_BUFFER_MINUTES
) * 60


@pytest.mark.asyncio
async def test_snmp_trap_discovery_with_device_attribute_server_integration(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_014: Verify integration of SNMP trap-based discovery with Device Attribute Server.

    This test validates that:
    - An endpoint discovered via SNMP trap-based discovery is created in Profiler.
    - After the Device Attribute Server polling interval elapses, the endpoint record
      is enriched with hostname and OS attributes from the Device Attribute Server.
    - Data sources / logs indicate that the attribute enrichment originated from the
      Device Attribute Server.

    Pre-requisites:
    - Profiler is configured with Device Attribute Server (e.g., PPS controller).
    - Polling interval for attribute server is set to 15 minutes.
    - Profiler SNMP trap-based discovery is active.
    """
    page = authenticated_page

    # -------------------------------------------------------------------------
    # Step 1: Ensure Device Attribute Server is reachable and has MAC entry
    # -------------------------------------------------------------------------
    try:
        await page.goto(DEVICE_ATTRIBUTE_SERVER_URL, wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open Device Attribute Server configuration page: {exc}")

    # NOTE: The following selectors are placeholders and should be adapted to
    # the actual Device Attribute Server configuration UI.
    mac_entry_row = page.locator(
        f"tr[data-testid='das-mac-row'][data-mac='{MAC_ADDRESS}']"
    )

    if not await mac_entry_row.is_visible():
        pytest.fail(
            f"Device Attribute Server does not have required MAC entry {MAC_ADDRESS}. "
            "Ensure test data is configured before running this test."
        )

    # -------------------------------------------------------------------------
    # Step 2: Confirm MAC is not yet in Profiler inventory
    # -------------------------------------------------------------------------
    try:
        await page.goto(INVENTORY_URL, wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open Profiler inventory page: {exc}")

    # Search for the MAC in inventory
    await page.fill(ENDPOINT_SEARCH_INPUT, MAC_ADDRESS)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)  # small wait for results to render

    endpoint_row = page.locator(
        f"{ENDPOINT_TABLE_ROW}[data-mac='{MAC_ADDRESS}']"
    )

    if await endpoint_row.is_visible():
        pytest.skip(
            f"Endpoint with MAC {MAC_ADDRESS} already exists in inventory. "
            "This test expects a clean state (no pre-existing endpoint)."
        )

    # -------------------------------------------------------------------------
    # Step 3: Connect endpoint to managed switch port to generate SNMP trap
    # -------------------------------------------------------------------------
    # This step is performed externally (e.g., via lab automation or manual action).
    # The test will wait for the endpoint to appear in inventory as a result of
    # the SNMP linkUp trap.
    #
    # NOTE: If you have an API or script to trigger the trap, it can be invoked here.
    # For now, we only document and rely on the external action.

    # -------------------------------------------------------------------------
    # Step 4: Verify Profiler creates endpoint entry quickly after receiving trap
    # -------------------------------------------------------------------------
    endpoint_creation_deadline = datetime.utcnow() + timedelta(
        seconds=ENDPOINT_CREATION_TIMEOUT_SECONDS
    )

    endpoint_created = False
    while datetime.utcnow() < endpoint_creation_deadline:
        try:
            await page.goto(INVENTORY_URL, wait_until="networkidle")
        except PlaywrightError as exc:
            pytest.fail(f"Failed to refresh inventory page: {exc}")

        await page.fill(ENDPOINT_SEARCH_INPUT, MAC_ADDRESS)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

        if await endpoint_row.is_visible():
            endpoint_created = True
            break

        # Poll every 10 seconds until timeout
        await asyncio.sleep(10)

    assert endpoint_created, (
        f"Endpoint with MAC {MAC_ADDRESS} was not created in inventory within "
        f"{ENDPOINT_CREATION_TIMEOUT_SECONDS} seconds after SNMP trap."
    )

    # Additional assertion: ensure the endpoint is marked as trap-discovered
    # Placeholder selector/attribute, adjust to actual UI representation
    trap_badge = endpoint_row.locator("[data-testid='discovery-source-trap']")
    assert await trap_badge.is_visible(), (
        "Endpoint entry exists but is not marked as discovered via SNMP trap."
    )

    # -------------------------------------------------------------------------
    # Step 5: Wait until Device Attribute Server polling interval + buffer
    # -------------------------------------------------------------------------
    # We wait for the attribute polling cycle to run and then enrich the endpoint.
    await asyncio.sleep(ATTRIBUTE_ENRICHMENT_TIMEOUT_SECONDS)

    # -------------------------------------------------------------------------
    # Step 6: Open endpoint details and review collected attributes
    # -------------------------------------------------------------------------
    try:
        await page.goto(INVENTORY_URL, wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open inventory page before inspecting endpoint: {exc}")

    await page.fill(ENDPOINT_SEARCH_INPUT, MAC_ADDRESS)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)

    # Ensure endpoint is still present
    assert await endpoint_row.is_visible(), (
        f"Endpoint with MAC {MAC_ADDRESS} is no longer present in inventory."
    )

    # Open details view
    details_link = endpoint_row.locator(ENDPOINT_DETAILS_LINK)
    try:
        await details_link.click()
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open endpoint details for MAC {MAC_ADDRESS}: {exc}")

    # -------------------------------------------------------------------------
    # Expected Result 1:
    # Endpoint entry is created via trap-based discovery (already asserted above).
    # -------------------------------------------------------------------------

    # -------------------------------------------------------------------------
    # Expected Result 2:
    # After attribute server polling, endpoint record is populated with hostname
    # `lab-win10-01` and OS `Windows 10`.
    # -------------------------------------------------------------------------
    hostname_field = page.locator(ENDPOINT_HOSTNAME_FIELD)
    os_field = page.locator(ENDPOINT_OS_FIELD)

    assert await hostname_field.is_visible(), "Hostname field is not visible."
    assert await os_field.is_visible(), "OS field is not visible."

    hostname_value = (await hostname_field.inner_text()).strip()
    os_value = (await os_field.inner_text()).strip()

    assert hostname_value == EXPECTED_HOSTNAME, (
        f"Hostname enrichment mismatch. Expected '{EXPECTED_HOSTNAME}', "
        f"got '{hostname_value}'."
    )
    assert os_value == EXPECTED_OS, (
        f"OS enrichment mismatch. Expected '{EXPECTED_OS}', got '{os_value}'."
    )

    # -------------------------------------------------------------------------
    # Expected Result 3:
    # Data sources/logs show attribute enrichment from Device Attribute Server.
    # -------------------------------------------------------------------------
    # Placeholder: data sources or logs indicator in UI
    datasources_field = page.locator(ENDPOINT_DATASOURCES_FIELD)
    assert await datasources_field.is_visible(), (
        "Data sources field is not visible in endpoint details."
    )

    datasources_text = (await datasources_field.inner_text()).lower()
    assert "device attribute server" in datasources_text or "attribute server" in datasources_text, (
        "Endpoint data sources do not indicate enrichment from Device Attribute Server."
    )

    # -------------------------------------------------------------------------
    # Postcondition:
    # Endpoint remains in inventory with both trap and attribute server data.
    # -------------------------------------------------------------------------
    # Re-check in inventory to ensure the endpoint is still present with enriched data
    try:
        await page.goto(INVENTORY_URL, wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reopen inventory page for postcondition check: {exc}")

    await page.fill(ENDPOINT_SEARCH_INPUT, MAC_ADDRESS)
    await page.keyboard.press("Enter")
    await page.wait_for_timeout(2000)

    assert await endpoint_row.is_visible(), (
        "Postcondition failed: endpoint is not present in inventory."
    )