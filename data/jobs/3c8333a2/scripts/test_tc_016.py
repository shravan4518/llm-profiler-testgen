import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_016_dhcpv6_collector_forwards_ipv6_endpoints(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_016 (Integration) – verify DHCPv6 collector captures IPv6 addresses and forwards endpoint data.

    Preconditions:
        - DHCPv6 collector enabled in basic configuration.
        - DHCPv6 server configured on network.
        - Client-IPv6 obtains IPv6 via DHCPv6.
        - "Forward and Sync Endpoint Data" enabled and configured to a Controller/PPS.

    Test Steps:
        1. Ensure DHCPv6 collector and external port sniffing are enabled and saved.
        2. Connect Client-IPv6 to the monitored network segment.
        3. Force client to obtain an IPv6 address via DHCPv6.
        4. Wait for profiler discovery cycle and DAS polling.
        5. Navigate to Profiler endpoint inventory / DDR report page.
        6. Confirm endpoint with MAC 00:11:22:33:44:55 and IPv6 2001:db8:1::10 appears.
        7. Verify endpoint is forwarded/synchronized to PPS/controller.

    Expected Results:
        - DHCPv6 packets are captured by Profiler.
        - Endpoint discovered with correct MAC and IPv6 address.
        - Endpoint forwarded to configured PPS/controller.
    """

    page: Page = authenticated_page

    # Test data
    target_mac = "00:11:22:33:44:55"
    target_ipv6 = "2001:db8:1::10"

    # Helper: robust click with logging
    async def safe_click(selector: str, description: str, timeout: int = 15000) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.click(selector)
            logger.info("Clicked: %s (%s)", selector, description)
        except PlaywrightError as exc:
            logger.error("Failed to click %s (%s): %s", selector, description, exc)
            pytest.fail(f"Unable to click {description} ({selector}): {exc}")

    # Helper: wait for text in a locator (with retries)
    async def wait_for_text(
        locator_str: str,
        expected_text: str,
        description: str,
        timeout: int = 60000,
    ) -> None:
        try:
            locator = page.locator(locator_str)
            await locator.wait_for(state="visible", timeout=timeout)
            await page.wait_for_timeout(1000)  # small settle time
            text_content = (await locator.text_content()) or ""
            if expected_text not in text_content:
                logger.error(
                    "Expected text '%s' not found in %s. Actual: '%s'",
                    expected_text,
                    description,
                    text_content.strip(),
                )
                pytest.fail(
                    f"Expected text '{expected_text}' not found in {description}. "
                    f"Actual: '{text_content.strip()}'"
                )
            logger.info("Verified text '%s' in %s", expected_text, description)
        except PlaywrightError as exc:
            logger.error(
                "Error waiting for text '%s' in %s: %s",
                expected_text,
                description,
                exc,
            )
            pytest.fail(
                f"Error waiting for text '{expected_text}' in {description}: {exc}"
            )

    # Helper: generic assertion wrapper
    def assert_true(condition: bool, message: str) -> None:
        if not condition:
            logger.error("Assertion failed: %s", message)
            pytest.fail(message)
        logger.info("Assertion passed: %s", message)

    # -------------------------------------------------------------------------
    # STEP 1 – Ensure DHCPv6 collector and external port sniffing are enabled
    # -------------------------------------------------------------------------
    try:
        # NOTE: The exact navigation/menu structure will depend on the product UI.
        # The selectors below are placeholders and should be adapted to the real UI.
        # Navigate to configuration → profiler / collectors page
        await safe_click("text=Configuration", "Configuration menu")
        await safe_click("text=Profiler Settings", "Profiler settings menu")
        await safe_click("text=DHCP Collectors", "DHCP collectors tab")

        # Verify DHCPv6 collector checkbox is enabled
        dhcpv6_checkbox = page.locator("input#dhcpv6_collector_enabled")
        await dhcpv6_checkbox.wait_for(state="attached", timeout=15000)
        dhcpv6_checked = await dhcpv6_checkbox.is_checked()
        assert_true(
            dhcpv6_checked,
            "DHCPv6 collector must be enabled in configuration.",
        )

        # Verify external port sniffing is enabled
        external_sniffing_checkbox = page.locator(
            "input#external_port_sniffing_enabled"
        )
        await external_sniffing_checkbox.wait_for(state="attached", timeout=15000)
        external_sniffing_checked = await external_sniffing_checkbox.is_checked()
        assert_true(
            external_sniffing_checked,
            "External port sniffing must be enabled.",
        )

        # Save configuration if a Save/Apply button is present
        save_button = page.locator("button:has-text('Save') >> nth=0")
        if await save_button.is_visible():
            await save_button.click()
            await page.wait_for_timeout(3000)
            # Optionally verify a success message
            if await page.locator("text=Configuration saved").is_visible():
                logger.info("Configuration saved successfully.")
    except PlaywrightError as exc:
        logger.error("Failed to verify DHCPv6 collector configuration: %s", exc)
        pytest.fail(f"Step 1 failed: unable to verify DHCPv6 collector configuration: {exc}")

    # -------------------------------------------------------------------------
    # STEP 2 & 3 – Connect Client-IPv6 and force DHCPv6 renew
    # -------------------------------------------------------------------------
    # NOTE:
    # These actions are typically done outside the web UI (e.g., via lab automation,
    # SSH to client, or orchestrator). Here we assume that a separate mechanism
    # performs this and we only wait/log from the test.
    logger.info("Assuming Client-IPv6 is connected and DHCPv6 renew has been triggered.")
    # If you have an API or external hook, you could integrate it here.
    await page.wait_for_timeout(10000)  # small delay to allow DHCPv6 exchange

    # -------------------------------------------------------------------------
    # STEP 4 – Wait for profiler discovery cycle and DAS polling
    # -------------------------------------------------------------------------
    # The actual discovery interval depends on system configuration.
    # Here we wait with a reasonable upper bound and allow early exit
    # once the endpoint appears.
    discovery_timeout_sec = 180  # 3 minutes upper bound
    poll_interval_sec = 10

    logger.info(
        "Waiting up to %s seconds for profiler discovery and DAS polling.",
        discovery_timeout_sec,
    )

    # -------------------------------------------------------------------------
    # STEP 5 – Navigate to Profiler endpoint inventory / DDR report page
    # -------------------------------------------------------------------------
    try:
        await safe_click("text=Profiler", "Profiler main menu")
        await safe_click("text=Endpoints", "Endpoint inventory menu")
    except PlaywrightError as exc:
        logger.error("Failed to navigate to endpoint inventory: %s", exc)
        pytest.fail(f"Step 5 failed: unable to open endpoint inventory: {exc}")

    # -------------------------------------------------------------------------
    # STEP 6 – Confirm endpoint with MAC and IPv6 appears
    # -------------------------------------------------------------------------
    endpoint_found = False
    endpoint_row_locator: Optional[str] = None

    # Example table row locator, adjust to real DOM:
    # Assume table rows have data attributes or columns that contain MAC/IP.
    row_selector = "table#endpoint_table tbody tr"

    try:
        start_time = asyncio.get_event_loop().time()
        while True:
            # Refresh or re-query the page to get latest data
            await page.reload(wait_until="networkidle")
            await page.wait_for_selector(row_selector, timeout=30000)

            rows = page.locator(row_selector)
            row_count = await rows.count()
            logger.info("Discovered %d endpoint rows during polling.", row_count)

            for i in range(row_count):
                row = rows.nth(i)
                row_text = (await row.text_content()) or ""
                if target_mac.lower() in row_text.lower() and target_ipv6 in row_text:
                    endpoint_found = True
                    endpoint_row_locator = f"{row_selector} >> nth={i}"
                    logger.info(
                        "Found endpoint row for MAC %s and IPv6 %s",
                        target_mac,
                        target_ipv6,
                    )
                    break

            if endpoint_found:
                break

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= discovery_timeout_sec:
                break

            logger.info(
                "Endpoint not found yet. Waiting %s seconds before next poll.",
                poll_interval_sec,
            )
            await page.wait_for_timeout(poll_interval_sec * 1000)

        assert_true(
            endpoint_found,
            f"Endpoint with MAC {target_mac} and IPv6 {target_ipv6} "
            f"must appear in Profiler endpoint inventory within "
            f"{discovery_timeout_sec} seconds.",
        )

        # Additional assertions on the row contents
        if endpoint_row_locator:
            row_locator = page.locator(endpoint_row_locator)
            mac_present = target_mac.lower() in (
                (await row_locator.text_content()) or ""
            ).lower()
            ipv6_present = target_ipv6 in ((await row_locator.text_content()) or "")
            assert_true(
                mac_present,
                f"Endpoint row must contain MAC address {target_mac}.",
            )
            assert_true(
                ipv6_present,
                f"Endpoint row must contain IPv6 address {target_ipv6}.",
            )
    except PlaywrightError as exc:
        logger.error("Error while searching for endpoint in inventory: %s", exc)
        pytest.fail(f"Step 6 failed: unable to verify endpoint in inventory: {exc}")

    # -------------------------------------------------------------------------
    # STEP 7 – Verify endpoint data is forwarded/synchronized to PPS/controller
    # -------------------------------------------------------------------------
    # This section assumes PPS/controller is accessible via the same browser.
    # Replace selectors/paths with real ones for the target PPS system.
    try:
        # Open PPS/Controller UI in a new tab for isolation
        pps_context = await browser.new_context(ignore_https_errors=True)
        pps_page = await pps_context.new_page()

        # The URL is provided in the test description
        pps_url = (
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
        )
        await pps_page.goto(pps_url, wait_until="networkidle", timeout=60000)

        # NOTE: If authentication is required, add login steps here.
        # For now, we assume authenticated_page fixture may already hold
        # a session or PPS is configured for SSO. Adjust as needed.

        # Navigate to PPS endpoint / device inventory
        await pps_page.wait_for_load_state("networkidle")
        # Example menu navigation; update selectors to match real PPS UI
        await pps_page.click("text=Endpoints")
        await pps_page.click("text=Endpoint Inventory")

        # Search/filter by MAC address
        search_input = pps_page.locator("input[name='search_mac']")
        if await search_input.is_visible():
            await search_input.fill(target_mac)
            await pps_page.click("button:has-text('Search')")
        else:
            logger.warning(
                "Search input for MAC not found; attempting full-table scan."
            )

        await pps_page.wait_for_timeout(5000)

        pps_row_selector = "table#endpoint_table tbody tr"
        await pps_page.wait_for_selector(pps_row_selector, timeout=30000)

        pps_rows = pps_page.locator(pps_row_selector)
        pps_row_count = await pps_rows.count()
        logger.info("PPS endpoint table rows: %d", pps_row_count)

        pps_endpoint_found = False
        for i in range(pps_row_count):
            row = pps_rows.nth(i)
            row_text = (await row.text_content()) or ""
            if target_mac.lower() in row_text.lower():
                if target_ipv6 in row_text:
                    pps_endpoint_found = True
                    logger.info(
                        "PPS endpoint record found for MAC %s and IPv6 %s",
                        target_mac,
                        target_ipv6,
                    )
                    break

        assert_true(
            pps_endpoint_found,
            "Endpoint record must be present in PPS/controller with "
            f"MAC {target_mac} and IPv6 {target_ipv6}.",
        )

        await pps_context.close()
    except PlaywrightError as exc:
        logger.error("Failed to verify endpoint synchronization with PPS: %s", exc)
        pytest.fail(f"Step 7 failed: unable to verify endpoint in PPS/controller: {exc}")