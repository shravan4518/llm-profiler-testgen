import asyncio
import logging
from typing import Any, Dict

import pytest
from playwright.async_api import Page, Browser, Error, TimeoutError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_reset_basic_profiler_configuration_to_defaults(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_002: Reset basic profiler configuration to default values.

    Validate that clicking `Reset` clears unsaved changes and reverts the basic
    configuration fields to the last saved configuration or documented defaults.

    Preconditions:
    - Admin logged in as TPSAdmin (via authenticated_page fixture).
    - Non-default basic configuration already saved (e.g., DHCPv6 enabled).

    Steps:
    1. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
    2. Note current values (e.g., DHCPv6 enabled, polling interval `600`).
    3. Change polling interval to `500` and uncheck “Enable DHCPv6 packet capturing”.
    4. Do NOT click Save Changes.
    5. Click `Reset`.
    6. Confirm reset if confirmation dialog appears.
    7. Observe all fields on the basic configuration form.

    Expected:
    - Unsaved changes are discarded.
    - All fields revert to last saved configuration or documented default.
    - No changes are committed to system configuration.
    """

    page: Page = authenticated_page

    # Locators (adjust selectors to match the real UI)
    # -------------------------------------------------------------------------
    # Navigation menu
    profiler_menu = page.get_by_role("link", name="Profiler")
    profiler_config_menu = page.get_by_role("link", name="Profiler Configuration")
    settings_menu = page.get_by_role("link", name="Settings")
    basic_config_menu = page.get_by_role("link", name="Basic Configuration")

    # Basic configuration form elements
    polling_interval_input = page.locator("input[name='pollingInterval']")
    dhcpv6_checkbox = page.locator("input[name='enableDhcpv6Capture']")
    save_changes_button = page.get_by_role("button", name="Save Changes")
    reset_button = page.get_by_role("button", name="Reset")

    # Confirmation dialog (if present)
    reset_confirm_button = page.get_by_role("button", name="OK")
    reset_cancel_button = page.get_by_role("button", name="Cancel")

    # Helper functions
    # -------------------------------------------------------------------------
    async def navigate_to_basic_configuration() -> None:
        """Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration."""
        try:
            # Step 1: Navigate via menus
            await profiler_menu.click()
            await profiler_config_menu.click()
            await settings_menu.click()
            await basic_config_menu.click()

            # Wait for the basic configuration form to be visible
            await polling_interval_input.wait_for(state="visible", timeout=10000)
        except TimeoutError as exc:
            logger.error("Timed out navigating to Basic Configuration: %s", exc)
            raise AssertionError(
                "Failed to navigate to Basic Configuration page within timeout."
            ) from exc
        except Error as exc:
            logger.error("Playwright error during navigation: %s", exc)
            raise AssertionError("Unexpected error during navigation.") from exc

    async def get_basic_config_snapshot() -> Dict[str, Any]:
        """Capture current basic configuration values from the UI."""
        try:
            polling_value = await polling_interval_input.input_value()
            dhcpv6_checked = await dhcpv6_checkbox.is_checked()
        except Error as exc:
            logger.error("Error reading basic configuration values: %s", exc)
            raise AssertionError(
                "Unable to read basic configuration values from the form."
            ) from exc

        return {
            "polling_interval": polling_value,
            "dhcpv6_enabled": dhcpv6_checked,
        }

    async def apply_unsaved_changes() -> Dict[str, Any]:
        """
        Apply changes without saving.

        Step 3: Change polling interval to `500` and uncheck DHCPv6.
        """
        try:
            original_values = await get_basic_config_snapshot()

            # Change polling interval to 500
            await polling_interval_input.fill("")
            await polling_interval_input.type("500")

            # Uncheck DHCPv6 if currently checked
            if await dhcpv6_checkbox.is_checked():
                await dhcpv6_checkbox.uncheck()
            else:
                # If it's already unchecked, check then uncheck to ensure a delta
                await dhcpv6_checkbox.check()
                await dhcpv6_checkbox.uncheck()

            # Verify that the unsaved changes are reflected in the UI
            changed_values = await get_basic_config_snapshot()
            assert changed_values["polling_interval"] == "500", (
                "Polling interval did not change to 500 as expected."
            )
            assert (
                changed_values["dhcpv6_enabled"] is False
            ), "DHCPv6 checkbox should be unchecked after modification."

            return original_values
        except AssertionError:
            raise
        except Error as exc:
            logger.error("Error applying unsaved changes: %s", exc)
            raise AssertionError(
                "Failed to apply unsaved changes to basic configuration."
            ) from exc

    async def trigger_reset_and_confirm() -> None:
        """
        Step 5 & 6: Click Reset and confirm any confirmation dialog.

        Handles both cases:
        - Confirmation dialog appears.
        - No confirmation dialog.
        """
        try:
            await reset_button.click()
        except Error as exc:
            logger.error("Error clicking Reset button: %s", exc)
            raise AssertionError("Unable to click Reset button.") from exc

        # Try to detect and confirm a reset confirmation dialog if it appears.
        try:
            await reset_confirm_button.wait_for(timeout=3000)
            await reset_confirm_button.click()
        except TimeoutError:
            # No confirmation dialog appeared within 3 seconds; assume none is present.
            logger.info("No reset confirmation dialog detected; proceeding.")
        except Error as exc:
            logger.error("Error handling reset confirmation dialog: %s", exc)
            # Try to cancel to avoid leaving UI in unknown state
            try:
                await reset_cancel_button.click()
            except Error:
                pass
            raise AssertionError(
                "Error while handling reset confirmation dialog."
            ) from exc

        # Give the page a moment to process reset
        await asyncio.sleep(1.0)

    async def assert_values_reverted(expected_values: Dict[str, Any]) -> None:
        """
        Step 7: Assert that all fields reverted to last saved configuration.

        - Unsaved changes are discarded.
        - Values match previously captured snapshot.
        """
        # Re-read configuration values after reset
        actual_values = await get_basic_config_snapshot()

        # Assertion: polling interval reverted
        assert (
            actual_values["polling_interval"] == expected_values["polling_interval"]
        ), (
            "Polling interval did not revert to last saved value after Reset. "
            f"Expected: {expected_values['polling_interval']}, "
            f"Found: {actual_values['polling_interval']}"
        )

        # Assertion: DHCPv6 checkbox reverted
        assert actual_values["dhcpv6_enabled"] == expected_values["dhcpv6_enabled"], (
            "DHCPv6 checkbox state did not revert to last saved value after Reset. "
            f"Expected: {expected_values['dhcpv6_enabled']}, "
            f"Found: {actual_values['dhcpv6_enabled']}"
        )

    async def assert_no_changes_committed(
        expected_values: Dict[str, Any],
    ) -> None:
        """
        Verify that no changes were committed to system configuration.

        Implementation strategy:
        - Re-navigate to the same page (simulating a fresh load).
        - Confirm values still match the original snapshot.
        """
        # Re-open the page to force reload of data from backend
        await navigate_to_basic_configuration()
        reloaded_values = await get_basic_config_snapshot()

        assert reloaded_values == expected_values, (
            "System configuration appears to have changed after Reset, "
            "but no Save Changes was performed. "
            f"Expected: {expected_values}, Found: {reloaded_values}"
        )

    # Test body
    # -------------------------------------------------------------------------
    # Step 1: Navigate to Basic Configuration page
    await navigate_to_basic_configuration()

    # Step 2: Note current values (assumed to be last saved configuration)
    original_config = await get_basic_config_snapshot()
    logger.info("Captured original basic configuration: %s", original_config)

    # Sanity check: ensure we have non-empty polling interval
    assert original_config["polling_interval"], (
        "Polling interval field is empty; expected a valid saved value."
    )

    # Step 3 & 4: Apply changes but do NOT save
    baseline_config = original_config.copy()
    await apply_unsaved_changes()

    # Step 5 & 6: Click Reset and confirm
    await trigger_reset_and_confirm()

    # Step 7 & Expected results: verify values reverted to last saved configuration
    await assert_values_reverted(baseline_config)

    # Additional check: ensure no changes were committed to system configuration
    await assert_no_changes_committed(baseline_config)