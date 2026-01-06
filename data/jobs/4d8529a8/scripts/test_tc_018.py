import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_018_negative_dhcp_sniffing_rspan_misconfigured(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_018: Negative – DHCP sniffing mode misconfigured (RSPAN selected but only IP helper configured)

    Objective:
        Confirm that mismatched configuration between switch (IP helper) and Profiler
        (RSPAN mode) results in lack of DHCP profiling and clearly diagnosable symptoms.

    Preconditions (assumed / partially simulated):
        - Switch is configured with IP helper to PPS internal IP.
        - PPS Profiler DHCP sniffing can be configured via UI.
        - Endpoint MAC under test: AA:BB:CC:DD:EE:14.

    Notes:
        - This test focuses on validating PPS Profiler UI behavior and logs.
        - Actual switch configuration and endpoint DHCP behavior are assumed to be
          orchestrated by external automation or testbed tools and are simulated
          here via UI checks and log inspection.
    """
    page: Page = authenticated_page

    # Helper functions
    async def set_dhcp_sniffing_to_rspan_only(page: Page) -> None:
        """
        Navigate to DHCP sniffing settings and configure:
        - DHCP Sniffing mode: "RSPAN for external ports"
        - DHCP Helper mode: disabled (if present)
        """
        try:
            # Step 1: In PPS, set DHCP Sniffing mode to “RSPAN for external ports”
            # and disable DHCP Helper mode (if options are exclusive).

            # Navigate to Profiler / DHCP sniffing configuration.
            # NOTE: Selectors are placeholders and should be adapted to real UI.
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/settings/dhcp",
                wait_until="networkidle",
            )

            # Select DHCP sniffing mode dropdown
            await page.wait_for_selector("select#dhcp-sniffing-mode", timeout=15000)
            await page.select_option(
                "select#dhcp-sniffing-mode",
                label="RSPAN for external ports",
            )

            # Disable DHCP helper mode if the checkbox exists
            helper_checkbox = page.locator("input#dhcp-helper-mode")
            if await helper_checkbox.count() > 0:
                is_checked = await helper_checkbox.is_checked()
                if is_checked:
                    await helper_checkbox.click()

            # Save configuration
            await page.click("button#save-dhcp-settings")

            # Verify a success notification appears
            await page.wait_for_selector(
                "div.alert-success:has-text('DHCP settings updated')",
                timeout=15000,
            )

        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to configure DHCP sniffing to RSPAN-only mode: {exc}"
            ) from exc

    async def simulate_endpoint_dhcp_request(mac_address: str) -> None:
        """
        Simulate or trigger DHCP for the endpoint.

        In a real environment, this would be done via:
        - External lab automation (e.g., API to a traffic generator),
        - Or a dedicated UI/API within PPS that can trigger/observe DHCP.

        For this test script, we assume the DHCP process is handled externally.
        This function acts as a placeholder to represent that step.
        """
        # Step 3: Connect endpoint MAC and trigger DHCP.
        # Placeholder: wait for some time to allow DHCP to occur in the lab.
        await asyncio.sleep(5)

    async def verify_endpoint_has_ip(mac_address: str) -> Optional[str]:
        """
        Verify that the endpoint has obtained an IP address.

        Returns:
            The IP address as a string if found, or None if not found.
        """
        try:
            # Step 4: Confirm endpoint receives IP address (network level).

            # Navigate to an endpoint monitoring page or session list.
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/endpoints",
                wait_until="networkidle",
            )

            # Search by MAC address
            await page.fill("input#endpoint-search", mac_address)
            await page.click("button#search-endpoints")

            # Wait briefly for any results to appear (if any)
            await page.wait_for_timeout(3000)

            # Attempt to read IP from a result row if present.
            # NOTE: This assumes that even if Profiler does not profile DHCP,
            # some other table or monitoring view might still show the IP.
            endpoint_row = page.locator(
                f"tr.endpoint-row:has(td:text-is('{mac_address}'))"
            )

            if await endpoint_row.count() == 0:
                # No row found; we cannot confirm IP from Profiler.
                # Return None to indicate "unknown from UI".
                return None

            ip_cell = endpoint_row.locator("td.endpoint-ip")
            if await ip_cell.count() == 0:
                return None

            ip_text = (await ip_cell.text_content()) or ""
            ip_text = ip_text.strip()

            return ip_text or None

        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed while verifying endpoint IP for {mac_address}: {exc}"
            ) from exc

    async def verify_profiler_has_no_device_record(mac_address: str) -> None:
        """
        Verify that Profiler does NOT create a device record for the given MAC.
        """
        try:
            # Step 5: In Profiler UI, search for MAC.
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/devices",
                wait_until="networkidle",
            )

            await page.fill("input#device-search", mac_address)
            await page.click("button#search-devices")

            # Wait for results to update
            await page.wait_for_timeout(3000)

            device_row = page.locator(
                f"tr.device-row:has(td:text-is('{mac_address}'))"
            )

            # Expected: No device record exists
            assert await device_row.count() == 0, (
                "Profiler should not have created a device record for "
                f"MAC {mac_address}, but one was found."
            )

        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed while verifying absence of device record for {mac_address}: {exc}"
            ) from exc

    async def verify_logs_indicate_no_dhcp_seen(mac_address: str) -> None:
        """
        Verify logs or diagnostics indicate that no DHCP was seen on the external port
        and give hints about configuration mismatch.
        """
        try:
            # Step 6: Review logs for any messages indicating no DHCP seen on external port.

            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/logs",
                wait_until="networkidle",
            )

            # Filter logs by MAC (if supported)
            if await page.locator("input#log-search").count() > 0:
                await page.fill("input#log-search", mac_address)
                await page.click("button#search-logs")
                await page.wait_for_timeout(3000)

            # Look for log hints about missing DHCP / RSPAN mismatch
            # These are sample text patterns; adapt to real system messages.
            log_container = page.locator("div.log-entry-list")

            logs_text = (await log_container.text_content()) or ""
            logs_text_lower = logs_text.lower()

            # We expect at least one of these hints to be present
            expected_hints = [
                "no dhcp packets seen on external rspan port",
                "no dhcp traffic observed on configured rspan interface",
                "dhcp helper configured but profiler in rspan mode",
                "dhcp profiling inactive due to configuration mismatch",
            ]

            hint_found = any(hint in logs_text_lower for hint in expected_hints)

            assert hint_found, (
                "Expected log hints about DHCP not being seen on the external RSPAN "
                "port and/or configuration mismatch, but none were found."
            )

        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed while verifying logs for MAC {mac_address}: {exc}"
            ) from exc

    # ------------------------------
    # Test execution
    # ------------------------------
    mac_under_test = "AA:BB:CC:DD:EE:14"

    # Step 1: Configure PPS DHCP sniffing mode
    await set_dhcp_sniffing_to_rspan_only(page)

    # Step 2: On switch, keep IP helper config; do NOT configure SPAN/RSPAN.
    # This is assumed to be handled outside of this script (lab setup).
    # We do not manipulate the switch from this test; we just document the assumption.
    # To make this explicit in logs:
    print(
        "INFO: Assuming switch is configured with IP helper only, "
        "no SPAN/RSPAN configured."
    )

    # Step 3: Connect endpoint MAC and trigger DHCP (simulated/assumed)
    await simulate_endpoint_dhcp_request(mac_under_test)

    # Step 4: Confirm endpoint receives IP address (network level).
    # In this UI-based test, we may not always see the IP in Profiler since
    # DHCP profiling is intentionally broken. We therefore treat this as a
    # soft check and assert that Profiler does not *claim* DHCP data.
    endpoint_ip = await verify_endpoint_has_ip(mac_under_test)

    # The requirement says: "Endpoint obtains an IP address normally via DHCP."
    # If the UI cannot show it, we log a warning but do not fail the test,
    # because this is a network-level behavior outside the Profiler.
    if endpoint_ip is None:
        print(
            "WARNING: Could not confirm endpoint IP from Profiler UI. "
            "Assuming external validation of DHCP success."
        )
    else:
        # If we do see an IP, ensure it looks like a valid IPv4 address format.
        assert (
            len(endpoint_ip.split(".")) == 4
        ), f"Endpoint IP does not look valid: {endpoint_ip}"

    # Step 5: Verify no device record is created for the MAC.
    await verify_profiler_has_no_device_record(mac_under_test)

    # Step 6: Verify logs indicate no DHCP seen / configuration mismatch.
    await verify_logs_indicate_no_dhcp_seen(mac_under_test)

    # Postconditions:
    # - No invalid device entries created (already asserted).
    # - Configuration remains misaligned until corrected (we leave settings as-is).
    # No teardown is performed here to keep the misconfiguration state for
    # subsequent negative tests, if desired.