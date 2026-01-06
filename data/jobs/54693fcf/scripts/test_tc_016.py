import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_016_snmpv3_trap_invalid_authentication_rejected(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_016: Verify security: SNMPv3 trap with invalid authentication is rejected.

    This test verifies that Profiler correctly enforces SNMPv3 authentication
    for traps and rejects traps that use invalid authentication credentials.
    It also validates that no endpoint inventory record is created/updated
    from such traps and that security logs contain the appropriate failure
    message.

    Prerequisites:
        - Profiler configured to accept SNMPv3 traps from switch 10.10.50.50
          with user 'snmptrapuser', auth SHA, priv AES.
        - Switch is able to send SNMPv3 traps.

    Steps:
        1. Configure Profiler SNMPv3 credentials.
        2. Configure switch SNMPv3 trap user with wrong auth password.
        3. Trigger linkUp event by connecting endpoint 55:66:77:88:99:AA.
        4. Confirm SNMPv3 trap is sent to Profiler (out-of-band assumption).
        5. Check Profiler logs and inventory for MAC 55:66:77:88:99:AA.

    Expected:
        - Profiler rejects the SNMPv3 trap due to authentication failure.
        - No endpoint record is created/updated from this trap.
        - Logs show SNMPv3 authentication failure for traps from 10.10.50.50.
    """
    page = authenticated_page
    mac_address = "55:66:77:88:99:AA"
    switch_ip = "10.10.50.50"
    snmp_user = "snmptrapuser"

    # Helper: robust click with error handling
    async def safe_click(selector: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.click(selector)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click {description} using selector '{selector}': {exc}")

    # Helper: robust fill with error handling
    async def safe_fill(selector: str, value: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout, state="visible")
            await page.fill(selector, value)
        except PlaywrightError as exc:
            pytest.fail(
                f"Failed to fill {description} using selector '{selector}' "
                f"with value '{value}': {exc}"
            )

    # Helper: wait for text in locator
    async def wait_for_text(locator_str: str, text: str, description: str, timeout: int = 15000):
        try:
            locator = page.locator(locator_str)
            await locator.wait_for(state="visible", timeout=timeout)
            await expect(locator).to_contain_text(text, timeout=timeout)
        except Exception as exc:
            pytest.fail(
                f"Timed out waiting for text '{text}' in {description} "
                f"('{locator_str}'): {exc}"
            )

    # -------------------------------------------------------------------------
    # Step 1: Configure Profiler SNMPv3 credentials (user, auth SHA, priv AES)
    # -------------------------------------------------------------------------
    # NOTE: The exact selectors are assumptions and should be adjusted to match
    #       the actual Profiler UI. They are written in a way that is easy to
    #       search and update.

    # Navigate to SNMP / Trap configuration section
    try:
        # Example navigation: Administration -> System Settings -> SNMP
        await safe_click("text=Administration", "Administration menu")
        await safe_click("text=System Settings", "System Settings menu")
        await safe_click("text=SNMP", "SNMP settings tab")

        # Open SNMPv3 Trap configuration
        await safe_click("text=SNMPv3 Trap Receivers", "SNMPv3 Trap Receivers tab")

        # Click "Add" or "Edit" for receiver 10.10.50.50
        # Prefer editing existing config if present; otherwise add new.
        if await page.locator(f"text={switch_ip}").first.is_visible():
            await page.locator(f"text={switch_ip}").first.click()
        else:
            await safe_click("button:has-text('Add')", "Add SNMPv3 trap receiver button")

        # Fill in SNMPv3 receiver details
        await safe_fill("input[name='receiver_ip']", switch_ip, "SNMPv3 receiver IP")
        await safe_fill("input[name='snmp_user']", snmp_user, "SNMPv3 user name")

        # Select auth protocol SHA
        await safe_click("select[name='auth_protocol']", "Auth protocol dropdown")
        await page.select_option("select[name='auth_protocol']", value="SHA")

        # Select priv protocol AES
        await safe_click("select[name='priv_protocol']", "Privacy protocol dropdown")
        await page.select_option("select[name='priv_protocol']", value="AES")

        # Assume correct passwords are already configured or come from a secure source.
        # We do NOT change them here; we only ensure the protocol settings are correct.
        # Save changes
        await safe_click("button:has-text('Save')", "Save SNMPv3 receiver configuration")

        # Verify configuration appears in list
        await page.wait_for_timeout(2000)
        receiver_row = page.locator("table >> tr", has_text=switch_ip)
        assert await receiver_row.count() > 0, (
            f"SNMPv3 receiver configuration for {switch_ip} was not found after saving."
        )
        assert await receiver_row.locator("td", has_text=snmp_user).count() > 0, (
            f"SNMPv3 user '{snmp_user}' not shown for receiver {switch_ip}."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed during Profiler SNMPv3 configuration (Step 1): {exc}")

    # -------------------------------------------------------------------------
    # Step 2: Configure switch SNMPv3 trap user with wrong auth password
    # -------------------------------------------------------------------------
    # This step is typically performed outside of the Profiler UI (e.g., on the switch CLI).
    # Here, we document/assert the precondition as an assumption.
    #
    # If there is a UI/API in Profiler that pushes config to the switch, that
    # should be automated here instead. For now, we log the assumption.

    wrong_auth_password = "WrongAuth!"
    # Document the assumption for test logs
    pytest.skipif = False  # placeholder to avoid linter warnings
    # In a real implementation, you might call a helper/API to configure the switch:
    # configure_switch_snmpv3_user(ip=switch_ip, user=snmp_user, auth_pw=wrong_auth_password)

    # -------------------------------------------------------------------------
    # Step 3: Trigger linkUp event by connecting endpoint 55:66:77:88:99:AA
    # -------------------------------------------------------------------------
    # This is also typically performed outside of the Profiler UI (physical/virtual connection).
    # We treat this as a timed wait to allow the trap to be generated and sent.

    trigger_window_start = datetime.utcnow()
    # Allow some time for the linkUp event and trap generation
    await asyncio.sleep(10)

    # -------------------------------------------------------------------------
    # Step 4: Capture traps to confirm SNMPv3 trap is sent to Profiler
    # -------------------------------------------------------------------------
    # Actual packet capture is out-of-scope for Playwright. We assume that:
    #   - The switch has been verified to send traps to Profiler.
    # To keep the test self-contained, we proceed to verify only Profiler behavior.
    #
    # If the UI exposes a "Last trap received" timestamp or counter, you could
    # assert it here. Example (pseudo-selectors):
    try:
        # Optional: check some trap statistics widget if available
        if await page.locator("text=Trap Statistics").first.is_visible():
            stats_panel = page.locator("text=Trap Statistics").first
            # This is informational only; not a hard assertion
            _ = await stats_panel.text_content()
    except PlaywrightError:
        # Non-fatal; continue with log/inventory verification
        pass

    # -------------------------------------------------------------------------
    # Step 5: Check Profiler logs and search inventory for MAC after a few minutes
    # -------------------------------------------------------------------------

    # 5a. Verify no endpoint record is created/updated for this MAC
    try:
        # Navigate to Inventory / Endpoints page
        await safe_click("text=Inventory", "Inventory menu")
        await safe_click("text=Endpoints", "Endpoints submenu")

        # Search for MAC address
        await safe_fill("input[placeholder='Search']", mac_address, "endpoint search field")
        await safe_click("button:has-text('Search')", "endpoint search button")

        # Wait for search results to load
        await page.wait_for_timeout(3000)

        # Assert that no row with this MAC exists
        endpoint_row = page.locator("table >> tr", has_text=mac_address)
        row_count = await endpoint_row.count()
        assert row_count == 0, (
            f"Endpoint with MAC {mac_address} was found in inventory, "
            f"but it should NOT be created/updated from an invalid SNMPv3 trap."
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed while verifying inventory for MAC {mac_address} (Step 5a): {exc}")

    # 5b. Verify logs show SNMPv3 authentication failure for traps from 10.10.50.50
    try:
        # Navigate to Logs / Security or System logs
        await safe_click("text=Logs", "Logs menu")
        # Prefer Security logs if available
        if await page.locator("text=Security Logs").first.is_visible():
            await safe_click("text=Security Logs", "Security Logs tab")
        else:
            await safe_click("text=System Logs", "System Logs tab")

        # Filter logs for SNMPv3 authentication failures and switch IP
        await safe_fill("input[placeholder='Search logs']", "SNMPv3 authentication", "log search")
        await safe_click("button:has-text('Search')", "log search button")
        await page.wait_for_timeout(3000)

        # Try to narrow to entries after the trigger time if UI supports time filtering
        # (Pseudo: adjust as needed)
        # if await page.locator("input[name='start_time']").is_visible():
        #     await page.fill("input[name='start_time']", trigger_window_start.strftime(...))

        log_rows = page.locator("table >> tr")
        log_count = await log_rows.count()
        assert log_count > 0, (
            "No log entries were found when searching for 'SNMPv3 authentication'. "
            "Expected to see at least one authentication failure."
        )

        # Look for a row that mentions both the switch IP and failure
        failure_found = False
        for i in range(log_count):
            row_text = (await log_rows.nth(i).inner_text()).lower()
            if switch_ip in row_text and "snmpv3" in row_text and "auth" in row_text:
                failure_found = True
                break

        assert failure_found, (
            f"No log entry was found indicating an SNMPv3 authentication failure "
            f"for traps from {switch_ip}."
        )

    except PlaywrightError as exc:
        pytest.fail(
            "Failed while verifying security/system logs for SNMPv3 "
            f"authentication failures (Step 5b): {exc}"
        )