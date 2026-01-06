import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_007_snmp_trap_incorrect_community(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_007: Verify handling of SNMP trap with incorrect community string.

    Title:
        Verify handling of SNMP trap with incorrect community string

    Description:
        Ensures Profiler discards traps with an invalid or unauthorized
        community string and does not update endpoint data based on them.

    Preconditions (assumed handled outside UI where applicable):
        - Profiler device configuration for switch 10.10.20.10 uses community
          'netmon_ro'.
        - Switch can be configured to send traps with different communities.

    Expected Results:
        - Profiler receives the trap packet but does not accept it due to
          community mismatch.
        - No new endpoint 22:33:44:55:66:77 appears in inventory.
        - No endpoint or device attributes are updated based on the invalid trap.
        - Logs indicate trap rejected due to invalid community or
          authentication failure.
    """
    page = authenticated_page
    switch_ip = "10.10.20.10"
    valid_community = "netmon_ro"
    invalid_community = "wrong_ro"
    test_mac = "22:33:44:55:66:77"
    switch_port = "Gi1/0/15"

    # Utility: safe locator click with error handling
    async def safe_click(locator_str: str, timeout: int = 10000) -> None:
        try:
            await page.locator(locator_str).click(timeout=timeout)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click '{locator_str}': {exc}")

    # Utility: safe fill with error handling
    async def safe_fill(locator_str: str, value: str, timeout: int = 10000) -> None:
        try:
            await page.locator(locator_str).fill(value, timeout=timeout)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to fill '{locator_str}' with '{value}': {exc}")

    # Utility: wait for text in a locator
    async def wait_for_text(locator_str: str, text: str, timeout: int = 10000) -> None:
        try:
            await page.locator(locator_str).get_by_text(text).first.wait_for(
                state="visible", timeout=timeout
            )
        except PlaywrightError as exc:
            pytest.fail(f"Text '{text}' not visible in '{locator_str}': {exc}")

    # NOTE:
    # The actual selectors below are placeholders and must be adapted
    # to the real Profiler UI (ids, data-test attributes, etc.).

    # -------------------------------------------------------------------------
    # Step 1: Add switch 10.10.20.10 to Profiler using community 'netmon_ro'
    # -------------------------------------------------------------------------
    try:
        # Navigate to the device/switch management page
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )

        # Example navigation to "Devices" / "Network Devices" page
        await safe_click("text=Devices")
        await safe_click("text=Network Devices")

        # Click "Add Device" or similar button
        await safe_click("button:has-text('Add Device')")

        # Fill device IP
        await safe_fill("input[name='device_ip']", switch_ip)

        # Fill SNMP community string
        await safe_fill("input[name='snmp_community']", valid_community)

        # Save device configuration
        await safe_click("button:has-text('Save')")

        # Verify device appears in device list
        device_row = page.locator("table >> tr", has_text=switch_ip)
        await device_row.wait_for(state="visible", timeout=15000)
        assert await device_row.is_visible(), (
            "Switch device should be visible in device list after adding."
        )
    except AssertionError:
        raise
    except Exception as exc:
        pytest.fail(f"Step 1 failed: could not add switch {switch_ip}: {exc}")

    # -------------------------------------------------------------------------
    # Step 2: Ensure no endpoint with MAC 22:33:44:55:66:77 exists in Profiler
    # -------------------------------------------------------------------------
    try:
        # Navigate to endpoint/inventory page
        await safe_click("text=Inventory")
        await safe_click("text=Endpoints")

        # Search for the test MAC
        await safe_fill("input[placeholder='Search']", test_mac)
        await page.keyboard.press("Enter")

        # Wait briefly for search results to load
        await page.wait_for_timeout(2000)

        # Verify no row contains this MAC address
        endpoint_row = page.locator("table >> tr", has_text=test_mac)
        is_visible = await endpoint_row.is_visible()
        assert not is_visible, (
            f"Precondition failed: endpoint with MAC {test_mac} already exists."
        )
    except AssertionError:
        raise
    except Exception as exc:
        pytest.fail(
            f"Step 2 failed: unable to verify absence of endpoint {test_mac}: {exc}"
        )

    # -------------------------------------------------------------------------
    # Step 3: Configure switch trap community for linkUp traps as 'wrong_ro'
    # -------------------------------------------------------------------------
    # NOTE: This is typically done on the switch itself (not in Profiler UI).
    # Here we only document/assume the configuration or provide a placeholder
    # where an API/CLI integration could be called.
    try:
        # Placeholder log to indicate external configuration step
        # In real automation, you might call an SSH/API helper here.
        print(
            f"[INFO] Ensure switch {switch_ip} is configured to send linkUp "
            f"traps with community '{invalid_community}'."
        )
    except Exception as exc:
        pytest.fail(f"Step 3 failed: could not ensure switch trap configuration: {exc}")

    # -------------------------------------------------------------------------
    # Step 4: Connect endpoint to Gi1/0/15 to generate a linkUp trap
    # -------------------------------------------------------------------------
    # Also typically done physically or via lab automation.
    try:
        print(
            f"[INFO] Connect endpoint with MAC {test_mac} to switch port "
            f"{switch_port} to generate linkUp trap."
        )
    except Exception as exc:
        pytest.fail(
            f"Step 4 failed: could not trigger linkUp trap for MAC {test_mac}: {exc}"
        )

    # -------------------------------------------------------------------------
    # Step 5: Confirm via packet capture that the trap community is 'wrong_ro'
    # -------------------------------------------------------------------------
    # This is usually verified via packet capture tools (e.g., tcpdump/Wireshark)
    # and may not be visible in the UI. We assume an external verification step.
    try:
        print(
            f"[INFO] Confirm via packet capture that SNMP trap community is "
            f"'{invalid_community}'."
        )
    except Exception as exc:
        pytest.fail(
            f"Step 5 failed: unable to confirm trap community '{invalid_community}': {exc}"
        )

    # -------------------------------------------------------------------------
    # Step 6: Wait 2–3 minutes, then search for MAC in Profiler
    # -------------------------------------------------------------------------
    try:
        wait_seconds = 150  # 2.5 minutes
        print(f"[INFO] Waiting {wait_seconds} seconds for trap processing...")
        await asyncio.sleep(wait_seconds)

        # Refresh endpoint inventory and search again
        await safe_click("text=Inventory")
        await safe_click("text=Endpoints")

        await safe_fill("input[placeholder='Search']", test_mac)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(3000)

        endpoint_row_after = page.locator("table >> tr", has_text=test_mac)
        is_visible_after = await endpoint_row_after.is_visible()
        assert not is_visible_after, (
            f"Endpoint with MAC {test_mac} should NOT be created from trap "
            f"with invalid community."
        )
    except AssertionError:
        raise
    except Exception as exc:
        pytest.fail(
            f"Step 6 failed: error while verifying endpoint absence after waiting: {exc}"
        )

    # -------------------------------------------------------------------------
    # Step 7: Check Profiler logs for messages about invalid community
    # -------------------------------------------------------------------------
    try:
        # Navigate to logs/audit page
        await safe_click("text=Administration")
        await safe_click("text=Logs")

        # Optionally filter by time window around when the trap was sent
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=10)
        print(
            f"[INFO] Filtering logs from {start_time.isoformat()} to "
            f"{end_time.isoformat()} for invalid community messages."
        )

        # Example: open advanced filter (placeholders)
        await safe_click("button:has-text('Advanced Filter')")

        # Filter by device IP (if supported)
        if await page.locator("input[name='device_ip_filter']").is_visible():
            await safe_fill("input[name='device_ip_filter']", switch_ip)

        # Filter by text that might indicate invalid community
        suspected_keywords = [
            "invalid community",
            "community mismatch",
            "authentication failure",
            "SNMP trap rejected",
        ]
        # Use the first keyword as a primary filter; others checked in results
        await safe_fill("input[name='message_filter']", suspected_keywords[0])

        await safe_click("button:has-text('Apply')")

        # Wait for logs to load
        await page.wait_for_timeout(3000)

        log_rows = page.locator("table >> tr")
        row_count = await log_rows.count()

        # Gather log text for assertion
        log_texts = []
        for i in range(row_count):
            text = await log_rows.nth(i).inner_text()
            log_texts.append(text)

        # Check if any log line contains any of the expected keywords
        matched_keyword = None
        for text in log_texts:
            for keyword in suspected_keywords:
                if keyword.lower() in text.lower():
                    matched_keyword = keyword
                    break
            if matched_keyword:
                break

        assert matched_keyword is not None, (
            "Profiler logs should contain a message indicating trap rejection "
            "due to invalid community or authentication failure."
        )
    except AssertionError:
        raise
    except Exception as exc:
        pytest.fail(f"Step 7 failed: error while checking logs for invalid community: {exc}")

    # -------------------------------------------------------------------------
    # Final sanity check: inventory unchanged (no side effects)
    # -------------------------------------------------------------------------
    try:
        await safe_click("text=Inventory")
        await safe_click("text=Endpoints")

        await safe_fill("input[placeholder='Search']", test_mac)
        await page.keyboard.press("Enter")
        await page.wait_for_timeout(2000)

        final_endpoint_row = page.locator("table >> tr", has_text=test_mac)
        final_visible = await final_endpoint_row.is_visible()
        assert not final_visible, (
            "Postcondition failed: inventory should remain unchanged; "
            f"endpoint {test_mac} must not exist."
        )
    except AssertionError:
        raise
    except Exception as exc:
        pytest.fail(
            f"Postcondition check failed: error verifying inventory unchanged: {exc}"
        )