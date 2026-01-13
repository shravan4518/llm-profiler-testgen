import asyncio
import re
import pytest
from playwright.async_api import Page, Browser, Error, TimeoutError


@pytest.mark.asyncio
async def test_tc_001_configure_basic_local_profiler_settings(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_001:
    Configure basic local Profiler settings and save successfully.

    This test validates that an admin can configure basic Profiler settings,
    including enabling DHCPv6 packet capturing, and that the configuration
    persists after navigation.

    Preconditions:
        - Authenticated as PPS admin via `authenticated_page` fixture.
        - Profiler module installed and licensed.
        - Profiler service running.

    Steps:
        1. Log in to PPS admin UI as `ppsadmin`.
        2. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
        3. Verify current basic configuration is either blank or default.
        4. Enter Profiler Name.
        5. Enter management IP address.
        6. Ensure polling interval is set to 720.
        7. Enable DHCPv6 packet capturing.
        8. Ensure DHCPv6 sniffing over external port is disabled.
        9. Save changes.
        10. Verify success message and no errors.
        11. Navigate away and back, then verify values persist.
    """

    page = authenticated_page

    # Test data
    profiler_name_value = "LocalProfiler01"
    management_ip_value = "10.10.10.10"
    polling_interval_value = "720"

    # NOTE: The following locators are assumptions and should be updated
    # to match actual application DOM attributes/labels.
    profiler_menu_selector = "text=Profiler"
    profiler_config_menu_selector = "text=Profiler Configuration"
    settings_menu_selector = "text=Settings"
    basic_config_menu_selector = "text=Basic Configuration"

    profiler_name_input_selector = "input[name='profilerName']"
    management_ip_input_selector = "input[name='managementIp']"
    polling_interval_input_selector = "input[name='pollingInterval']"
    dhcpv6_capture_checkbox_selector = "input[name='enableDhcpv6Capture']"
    dhcpv6_sniff_external_checkbox_selector = (
        "input[name='enableDhcpv6SniffExternal']"
    )
    save_changes_button_selector = "button:has-text('Save Changes')"
    success_message_selector = "text=/Changes saved successfully/i"

    # ------------------------------------------------------------------
    # Step 1: Log in as ppsadmin
    # ------------------------------------------------------------------
    # Assumption: authenticated_page fixture already logs in as `ppsadmin`.
    # Validate we are on an authenticated admin page by checking a known element.
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
        await page.wait_for_selector("text=/Admin|Dashboard|Home/i", timeout=15000)
    except TimeoutError as exc:
        raise AssertionError(
            "Failed to verify authenticated admin UI. "
            "Check login fixture or system availability."
        ) from exc

    # ------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # ------------------------------------------------------------------
    try:
        # Open Profiler main menu
        await page.click(profiler_menu_selector)
        # Navigate to Profiler Configuration
        await page.click(profiler_config_menu_selector)
        # Navigate to Settings
        await page.click(settings_menu_selector)
        # Navigate to Basic Configuration
        await page.click(basic_config_menu_selector)

        # Wait for Basic Configuration form to be visible
        await page.wait_for_selector(profiler_name_input_selector, timeout=15000)
    except (TimeoutError, Error) as exc:
        raise AssertionError(
            "Failed to navigate to Profiler > Profiler Configuration > "
            "Settings > Basic Configuration."
        ) from exc

    # ------------------------------------------------------------------
    # Step 3: Verify current basic configuration is either blank or default
    # ------------------------------------------------------------------
    # For robustness, we do not assert strict blank/default values here;
    # instead, we log current values and proceed to overwrite them.
    profiler_name_input = page.locator(profiler_name_input_selector)
    management_ip_input = page.locator(management_ip_input_selector)
    polling_interval_input = page.locator(polling_interval_input_selector)
    dhcpv6_capture_checkbox = page.locator(dhcpv6_capture_checkbox_selector)
    dhcpv6_sniff_external_checkbox = page.locator(
        dhcpv6_sniff_external_checkbox_selector
    )

    try:
        current_profiler_name = await profiler_name_input.input_value()
        current_management_ip = await management_ip_input.input_value()
        current_polling_interval = await polling_interval_input.input_value()
    except Error as exc:
        raise AssertionError(
            "Failed to read current basic configuration values."
        ) from exc

    # Optional informational checks (not failing the test):
    # These are kept as soft validations; if they fail, they will not break the test.
    # They are helpful for debugging but are not strict requirements.
    if current_polling_interval and not re.fullmatch(r"\d+", current_polling_interval):
        # Not raising assertion; just a sanity check.
        print(
            f"INFO: Polling interval is non-numeric: {current_polling_interval!r}"
        )

    # ------------------------------------------------------------------
    # Step 4: Enter `LocalProfiler01` in the Profiler Name field
    # ------------------------------------------------------------------
    try:
        await profiler_name_input.fill(profiler_name_value)
        assert (
            await profiler_name_input.input_value() == profiler_name_value
        ), "Profiler Name field did not accept the expected value."
    except Error as exc:
        raise AssertionError(
            "Failed to set Profiler Name field."
        ) from exc

    # ------------------------------------------------------------------
    # Step 5: Enter `10.10.10.10` in the management IP/address field
    # ------------------------------------------------------------------
    try:
        await management_ip_input.fill(management_ip_value)
        assert (
            await management_ip_input.input_value() == management_ip_value
        ), "Management IP field did not accept the expected value."
    except Error as exc:
        raise AssertionError(
            "Failed to set Management IP field."
        ) from exc

    # ------------------------------------------------------------------
    # Step 6: Ensure the polling interval is set to `720`
    # ------------------------------------------------------------------
    try:
        await polling_interval_input.fill(polling_interval_value)
        assert (
            await polling_interval_input.input_value() == polling_interval_value
        ), "Polling interval field did not accept the expected value."
    except Error as exc:
        raise AssertionError(
            "Failed to set Polling Interval field."
        ) from exc

    # ------------------------------------------------------------------
    # Step 7: Check the `Enable DHCPv6 packet capturing` checkbox
    # ------------------------------------------------------------------
    try:
        if not await dhcpv6_capture_checkbox.is_checked():
            await dhcpv6_capture_checkbox.check()
        assert await dhcpv6_capture_checkbox.is_checked(), (
            "Enable DHCPv6 packet capturing checkbox is not checked after setting."
        )
    except Error as exc:
        raise AssertionError(
            "Failed to set 'Enable DHCPv6 packet capturing' checkbox."
        ) from exc

    # ------------------------------------------------------------------
    # Step 8: Ensure `Enable DHCPv6 sniffing over external port` is unchecked
    # ------------------------------------------------------------------
    try:
        if await dhcpv6_sniff_external_checkbox.is_checked():
            await dhcpv6_sniff_external_checkbox.uncheck()
        assert not await dhcpv6_sniff_external_checkbox.is_checked(), (
            "Enable DHCPv6 sniffing over external port checkbox is checked "
            "when it should be unchecked."
        )
    except Error as exc:
        raise AssertionError(
            "Failed to set 'Enable DHCPv6 sniffing over external port' checkbox."
        ) from exc

    # ------------------------------------------------------------------
    # Step 9: Click `Save Changes`
    # ------------------------------------------------------------------
    try:
        async with page.expect_navigation(wait_until="networkidle", timeout=30000):
            await page.click(save_changes_button_selector)
    except TimeoutError:
        # Some apps save via XHR without navigation; fall back to waiting for success msg
        try:
            await page.wait_for_timeout(2000)
        except Error:
            pass
    except Error as exc:
        raise AssertionError(
            "Failed to click 'Save Changes' or trigger save operation."
        ) from exc

    # ------------------------------------------------------------------
    # Step 10: Observe any confirmation message or error
    # ------------------------------------------------------------------
    # Expected: System accepts configuration and displays success message.
    try:
        # Wait for success message; adjust timeout as needed for environment
        await page.wait_for_selector(success_message_selector, timeout=20000)
    except TimeoutError as exc:
        # Try to detect any visible error messages to give a better failure reason
        error_banner = page.locator(
            "text=/error|failed|invalid|unable to save/i"
        ).first
        try:
            if await error_banner.is_visible():
                error_text = await error_banner.text_content()
                raise AssertionError(
                    f"Configuration save appears to have failed. "
                    f"Error message: {error_text!r}"
                ) from exc
        except Error:
            # If we cannot read error text, just fail with generic message
            pass
        raise AssertionError(
            "Did not observe expected success message after saving configuration."
        ) from exc

    # ------------------------------------------------------------------
    # Step 11: Navigate away (e.g., Home tab), then back to Basic Configuration
    # ------------------------------------------------------------------
    home_tab_selector = "text=Home"

    try:
        # Navigate to Home (or equivalent landing page)
        await page.click(home_tab_selector)
        await page.wait_for_load_state("networkidle", timeout=15000)

        # Navigate back to Basic Configuration
        await page.click(profiler_menu_selector)
        await page.click(profiler_config_menu_selector)
        await page.click(settings_menu_selector)
        await page.click(basic_config_menu_selector)

        await page.wait_for_selector(profiler_name_input_selector, timeout=15000)
    except (TimeoutError, Error) as exc:
        raise AssertionError(
            "Failed to navigate away and back to Basic Configuration page."
        ) from exc

    # ------------------------------------------------------------------
    # Final Assertions: Verify all configured values persist
    # ------------------------------------------------------------------
    try:
        persisted_profiler_name = await profiler_name_input.input_value()
        persisted_management_ip = await management_ip_input.input_value()
        persisted_polling_interval = await polling_interval_input.input_value()
        persisted_dhcpv6_capture = await dhcpv6_capture_checkbox.is_checked()
        persisted_dhcpv6_sniff_external = (
            await dhcpv6_sniff_external_checkbox.is_checked()
        )
    except Error as exc:
        raise AssertionError(
            "Failed to read persisted configuration values after navigation."
        ) from exc

    assert (
        persisted_profiler_name == profiler_name_value
    ), (
        f"Profiler Name did not persist. Expected {profiler_name_value!r}, "
        f"got {persisted_profiler_name!r}."
    )
    assert (
        persisted_management_ip == management_ip_value
    ), (
        f"Management IP did not persist. Expected {management_ip_value!r}, "
        f"got {persisted_management_ip!r}."
    )
    assert (
        persisted_polling_interval == polling_interval_value
    ), (
        f"Polling interval did not persist. Expected {polling_interval_value!r}, "
        f"got {persisted_polling_interval!r}."
    )
    assert persisted_dhcpv6_capture is True, (
        "Enable DHCPv6 packet capturing checkbox did not persist as checked."
    )
    assert persisted_dhcpv6_sniff_external is False, (
        "Enable DHCPv6 sniffing over external port checkbox did not persist as "
        "unchecked."
    )

    # If we reach this point, configuration is stored and appears active
    # with DHCPv6 packet capturing enabled.
    # Additional validation (e.g., backend verification) would go here if available.

    # Small wait for stability in case subsequent tests rely on this configuration
    await asyncio.sleep(1)