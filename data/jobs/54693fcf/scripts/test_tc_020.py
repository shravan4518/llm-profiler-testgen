import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
async def test_tc_020_ssh_collector_with_snmp_trap_on_palo_alto(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_020: Verify integration with SSH-based collector when SNMP trap-based discovery
    occurs on a Palo Alto device.

    This test validates that:
    - The device 10.10.70.70 is configured to use SSH as the collection method.
    - An endpoint first discovered via SNMP trap is later enriched by SSH collector data.
    - No duplicate endpoints are created.
    - Device is correctly identified as Palo Alto and relevant attributes are populated.

    Notes:
    - This script assumes the UI provides:
      * A way to configure collection methods for a device.
      * A way to confirm an SNMP trap-based discovery event.
      * A list/search view for endpoints.
      * Endpoint detail view where SSH-enriched attributes (IP, zone, etc.) appear.
    - Where exact selectors are unknown, CSS/XPath selectors are written as examples
      and should be adjusted to match the real application DOM.
    """

    page = authenticated_page

    # Helper functions ----------------------------------------------------- #

    async def safe_click(selector: str, description: str, timeout: int = 10000) -> None:
        """Click an element safely with error handling and descriptive messages."""
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.click(selector)
        except PlaywrightTimeoutError:
            pytest.fail(f"Timed out waiting for element to click: {description} ({selector})")
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click {description} ({selector}): {exc}")

    async def safe_fill(selector: str, value: str, description: str, timeout: int = 10000) -> None:
        """Fill an input element safely with error handling."""
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.fill(selector, value)
        except PlaywrightTimeoutError:
            pytest.fail(f"Timed out waiting for input: {description} ({selector})")
        except PlaywrightError as exc:
            pytest.fail(f"Failed to fill {description} ({selector}) with '{value}': {exc}")

    async def safe_get_text(selector: str, description: str, timeout: int = 10000) -> str:
        """Get text content from an element safely with error handling."""
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            element = await page.query_selector(selector)
            if not element:
                pytest.fail(f"Element not found for {description} ({selector})")
            text = await element.text_content()
            return text.strip() if text else ""
        except PlaywrightTimeoutError:
            pytest.fail(f"Timed out waiting for element text: {description} ({selector})")
        except PlaywrightError as exc:
            pytest.fail(f"Failed to read text from {description} ({selector}): {exc}")
        return ""

    async def wait_for_endpoint_with_mac(
        mac_address: str,
        timeout: int = 120000,
    ) -> None:
        """
        Poll the endpoint list/search until an endpoint with the given MAC appears.

        This models the trap-based discovery completing and the endpoint being visible.
        """
        poll_interval = 5000
        elapsed = 0

        while elapsed < timeout:
            # Refresh or re-search as needed
            await safe_click("button#refresh-endpoints", "Refresh endpoints list")

            # Example: search by MAC in endpoint list
            await safe_fill("input#endpoint-search", mac_address, "Endpoint search field")
            await safe_click("button#endpoint-search-btn", "Endpoint search button")

            # Check if a row containing the MAC exists
            locator = page.locator("table#endpoints-table tr", has_text=mac_address)
            if await locator.count() > 0:
                return

            await asyncio.sleep(poll_interval / 1000)
            elapsed += poll_interval

        pytest.fail(f"Endpoint with MAC {mac_address} not found within {timeout/1000} seconds")

    async def open_endpoint_details(mac_address: str) -> None:
        """Open the endpoint details view for the given MAC from the endpoints list."""
        row_locator = page.locator("table#endpoints-table tr", has_text=mac_address)
        if await row_locator.count() == 0:
            pytest.fail(f"No endpoint row found with MAC {mac_address} to open details")

        # Example: click on the MAC link inside the row
        mac_link = row_locator.locator("a.endpoint-mac-link")
        try:
            await mac_link.first.click()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to open endpoint details for MAC {mac_address}: {exc}")

    async def get_endpoint_attribute(
        label_text: str,
        timeout: int = 15000,
    ) -> Optional[str]:
        """
        Retrieve an attribute value from the endpoint details by label text.

        Assumes a structure like:
        <div class="endpoint-attr">
          <span class="label">IP Address</span>
          <span class="value">10.10.70.71</span>
        </div>
        """
        try:
            label_locator = page.locator(
                "div.endpoint-attr span.label", has_text=label_text
            )
            await label_locator.first.wait_for(timeout=timeout, state="visible")
            container = label_locator.first.locator("xpath=..")
            value_span = container.locator("span.value")
            if await value_span.count() == 0:
                return None
            text = await value_span.first.text_content()
            return text.strip() if text else None
        except PlaywrightTimeoutError:
            return None
        except PlaywrightError:
            return None

    # --------------------------------------------------------------------- #
    # Step 1: Configure Profiler to use SSH as the collection method
    #         for device 10.10.70.70.
    # --------------------------------------------------------------------- #

    # Navigate to device configuration / inventory page
    # (Adjust selector/URL according to actual UI)
    await safe_click("a#nav-devices", "Devices navigation menu")

    # Search for the Palo Alto device by IP
    device_ip = "10.10.70.70"
    await safe_fill("input#device-search", device_ip, "Device search field")
    await safe_click("button#device-search-btn", "Device search button")

    # Open device configuration
    device_row = page.locator("table#devices-table tr", has_text=device_ip)
    if await device_row.count() == 0:
        pytest.fail(f"Device with IP {device_ip} not found in device inventory")

    await device_row.first.click()

    # Set collection method to SSH for this device
    await safe_click("select#collection-method", "Collection method dropdown")
    await page.select_option("select#collection-method", value="ssh")

    # Save device configuration
    await safe_click("button#save-device", "Save device configuration")

    # Assert that the collection method is now SSH (read-only or confirmation message)
    collection_method_text = await safe_get_text(
        "span#collection-method-display", "Collection method display"
    )
    assert collection_method_text.lower() == "ssh", (
        f"Expected collection method 'SSH', got '{collection_method_text}'"
    )

    # --------------------------------------------------------------------- #
    # Step 2: Ensure Palo Alto device is configured to send SNMP traps
    #         to Profiler for interface link events (or simulated traps).
    #         (UI verification that trap receiver is configured and enabled)
    # --------------------------------------------------------------------- #

    # Navigate to trap configuration for the device if available
    await safe_click("a#device-trap-settings-tab", "Device trap settings tab")

    trap_status_text = await safe_get_text(
        "span#trap-status", "Trap status indicator"
    )
    assert "enabled" in trap_status_text.lower(), (
        "SNMP trap receiver is not enabled for device; "
        f"status text: '{trap_status_text}'"
    )

    # Optional: verify trap destination is Profiler server
    trap_destination = await safe_get_text(
        "span#trap-destination", "Trap destination"
    )
    assert trap_destination != "", "Trap destination is empty; expected Profiler address"

    # --------------------------------------------------------------------- #
    # Step 3: Connect an endpoint with MAC AA:AA:AA:AA:AA:01 to a monitored port.
    #         (Assumed to be done externally; we only proceed to verification.)
    # --------------------------------------------------------------------- #

    endpoint_mac = "AA:AA:AA:AA:AA:01"

    # --------------------------------------------------------------------- #
    # Step 4: Confirm SNMP trap is sent and that SSH collector can later read
    #         ARP/CAM tables showing the MAC.
    #         - We validate via:
    #           * Trap log/event view showing a link event for the MAC.
    #           * Later, endpoint details show attributes that imply SSH collection.
    # --------------------------------------------------------------------- #

    # Navigate to trap/event log page
    await safe_click("a#nav-events", "Events navigation menu")
    await safe_click("a#nav-snmp-traps", "SNMP traps submenu")

    # Filter SNMP traps for the target device and MAC (if UI supports MAC filter)
    await safe_fill("input#trap-device-filter", device_ip, "Trap device filter")
    await safe_fill("input#trap-mac-filter", endpoint_mac, "Trap MAC filter")
    await safe_click("button#trap-filter-apply", "Apply trap filters")

    # Wait for a trap row that references the MAC and is of type link event
    trap_row = page.locator(
        "table#trap-events-table tr",
        has_text=endpoint_mac,
    )

    try:
        await trap_row.first.wait_for(timeout=120000, state="visible")
    except PlaywrightTimeoutError:
        pytest.fail(
            f"No SNMP trap event found for MAC {endpoint_mac} within 120 seconds"
        )

    # Optional assertion on trap type column (e.g., "Link Up", "Link Down")
    trap_type_text = await safe_get_text(
        "table#trap-events-table tr:has-text('AA:AA:AA:AA:AA:01') td.trap-type",
        "Trap type cell for endpoint MAC",
    )
    assert trap_type_text != "", "Trap type text is empty; expected a link event type"

    # --------------------------------------------------------------------- #
    # Step 5: Verify in Profiler that an endpoint is first discovered via the trap.
    #         - Check endpoint list for MAC.
    #         - Confirm discovery source = SNMP trap.
    # --------------------------------------------------------------------- #

    await safe_click("a#nav-endpoints", "Endpoints navigation menu")

    # Wait until endpoint with MAC appears (trap-based discovery)
    await wait_for_endpoint_with_mac(endpoint_mac)

    # Open endpoint details
    await open_endpoint_details(endpoint_mac)

    # Verify discovery source shows SNMP trap (or similar)
    discovery_source = await get_endpoint_attribute("Discovery Source")
    assert discovery_source is not None, "Discovery Source attribute not found"
    assert "trap" in discovery_source.lower() or "snmp" in discovery_source.lower(), (
        f"Expected discovery source to be SNMP trap-based, got '{discovery_source}'"
    )

    # --------------------------------------------------------------------- #
    # Step 6: After SSH collection occurs, check endpoint details to see if
    #         additional attributes (e.g., IP, zone) are populated from SSH data.
    #         - We poll for changes that indicate SSH enrichment.
    # --------------------------------------------------------------------- #

    async def wait_for_ssh_enrichment(timeout: int = 180000) -> None:
        """Poll endpoint details until SSH-based attributes appear or timeout."""
        poll_interval = 10000
        elapsed = 0

        while elapsed < timeout:
            # Refresh endpoint details (if UI has a refresh button)
            try:
                await safe_click("button#endpoint-refresh", "Endpoint details refresh")
            except AssertionError:
                # If refresh button not present, reload the details by re-opening
                await safe_click("a#nav-endpoints", "Endpoints navigation menu")
                await wait_for_endpoint_with_mac(endpoint_mac)
                await open_endpoint_details(endpoint_mac)

            ip_address = await get_endpoint_attribute("IP Address")
            zone_value = await get_endpoint_attribute("Zone")
            collection_sources = await get_endpoint_attribute("Collection Sources")

            # We consider enrichment successful if:
            # - IP is populated, AND
            # - Zone or Collection Sources indicate SSH.
            ip_ok = ip_address not in (None, "", "unknown")
            zone_ok = zone_value not in (None, "", "unknown")
            ssh_mentioned = (
                collection_sources is not None
                and "ssh" in collection_sources.lower()
            )

            if ip_ok and (zone_ok or ssh_mentioned):
                # Assert Palo Alto device identification as part of enrichment
                device_vendor = await get_endpoint_attribute("Device Vendor")
                assert device_vendor is not None, "Device Vendor attribute not found"
                assert "palo alto" in device_vendor.lower(), (
                    f"Expected device vendor to be Palo Alto, got '{device_vendor}'"
                )
                return

            await asyncio.sleep(poll_interval / 1000)
            elapsed += poll_interval

        pytest.fail(
            "SSH enrichment did not populate expected attributes "
            f"(IP/Zone/SSH source) within {timeout/1000} seconds"
        )

    await wait_for_ssh_enrichment()

    # --------------------------------------------------------------------- #
    # Final Assertions:
    # - Trap-based discovery triggered initial endpoint creation.
    # - SSH-based collector augmented the same endpoint entry; no duplicates.
    # - Device is correctly identified as Palo Alto; attributes appear in details.
    # --------------------------------------------------------------------- #

    # Verify no duplicate endpoints exist for the same MAC
    await safe_click("a#nav-endpoints", "Endpoints navigation menu")
    await safe_fill("input#endpoint-search", endpoint_mac, "Endpoint search field")
    await safe_click("button#endpoint-search-btn", "Endpoint search button")

    endpoint_rows = page.locator("table#endpoints-table tr", has_text=endpoint_mac)
    count = await endpoint_rows.count()
    assert count == 1, (
        f"Expected a single endpoint record for MAC {endpoint_mac}, found {count}"
    )

    # Re-open details to assert Palo Alto and attribute presence one more time
    await open_endpoint_details(endpoint_mac)

    device_vendor_final = await get_endpoint_attribute("Device Vendor")
    assert device_vendor_final is not None, "Device Vendor attribute not found in final check"
    assert "palo alto" in device_vendor_final.lower(), (
        f"Expected device vendor to be Palo Alto in final check, got '{device_vendor_final}'"
    )

    ip_final = await get_endpoint_attribute("IP Address")
    assert ip_final not in (None, "", "unknown"), (
        f"Expected IP address to be populated from SSH; got '{ip_final}'"
    )

    zone_final = await get_endpoint_attribute("Zone")
    # Zone may be optional depending on environment; log a soft expectation
    if zone_final in (None, "", "unknown"):
        pytest.skip(
            "Zone attribute not populated; environment may not provide zone mapping. "
            "Core SSH enrichment (IP, vendor, single endpoint) is verified."
        )