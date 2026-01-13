import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error, TimeoutError, expect


logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_save_basic_profiler_configuration_with_dhcpv6(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_001: Save basic profiler configuration with valid settings (including DHCPv6 enable)

    This test validates that an admin can successfully configure and save the basic
    profiler basic configuration, including enabling DHCPv6 packet capturing and
    DHCPv6 sniffing over external port, and that these settings persist after reload.

    Steps:
        1. Log in to the PPS admin console (handled by `authenticated_page` fixture).
        2. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
        3. Verify that existing values are displayed.
        4. Enable "DHCPv6 packet capturing".
        5. Enable "DHCPv6 sniffing over external port".
        6. Ensure polling interval remains 720.
        7. Click "Save Changes".
        8. Confirm success message is displayed.
        9. Reload/navigate back to Basic Configuration.
        10. Verify DHCPv6 options remain enabled and polling interval unchanged.

    Expected:
        - Save operation completes without error.
        - UI displays a clear success confirmation.
        - After reload, DHCPv6 options remain enabled and polling interval is preserved.
    """
    page: Page = authenticated_page

    # Helper locators (update selectors to match actual application DOM)
    profiler_menu_locator = page.get_by_role("link", name="Profiler")
    profiler_config_menu_locator = page.get_by_role(
        "link", name="Profiler Configuration"
    )
    settings_menu_locator = page.get_by_role("link", name="Settings")
    basic_config_link_locator = page.get_by_role(
        "link", name="Basic Configuration"
    )

    dhcpv6_capture_checkbox = page.get_by_label(
        "Enable DHCPv6 packet capturing", exact=True
    )
    dhcpv6_sniffing_checkbox = page.get_by_label(
        "Enable DHCPv6 sniffing over external port", exact=True
    )
    polling_interval_input = page.get_by_label(
        "Polling interval", exact=False
    )  # relax exact if label is longer

    save_changes_button = page.get_by_role("button", name="Save Changes")
    success_message_locator = page.locator(
        "text=Changes saved successfully"
    )

    # Optional: more generic success locator if exact text differs
    generic_success_locator = page.locator(
        "css=.msg-success, .alert-success, .ui-message-success"
    )

    async def safe_click(locator, description: str) -> None:
        """Click with basic error handling and logging."""
        try:
            await expect(locator).to_be_visible(timeout=10_000)
            await locator.click()
        except TimeoutError as exc:
            logger.error("Timed out waiting to click %s: %s", description, exc)
            pytest.fail(f"Timed out waiting to click {description}")
        except Error as exc:
            logger.error("Failed to click %s: %s", description, exc)
            pytest.fail(f"Failed to click {description}: {exc}")

    async def assert_checkbox_checked(locator, description: str) -> None:
        """Assert that a checkbox is checked with explicit error message."""
        try:
            await expect(locator).to_be_visible(timeout=10_000)
            await expect(locator).to_be_checked()
        except AssertionError as exc:
            logger.error("%s is not checked as expected: %s", description, exc)
            pytest.fail(f"{description} is not checked as expected")
        except TimeoutError as exc:
            logger.error("Timed out waiting for %s to be visible: %s", description, exc)
            pytest.fail(f"Timed out waiting for {description} to be visible")

    async def get_input_value(locator, description: str) -> Optional[str]:
        """Get the value of an input with error handling."""
        try:
            await expect(locator).to_be_visible(timeout=10_000)
            value = await locator.input_value()
            logger.info("%s current value: %s", description, value)
            return value
        except TimeoutError as exc:
            logger.error("Timed out waiting for %s input: %s", description, exc)
            pytest.fail(f"Timed out waiting for {description} input")
        except Error as exc:
            logger.error("Failed to read %s input value: %s", description, exc)
            pytest.fail(f"Failed to read {description} input value")
        return None

    # ----------------------------------------------------------------------
    # Step 1: Log in to the PPS admin console
    # ----------------------------------------------------------------------
    # This step is handled by the `authenticated_page` fixture.
    # We just verify we are on an admin page and reachable.
    try:
        await expect(page).to_have_url(
            lambda url: "https://" in url and "admin" in url,
            timeout=15_000,
        )
    except TimeoutError:
        logger.warning(
            "Could not confirm admin URL pattern; continuing with navigation."
        )

    # ----------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # ----------------------------------------------------------------------
    await safe_click(profiler_menu_locator, "Profiler menu")
    await safe_click(profiler_config_menu_locator, "Profiler Configuration menu")
    await safe_click(settings_menu_locator, "Settings menu")
    await safe_click(basic_config_link_locator, "Basic Configuration link")

    # Ensure Basic Configuration page is loaded
    basic_config_header = page.get_by_role("heading", name="Basic Configuration")
    try:
        await expect(basic_config_header).to_be_visible(timeout=10_000)
    except TimeoutError as exc:
        logger.error("Basic Configuration page did not load: %s", exc)
        pytest.fail("Basic Configuration page did not load")

    # ----------------------------------------------------------------------
    # Step 3: Verify that existing values are displayed
    # ----------------------------------------------------------------------
    # At minimum, check that key controls are visible.
    try:
        await expect(dhcpv6_capture_checkbox).to_be_visible(timeout=10_000)
        await expect(dhcpv6_sniffing_checkbox).to_be_visible(timeout=10_000)
        await expect(polling_interval_input).to_be_visible(timeout=10_000)
    except TimeoutError as exc:
        logger.error("Basic configuration fields not visible: %s", exc)
        pytest.fail("Basic configuration fields not visible")

    # Capture existing values (for verification that they remain unchanged where required)
    original_polling_interval = await get_input_value(
        polling_interval_input, "Polling interval"
    )

    # ----------------------------------------------------------------------
    # Step 4: Check the checkbox “Enable DHCPv6 packet capturing”
    # ----------------------------------------------------------------------
    try:
        await expect(dhcpv6_capture_checkbox).to_be_visible(timeout=10_000)
        is_checked = await dhcpv6_capture_checkbox.is_checked()
        if not is_checked:
            await dhcpv6_capture_checkbox.check()
    except Error as exc:
        logger.error("Failed to enable DHCPv6 packet capturing: %s", exc)
        pytest.fail(f"Failed to enable DHCPv6 packet capturing: {exc}")

    # ----------------------------------------------------------------------
    # Step 5: Check the checkbox “Enable DHCPv6 sniffing over external port”
    # ----------------------------------------------------------------------
    try:
        await expect(dhcpv6_sniffing_checkbox).to_be_visible(timeout=10_000)
        is_checked = await dhcpv6_sniffing_checkbox.is_checked()
        if not is_checked:
            await dhcpv6_sniffing_checkbox.check()
    except Error as exc:
        logger.error("Failed to enable DHCPv6 sniffing over external port: %s", exc)
        pytest.fail(f"Failed to enable DHCPv6 sniffing over external port: {exc}")

    # ----------------------------------------------------------------------
    # Step 6: Ensure polling interval (if present) remains 720
    # ----------------------------------------------------------------------
    current_polling_interval = await get_input_value(
        polling_interval_input, "Polling interval"
    )

    # If the field is empty or different, set it to 720 to meet the requirement.
    target_polling_interval = "720"
    if current_polling_interval != target_polling_interval:
        try:
            await polling_interval_input.fill(target_polling_interval)
        except Error as exc:
            logger.error("Failed to set polling interval to %s: %s", target_polling_interval, exc)
            pytest.fail(f"Failed to set polling interval to {target_polling_interval}")

    # Assert that the value is now 720
    updated_polling_interval = await get_input_value(
        polling_interval_input, "Polling interval"
    )
    assert (
        updated_polling_interval == target_polling_interval
    ), f"Polling interval expected to be {target_polling_interval}, got {updated_polling_interval}"

    # ----------------------------------------------------------------------
    # Step 7: Click “Save Changes”
    # ----------------------------------------------------------------------
    await safe_click(save_changes_button, "Save Changes button")

    # ----------------------------------------------------------------------
    # Step 8: Confirm that a success message is displayed
    # ----------------------------------------------------------------------
    success_assertion_errors = []

    try:
        await expect(success_message_locator).to_be_visible(timeout=15_000)
    except TimeoutError as exc:
        success_assertion_errors.append(str(exc))

    if success_assertion_errors:
        # Try generic success locator as a fallback
        try:
            await expect(generic_success_locator).to_be_visible(timeout=10_000)
        except TimeoutError:
            logger.error(
                "Success message not found after saving changes: %s",
                "; ".join(success_assertion_errors),
            )
            pytest.fail("Success message not displayed after saving changes")

    # ----------------------------------------------------------------------
    # Step 9: Refresh the browser page or navigate away and back to Basic Configuration
    # ----------------------------------------------------------------------
    # Simpler and less brittle: reload the page and re-open Basic Configuration
    try:
        await page.reload(wait_until="networkidle")
    except Error as exc:
        logger.error("Failed to reload the page: %s", exc)
        pytest.fail(f"Failed to reload the page after saving: {exc}")

    # Re-navigate in case reload changes current menu context
    await safe_click(profiler_menu_locator, "Profiler menu (post-save)")
    await safe_click(
        profiler_config_menu_locator, "Profiler Configuration menu (post-save)"
    )
    await safe_click(settings_menu_locator, "Settings menu (post-save)")
    await safe_click(
        basic_config_link_locator, "Basic Configuration link (post-save)"
    )

    try:
        await expect(basic_config_header).to_be_visible(timeout=10_000)
    except TimeoutError as exc:
        logger.error("Basic Configuration page did not load after reload: %s", exc)
        pytest.fail("Basic Configuration page did not load after reload")

    # ----------------------------------------------------------------------
    # Step 10: Verify that both DHCPv6-related checkboxes are still checked
    #         and polling interval is unchanged
    # ----------------------------------------------------------------------
    await assert_checkbox_checked(
        dhcpv6_capture_checkbox,
        "Enable DHCPv6 packet capturing checkbox after reload",
    )
    await assert_checkbox_checked(
        dhcpv6_sniffing_checkbox,
        "Enable DHCPv6 sniffing over external port checkbox after reload",
    )

    persisted_polling_interval = await get_input_value(
        polling_interval_input, "Polling interval after reload"
    )
    assert (
        persisted_polling_interval == target_polling_interval
    ), (
        f"Polling interval expected to remain {target_polling_interval} after reload, "
        f"but found {persisted_polling_interval}"
    )