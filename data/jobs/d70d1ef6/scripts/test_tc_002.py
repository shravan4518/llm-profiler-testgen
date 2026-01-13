import asyncio
import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError, TimeoutError


@pytest.mark.asyncio
async def test_tc_002_reset_basic_profiler_configuration_to_defaults(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_002: Reset basic Profiler configuration to default settings.

    Preconditions:
        - Configuration from TC_001 exists (non-default values set).

    Steps:
        1. Log in to PPS admin UI as `ppsadmin` (handled by authenticated_page fixture).
        2. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
        3. Confirm that the fields show the non-default values from TC_001.
        4. Click the `Reset` button.
        5. Confirm any prompt asking to confirm reset (if present) and proceed.
        6. Observe the values shown in the form.
        7. Navigate away and back to the Basic Configuration page.

    Expected:
        - After clicking Reset, UI fields revert to documented default values:
            * Profiler Name: empty
            * IP/Host: blank or factory default (assume blank here)
            * Polling interval: "720"
            * DHCPv6-related checkboxes: unchecked
        - No validation errors are shown.
        - After navigation away/back, default values persist.
    """

    page = authenticated_page

    # --- Helper selectors (update as needed to match actual DOM) ---
    profiler_menu_selector = "text=Profiler"
    profiler_config_menu_selector = "text=Profiler Configuration"
    settings_menu_selector = "text=Settings"
    basic_config_link_selector = "text=Basic Configuration"

    profiler_name_input_selector = "input[name='profilerName']"
    ip_host_input_selector = "input[name='profilerHost']"
    polling_interval_input_selector = "input[name='pollingInterval']"
    dhcpv6_checkbox_selector = "input[name='dhcpv6Enabled']"

    reset_button_selector = "button:has-text('Reset')"
    confirm_reset_button_selector = "button:has-text('OK'), button:has-text('Yes')"
    cancel_reset_button_selector = "button:has-text('Cancel'), button:has-text('No')"

    validation_error_selector = ".error, .validation-error, .ui-error"

    # These are the expected default values per test description
    expected_default_profiler_name = ""
    expected_default_ip_host = ""  # assuming blank is default
    expected_default_polling_interval = "720"
    expected_default_dhcpv6_checked = False

    # ----------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # ----------------------------------------------------------------
    try:
        await page.wait_for_load_state("networkidle")

        # Open Profiler main menu
        await page.click(profiler_menu_selector)
        # Navigate to Profiler Configuration
        await page.click(profiler_config_menu_selector)
        # Navigate to Settings
        await page.click(settings_menu_selector)
        # Open Basic Configuration page
        await page.click(basic_config_link_selector)

        # Ensure Basic Configuration page is loaded (by checking a key field)
        await page.wait_for_selector(profiler_name_input_selector, timeout=10_000)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to navigate to Basic Configuration page: {exc}")

    # ----------------------------------------------------------------
    # Step 3: Confirm that fields show non-default values from TC_001
    # ----------------------------------------------------------------
    # The exact values from TC_001 are not provided, but we can at least assert
    # that they differ from the expected defaults (indicating non-default config).
    try:
        profiler_name_value = await page.locator(profiler_name_input_selector).input_value()
        ip_host_value = await page.locator(ip_host_input_selector).input_value()
        polling_interval_value = await page.locator(polling_interval_input_selector).input_value()
        dhcpv6_checked = await page.locator(dhcpv6_checkbox_selector).is_checked()
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to read current basic configuration values: {exc}")

    # Assert that at least one field is non-default, indicating TC_001 config is present.
    non_default_condition = any(
        [
            profiler_name_value != expected_default_profiler_name,
            ip_host_value != expected_default_ip_host,
            polling_interval_value != expected_default_polling_interval,
            dhcpv6_checked != expected_default_dhcpv6_checked,
        ]
    )
    assert non_default_condition, (
        "Expected non-default configuration from TC_001, but all fields appear to be defaults."
    )

    # ----------------------------------------------------------------
    # Step 4: Click the `Reset` button
    # ----------------------------------------------------------------
    try:
        await page.click(reset_button_selector)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to click Reset button: {exc}")

    # ----------------------------------------------------------------
    # Step 5: Confirm any prompt asking to confirm reset (if present) and proceed
    # ----------------------------------------------------------------
    # Handle possible JavaScript dialog (alert/confirm)
    dialog_handled = False

    async def dialog_handler(dialog) -> None:
        nonlocal dialog_handled
        dialog_handled = True
        await dialog.accept()

    page.on("dialog", dialog_handler)

    # There may also be an in-page modal; attempt to confirm it if it appears.
    try:
        # Wait briefly to see if a confirmation button appears
        confirm_button = page.locator(confirm_reset_button_selector)
        if await confirm_button.is_visible(timeout=3_000):
            await confirm_button.click()
    except TimeoutError:
        # No visible confirm button; either dialog handled or no confirmation required
        pass
    except PlaywrightError as exc:
        pytest.fail(f"Error while handling reset confirmation prompt: {exc}")

    # Give the page a moment to process reset
    await asyncio.sleep(1)

    # ----------------------------------------------------------------
    # Step 6: Observe the values shown in the form (should be defaults)
    # ----------------------------------------------------------------
    try:
        await page.wait_for_selector(profiler_name_input_selector, timeout=10_000)

        profiler_name_after_reset = await page.locator(
            profiler_name_input_selector
        ).input_value()
        ip_host_after_reset = await page.locator(ip_host_input_selector).input_value()
        polling_interval_after_reset = await page.locator(
            polling_interval_input_selector
        ).input_value()
        dhcpv6_checked_after_reset = await page.locator(
            dhcpv6_checkbox_selector
        ).is_checked()
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to read configuration values after reset: {exc}")

    # Assert that all fields match expected defaults
    assert profiler_name_after_reset == expected_default_profiler_name, (
        f"Profiler Name should be default ('{expected_default_profiler_name}'), "
        f"but is '{profiler_name_after_reset}'."
    )
    assert ip_host_after_reset == expected_default_ip_host, (
        f"IP/Host should be default ('{expected_default_ip_host}'), "
        f"but is '{ip_host_after_reset}'."
    )
    assert polling_interval_after_reset == expected_default_polling_interval, (
        f"Polling interval should be default '{expected_default_polling_interval}', "
        f"but is '{polling_interval_after_reset}'."
    )
    assert dhcpv6_checked_after_reset is expected_default_dhcpv6_checked, (
        "DHCPv6 checkbox state does not match expected default: "
        f"expected {expected_default_dhcpv6_checked}, "
        f"got {dhcpv6_checked_after_reset}."
    )

    # ----------------------------------------------------------------
    # Assert: No validation errors are shown
    # ----------------------------------------------------------------
    try:
        error_locators = page.locator(validation_error_selector)
        # If selector does not match anything, count() will be 0
        error_count = await error_locators.count()
    except PlaywrightError as exc:
        pytest.fail(f"Failed while checking for validation errors: {exc}")

    assert error_count == 0, "Validation errors are displayed after reset."

    # ----------------------------------------------------------------
    # Step 7: Navigate away and back to the Basic Configuration page
    # ----------------------------------------------------------------
    try:
        # Navigate away (e.g., to Profiler Configuration main page)
        await page.click(profiler_config_menu_selector)
        await page.wait_for_load_state("networkidle")

        # Navigate back to Basic Configuration
        await page.click(settings_menu_selector)
        await page.click(basic_config_link_selector)
        await page.wait_for_selector(profiler_name_input_selector, timeout=10_000)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to navigate away and back to Basic Configuration page: {exc}")

    # ----------------------------------------------------------------
    # Final verification: defaults persist after navigation
    # ----------------------------------------------------------------
    try:
        profiler_name_after_nav = await page.locator(
            profiler_name_input_selector
        ).input_value()
        ip_host_after_nav = await page.locator(ip_host_input_selector).input_value()
        polling_interval_after_nav = await page.locator(
            polling_interval_input_selector
        ).input_value()
        dhcpv6_checked_after_nav = await page.locator(
            dhcpv6_checkbox_selector
        ).is_checked()
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to read configuration values after navigation: {exc}")

    assert profiler_name_after_nav == expected_default_profiler_name, (
        "Profiler Name default did not persist after navigation."
    )
    assert ip_host_after_nav == expected_default_ip_host, (
        "IP/Host default did not persist after navigation."
    )
    assert polling_interval_after_nav == expected_default_polling_interval, (
        "Polling interval default did not persist after navigation."
    )
    assert dhcpv6_checked_after_nav is expected_default_dhcpv6_checked, (
        "DHCPv6 default checkbox state did not persist after navigation."
    )