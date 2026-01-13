import asyncio
import logging
from typing import Tuple

import pytest
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_011_dhcpv6_external_sniffing_dependency(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_011: Attempt to enable DHCPv6 sniffing over external port without enabling DHCPv6 packet capturing.

    Title:
        Attempt to enable DHCPv6 sniffing over external port without enabling DHCPv6 packet capturing

    Category:
        Negative

    Priority:
        Medium

    Description:
        Ensure correct dependency handling if external port sniffing is enabled
        while base DHCPv6 collector is disabled.

    Preconditions:
        - User is authenticated as `ppsadmin`.
        - Basic Configuration page is accessible.

    Steps:
        1. Log in as `ppsadmin`.  (handled by authenticated_page fixture)
        2. Navigate to Basic Configuration page.
        3. Uncheck "Enable DHCPv6 packet capturing".
        4. Check "Enable DHCPv6 sniffing over external port".
        5. Click "Save Changes".

    Expected Results:
        - System either:
          - Automatically checks "Enable DHCPv6 packet capturing", OR
          - Shows an error indicating external sniffing requires base DHCPv6 capturing.
        - Configuration is not saved in an inconsistent state where external sniffing
          is enabled while base collector is disabled.

    Postconditions:
        - Settings reflect a consistent state honoring feature dependencies.
    """
    page: Page = authenticated_page

    # Locators (CSS/xpath are examples; adjust to actual application identifiers)
    basic_config_nav_locator = page.get_by_role("link", name="Basic Configuration")
    dhcpv6_capture_checkbox_locator = page.get_by_label(
        "Enable DHCPv6 packet capturing", exact=True
    )
    dhcpv6_external_sniff_checkbox_locator = page.get_by_label(
        "Enable DHCPv6 sniffing over external port", exact=True
    )
    save_changes_button_locator = page.get_by_role("button", name="Save Changes")

    # Potential error / validation message locators (examples; adjust as needed)
    generic_error_locator = page.locator(".error, .error-message, .validation-error")
    dialog_error_locator = page.get_by_role("dialog")

    async def navigate_to_basic_configuration() -> None:
        """Navigate to the Basic Configuration page using the main navigation."""
        try:
            # Step 2: Navigate to Basic Configuration page
            await basic_config_nav_locator.click()
            await page.wait_for_load_state("networkidle")
        except PlaywrightError as exc:
            logger.error("Failed to navigate to Basic Configuration page: %s", exc)
            pytest.fail("Navigation to Basic Configuration page failed.")

    async def set_checkbox_state(locator, desired_state: bool) -> None:
        """
        Set the checkbox to a desired state (checked/unchecked) safely.

        Args:
            locator: Playwright locator for the checkbox.
            desired_state: True to check, False to uncheck.
        """
        try:
            await locator.wait_for(state="visible", timeout=5000)
            current_state = await locator.is_checked()
            if current_state != desired_state:
                await locator.click()
        except PlaywrightError as exc:
            logger.error("Failed to set checkbox state: %s", exc)
            pytest.fail("Unable to interact with checkbox.")

    async def click_save_changes() -> None:
        """Click the Save Changes button and wait for any network activity to settle."""
        try:
            await save_changes_button_locator.wait_for(state="visible", timeout=5000)
            await save_changes_button_locator.click()
            # Give the backend some time to respond and UI to update
            await page.wait_for_timeout(1000)
        except PlaywrightError as exc:
            logger.error("Failed to click 'Save Changes': %s", exc)
            pytest.fail("Unable to click 'Save Changes' button.")

    async def read_checkbox_states() -> Tuple[bool, bool]:
        """Read the current checked states of the two relevant checkboxes."""
        try:
            await dhcpv6_capture_checkbox_locator.wait_for(state="visible", timeout=5000)
            await dhcpv6_external_sniff_checkbox_locator.wait_for(
                state="visible", timeout=5000
            )
            base_capture_enabled = await dhcpv6_capture_checkbox_locator.is_checked()
            external_sniff_enabled = await dhcpv6_external_sniff_checkbox_locator.is_checked()
            return base_capture_enabled, external_sniff_enabled
        except PlaywrightError as exc:
            logger.error("Failed to read checkbox states: %s", exc)
            pytest.fail("Unable to read DHCPv6 configuration states.")

    async def detect_error_message() -> bool:
        """
        Detect if any error / validation message is displayed after saving.

        Returns:
            True if an error message/dialog appears, False otherwise.
        """
        try:
            # Try to detect inline error
            if await generic_error_locator.first.is_visible():
                return True
        except PlaywrightTimeoutError:
            pass
        except PlaywrightError:
            # Ignore locator issues here; we fall back to dialog check
            pass

        try:
            # Try to detect error dialog
            if await dialog_error_locator.is_visible():
                # Optionally, check that dialog contains relevant text
                dialog_text = await dialog_error_locator.text_content()
                if dialog_text and "DHCPv6" in dialog_text:
                    return True
                return True
        except PlaywrightTimeoutError:
            pass
        except PlaywrightError:
            pass

        return False

    # -------------------------------------------------------------------------
    # Test execution
    # -------------------------------------------------------------------------

    # Step 2: Navigate to Basic Configuration page
    await navigate_to_basic_configuration()

    # Ensure we start from a known baseline: read current states
    base_initial_state, external_initial_state = await read_checkbox_states()
    logger.info(
        "Initial states - DHCPv6 capture: %s, external sniff: %s",
        base_initial_state,
        external_initial_state,
    )

    # Step 3: Uncheck "Enable DHCPv6 packet capturing"
    await set_checkbox_state(dhcpv6_capture_checkbox_locator, desired_state=False)

    # Step 4: Check "Enable DHCPv6 sniffing over external port"
    await set_checkbox_state(dhcpv6_external_sniff_checkbox_locator, desired_state=True)

    # Step 5: Click "Save Changes"
    await click_save_changes()

    # Give the system a moment to apply logic, then re-read states
    await page.wait_for_timeout(1000)

    # Re-read the checkbox states after attempting to save
    base_after_save, external_after_save = await read_checkbox_states()
    logger.info(
        "Post-save states - DHCPv6 capture: %s, external sniff: %s",
        base_after_save,
        external_after_save,
    )

    # Check if any error message is displayed
    error_displayed = await detect_error_message()

    # -------------------------------------------------------------------------
    # Assertions for expected outcomes
    # -------------------------------------------------------------------------

    # Expected behavior (at least one must be true):
    # 1) System auto-enables base DHCPv6 capture when external sniffing is enabled
    #    -> base_after_save must be True if external_after_save is True
    # 2) System shows an error and does not allow inconsistent configuration
    #    -> external_after_save must not remain True while base_after_save is False

    # Assert that we do NOT end up in an inconsistent state
    inconsistent_state = external_after_save and not base_after_save
    assert not inconsistent_state, (
        "Inconsistent configuration detected: external DHCPv6 sniffing is enabled "
        "while base DHCPv6 packet capturing is disabled."
    )

    # If external sniffing remains enabled, base capture must be enabled as well
    if external_after_save:
        assert base_after_save, (
            "External DHCPv6 sniffing is enabled but base DHCPv6 packet capturing "
            "was not automatically enabled."
        )

    # If base capture remains disabled, we expect an error to have been shown
    if not base_after_save and external_initial_state is False:
        # This branch covers the case where the system rejects the change
        # and keeps both disabled, or reverts external sniffing.
        # At minimum, we expect some feedback/error when dependency is violated.
        assert error_displayed or not external_after_save, (
            "No error or automatic correction was detected when attempting to enable "
            "DHCPv6 external sniffing while base capturing was disabled."
        )

    # -------------------------------------------------------------------------
    # Postconditions: ensure configuration remains consistent
    # -------------------------------------------------------------------------
    # Final sanity check: configuration must not violate dependency.
    final_base_state, final_external_state = await read_checkbox_states()
    assert not (final_external_state and not final_base_state), (
        "Postcondition failed: configuration left in inconsistent state where "
        "external DHCPv6 sniffing is enabled but base capturing is disabled."
    )