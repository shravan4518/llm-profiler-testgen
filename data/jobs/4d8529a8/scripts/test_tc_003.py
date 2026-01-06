import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Browser, Error, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
async def test_enable_dhcpv6_packet_capturing_basic_configuration(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_003: Enable DHCPv6 packet capturing in basic configuration

    Validates that enabling “DHCPv6 packet capturing” in Basic Configuration
    activates DHCPv6 collection and that Profiler records DHCPv6 data for a
    specific endpoint.

    Preconditions:
    - PPS/Profiler with Phase 3 IPv6 support is enabled.
    - Dual-stack network with DHCPv6 server and IPv6-enabled endpoint.
    - Administrator access to PPS UI (provided by authenticated_page fixture).

    Expected Results:
    - DHCPv6Collector process is started/enabled (logs or status page).
    - Profiler records the DHCPv6 transaction for the endpoint.
    - Device record shows IPv6 address and DHCPv6 options.
    - Device classification includes IPv6 context.
    """

    page = authenticated_page
    endpoint_mac = "AA:BB:CC:DD:EE:03"

    # Helper: safe click with error handling
    async def safe_click(selector: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.click(selector)
        except (PlaywrightTimeoutError, Error) as exc:
            pytest.fail(f"Failed to {description}. Selector: '{selector}'. Error: {exc}")

    # Helper: safe fill with error handling
    async def safe_fill(selector: str, value: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.fill(selector, value)
        except (PlaywrightTimeoutError, Error) as exc:
            pytest.fail(f"Failed to {description}. Selector: '{selector}'. Error: {exc}")

    # Helper: safe checkbox toggle
    async def ensure_checkbox_checked(selector: str, description: str) -> None:
        try:
            checkbox = await page.wait_for_selector(selector, state="attached", timeout=10000)
            is_checked = await checkbox.is_checked()
            if not is_checked:
                await checkbox.check()
        except (PlaywrightTimeoutError, Error) as exc:
            pytest.fail(f"Failed to enable {description}. Selector: '{selector}'. Error: {exc}")

    # -------------------------------------------------------------------------
    # Step 1: Log in to PPS as admin
    # -------------------------------------------------------------------------
    # Assumption: authenticated_page fixture already logs in as admin and
    # navigates to the PPS main dashboard. We verify by checking for a known
    # dashboard element instead of performing login here.

    try:
        await page.wait_for_selector("text=Dashboard", timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Admin login verification failed: 'Dashboard' not visible. Error: {exc}")

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler Configuration > Settings > Basic Configuration
    # -------------------------------------------------------------------------
    # NOTE: Selectors are examples and should be adapted to actual PPS UI.

    await safe_click(
        "nav >> text=Profiler Configuration",
        "open 'Profiler Configuration' menu",
    )

    await safe_click(
        "nav >> text=Settings",
        "open 'Settings' submenu",
    )

    await safe_click(
        "text=Basic Configuration",
        "open 'Basic Configuration' page",
    )

    # Verify we are on Basic Configuration page
    try:
        await page.wait_for_selector("h1:has-text('Basic Configuration')", timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Basic Configuration page did not load correctly. Error: {exc}")

    # -------------------------------------------------------------------------
    # Step 3: Check the option “Enable DHCPv6 packet capturing”.
    # -------------------------------------------------------------------------
    # Example selector: checkbox with label text or data-testid
    dhcpv6_capture_checkbox_selector = (
        "input[type='checkbox'][name='enableDhcpv6Capture']"
    )

    await ensure_checkbox_checked(
        dhcpv6_capture_checkbox_selector,
        "DHCPv6 packet capturing",
    )

    # -------------------------------------------------------------------------
    # Step 4: If available, enable “DHCPv6 sniffing over external port” and save.
    # -------------------------------------------------------------------------
    dhcpv6_sniffing_checkbox_selector = (
        "input[type='checkbox'][name='enableDhcpv6SniffingExternalPort']"
    )

    # Enable sniffing only if the checkbox exists
    try:
        sniffing_checkbox = await page.query_selector(dhcpv6_sniffing_checkbox_selector)
        if sniffing_checkbox:
            await ensure_checkbox_checked(
                dhcpv6_sniffing_checkbox_selector,
                "DHCPv6 sniffing over external port",
            )
    except Error as exc:
        pytest.fail(
            f"Error while checking for DHCPv6 sniffing external port option. Error: {exc}"
        )

    # Save configuration
    save_button_selector = "button:has-text('Save')"
    await safe_click(save_button_selector, "save Basic Configuration")

    # Confirm success notification
    try:
        await page.wait_for_selector(
            "text=Configuration saved successfully",
            timeout=15000,
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Configuration save confirmation not found. Error: {exc}")

    # -------------------------------------------------------------------------
    # Step 5: Note the time of configuration change.
    # -------------------------------------------------------------------------
    config_change_time = datetime.utcnow()

    # -------------------------------------------------------------------------
    # Step 6: Wait 15 minutes to allow configuration to take effect.
    # -------------------------------------------------------------------------
    # For automation, we typically do NOT wait full 15 minutes. Here we:
    # - Log the intended wait window.
    # - Use a shorter sleep as a compromise, which can be adjusted by env var.
    # If your environment requires real-time waiting, replace with 15 * 60.
    intended_wait_minutes = 15
    effective_wait_seconds = int(
        float(
            # Allow override via environment variable if test runner supports it
            __import__("os").environ.get("DHCPV6_WAIT_SECONDS", "60")
        )
    )
    print(
        f"[INFO] Configuration changed at {config_change_time.isoformat()}Z. "
        f"Per spec, wait {intended_wait_minutes} minutes; "
        f"test will actually wait {effective_wait_seconds} seconds."
    )

    await asyncio.sleep(effective_wait_seconds)

    # -------------------------------------------------------------------------
    # Step 7: Reboot the dual-stack endpoint (external action).
    # -------------------------------------------------------------------------
    # This step is typically done via an external system (e.g., SSH, API, or lab
    # controller). Here we:
    # - Document the required action.
    # - Optionally pause for manual intervention.
    #
    # If you have an automation API, integrate it here instead.

    print(
        "[ACTION REQUIRED] Reboot the dual-stack endpoint so it requests IPv6 "
        "via DHCPv6, then press Enter in the test console to continue."
    )
    # If running in a non-interactive CI environment, this input will fail.
    # Wrap in try/except so test does not crash; instead, we just proceed.
    try:
        _ = input()  # type: ignore[func-returns-value]
    except Exception:
        print("[WARN] Non-interactive environment detected; skipping manual wait.")

    # -------------------------------------------------------------------------
    # Step 8: Navigate to Profiler > Discovered Devices and filter by MAC.
    # -------------------------------------------------------------------------
    await safe_click("nav >> text=Profiler", "open 'Profiler' menu")
    await safe_click("nav >> text=Discovered Devices", "open 'Discovered Devices' page")

    try:
        await page.wait_for_selector(
            "h1:has-text('Discovered Devices')",
            timeout=15000,
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"'Discovered Devices' page did not load correctly. Error: {exc}")

    # Apply MAC filter
    mac_filter_input_selector = "input[name='macFilter']"
    await safe_fill(
        mac_filter_input_selector,
        endpoint_mac,
        "fill MAC address filter",
    )

    search_button_selector = "button:has-text('Search')"
    await safe_click(search_button_selector, "apply MAC filter")

    # Wait for search results to load
    results_row_selector = f"tr:has(td:text('{endpoint_mac}'))"
    try:
        await page.wait_for_selector(results_row_selector, timeout=60000)
    except PlaywrightTimeoutError:
        pytest.fail(
            f"Endpoint with MAC '{endpoint_mac}' not found in Discovered Devices "
            f"after DHCPv6 capture was enabled."
        )

    # -------------------------------------------------------------------------
    # Step 9: Open device details and verify IPv6 DHCP information.
    # -------------------------------------------------------------------------
    # Open device details by clicking on the row or a details link
    device_details_link_selector = f"{results_row_selector} >> text=Details"
    try:
        # Prefer explicit details link if present, otherwise click the row
        details_link = await page.query_selector(device_details_link_selector)
        if details_link:
            await details_link.click()
        else:
            await page.click(results_row_selector)
    except Error as exc:
        pytest.fail(f"Failed to open device details for MAC '{endpoint_mac}'. Error: {exc}")

    # Verify device details page loaded
    try:
        await page.wait_for_selector(
            "h1:has-text('Device Details')",
            timeout=15000,
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Device Details page did not load correctly. Error: {exc}")

    # -------------------------------------------------------------------------
    # Assertions for Expected Results
    # -------------------------------------------------------------------------

    # 1) DHCPv6Collector process is started/enabled (logs or status page).
    #    Assuming there is a status section or badge in the device details or
    #    Profiler status area. Adjust selectors to match actual UI.
    #
    # Example: a status badge saying "DHCPv6Collector: Running"
    dhcpv6_collector_status_selector = "text=DHCPv6Collector: Running"
    try:
        await page.wait_for_selector(
            dhcpv6_collector_status_selector,
            timeout=30000,
        )
    except PlaywrightTimeoutError:
        # As a fallback, navigate to a general Profiler status page if exists
        print("[WARN] DHCPv6Collector status not found in Device Details. "
              "Attempting to verify via Profiler status page.")
        await safe_click("nav >> text=Profiler", "open 'Profiler' menu (status check)")
        await safe_click("nav >> text=Status", "open 'Status' page")
        try:
            await page.wait_for_selector(
                "text=DHCPv6Collector: Running",
                timeout=30000,
            )
        except PlaywrightTimeoutError as exc:
            pytest.fail(
                "DHCPv6Collector does not appear to be running/enabled in UI. "
                f"Error: {exc}"
            )

    # 2) Profiler records the DHCPv6 transaction for the endpoint.
    #    Example: DHCPv6 transaction table or section in device details.
    dhcpv6_transaction_section_selector = "section:has(h2:has-text('DHCPv6'))"
    try:
        dhcpv6_section = await page.wait_for_selector(
            dhcpv6_transaction_section_selector,
            timeout=30000,
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            "DHCPv6 transaction section not found in device details for endpoint. "
            f"Error: {exc}"
        )

    # Check that at least one DHCPv6 transaction row is present
    dhcpv6_transaction_row_selector = (
        f"{dhcpv6_transaction_section_selector} >> tr.dhcpv6-transaction-row"
    )
    try:
        await page.wait_for_selector(
            dhcpv6_transaction_row_selector,
            timeout=30000,
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            "No DHCPv6 transaction records found for the endpoint in Profiler. "
            f"Error: {exc}"
        )

    # 3) Device record shows IPv6 address and DHCPv6 options.
    #    Example fields: IPv6 address, IAID, DUID, DNS servers, etc.
    ipv6_address_selector = "text=IPv6 Address"
    dhcpv6_options_selector = "text=DHCPv6 Options"

    try:
        ipv6_label = await page.wait_for_selector(ipv6_address_selector, timeout=15000)
        ipv6_value = await ipv6_label.evaluate(
            "el => el.closest('tr')?.querySelector('td.value')?.textContent || ''"
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            "IPv6 Address field not found in device details for endpoint. "
            f"Error: {exc}"
        )

    assert ipv6_value, "IPv6 address value is empty; expected a valid IPv6 address."

    try:
        dhcpv6_options_label = await page.wait_for_selector(
            dhcpv6_options_selector,
            timeout=15000,
        )
        dhcpv6_options_value = await dhcpv6_options_label.evaluate(
            "el => el.closest('tr')?.querySelector('td.value')?.textContent || ''"
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            "DHCPv6 Options field not found in device details for endpoint. "
            f"Error: {exc}"
        )

    assert dhcpv6_options_value, (
        "DHCPv6 options value is empty; expected DHCPv6 options to be recorded."
    )

    # 4) Device classification includes IPv6 context (still consistent with OS fingerprint).
    #    Example: classification field includes IPv6-related tags or context.
    classification_label_selector = "text=Device Classification"
    try:
        classification_label = await page.wait_for_selector(
            classification_label_selector,
            timeout=15000,
        )
        classification_value = await classification_label.evaluate(
            "el => el.closest('tr')?.querySelector('td.value')?.textContent || ''"
        )
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            "Device Classification field not found in device details for endpoint. "
            f"Error: {exc}"
        )

    assert classification_value, "Device classification is empty; expected a value."
    assert "IPv6" in classification_value or "v6" in classification_value.lower(), (
        "Device classification does not appear to include IPv6 context. "
        f"Classification value: '{classification_value}'"
    )

    # -------------------------------------------------------------------------
    # Postconditions: DHCPv6 packet capturing remains enabled
    # -------------------------------------------------------------------------
    # Re-open Basic Configuration and confirm checkbox is still enabled.
    await safe_click("nav >> text=Profiler Configuration", "re-open 'Profiler Configuration'")
    await safe_click("nav >> text=Settings", "re-open 'Settings' submenu")
    await safe_click("text=Basic Configuration", "re-open 'Basic Configuration' page")

    try:
        await page.wait_for_selector("h1:has-text('Basic Configuration')", timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Failed to re-open Basic Configuration page. Error: {exc}")

    try:
        dhcpv6_checkbox = await page.wait_for_selector(
            dhcpv6_capture_checkbox_selector,
            timeout=10000,
        )
        is_still_checked = await dhcpv6_checkbox.is_checked()
    except (PlaywrightTimeoutError, Error) as exc:
        pytest.fail(
            "Failed to verify that DHCPv6 packet capturing remains enabled. "
            f"Error: {exc}"
        )

    assert is_still_checked, (
        "DHCPv6 packet capturing is no longer enabled after test execution; "
        "expected it to remain enabled for subsequent IPv6 endpoints."
    )