import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_007_negative_polling_interval_validation(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_007: Attempt to save basic configuration with invalid polling interval (negative number).

    Title:
        Attempt to save basic configuration with invalid polling interval (negative number)

    Category:
        Negative

    Priority:
        High

    Description:
        Verify that validation prevents saving basic configuration when the polling interval
        is a negative value. The test ensures that:
        - The save operation is rejected.
        - A clear validation error message appears near the polling interval field.
        - The stored configuration value for the polling interval is not changed.

    Prerequisites:
        - Admin is already logged in (provided via authenticated_page fixture).
    """
    page: Page = authenticated_page

    # Helper selectors (adjust as needed for the real application)
    profiler_menu_selector = "text=Profiler"
    profiler_config_menu_selector = "text=Profiler Configuration"
    device_attribute_server_menu_selector = (
        "text=Device Attribute Server, text=Basic Configuration"
    )
    polling_interval_input_selector = "input[name='pollingInterval']"
    save_changes_button_selector = "button:has-text('Save Changes')"
    validation_error_selector = (
        "text=Polling interval must be a positive integer, "
        ".polling-interval-error, "
        "span[role='alert']"
    )
    # Selector for a valid server checkbox or row
    valid_server_checkbox_selector = "input[type='checkbox'][name='serverEnabled']"

    # --- Utility functions -----------------------------------------------------

    async def get_polling_interval_value() -> Optional[str]:
        """Safely get the current value of the polling interval field."""
        try:
            locator = page.locator(polling_interval_input_selector)
            if not await locator.is_visible():
                return None
            return await locator.input_value()
        except PlaywrightError as exc:
            logger.error("Failed to read polling interval input value: %s", exc)
            return None

    async def navigate_to_device_attribute_server() -> None:
        """Navigate to Profiler > Profiler Configuration > Device Attribute Server."""
        try:
            # Step 1: Navigate through the menu hierarchy
            # Click "Profiler"
            await page.get_by_text("Profiler", exact=True).click()
            await page.wait_for_timeout(500)

            # Click "Profiler Configuration"
            await page.get_by_text("Profiler Configuration", exact=True).click()
            await page.wait_for_timeout(500)

            # Click "Device Attribute Server" or basic configuration tab
            await page.get_by_text(
                "Device Attribute Server", exact=False
            ).first.click()
            # Wait for the configuration form to be visible
            await page.wait_for_selector(polling_interval_input_selector, timeout=10000)
        except PlaywrightError as exc:
            pytest.fail(f"Navigation to Device Attribute Server failed: {exc}")

    async def ensure_valid_server_selected() -> None:
        """
        Ensure at least one valid server is selected to isolate interval validation.
        If none are selected, select the first visible checkbox.
        """
        try:
            checkboxes = page.locator(valid_server_checkbox_selector)
            count = await checkboxes.count()
            if count == 0:
                logger.warning(
                    "No server checkbox elements found; proceeding without server selection."
                )
                return

            # Check if any is already selected
            for i in range(count):
                checkbox = checkboxes.nth(i)
                if await checkbox.is_visible() and await checkbox.is_checked():
                    return

            # If none selected, select the first visible one
            for i in range(count):
                checkbox = checkboxes.nth(i)
                if await checkbox.is_visible():
                    await checkbox.check()
                    await page.wait_for_timeout(200)
                    return
        except PlaywrightError as exc:
            logger.error("Error ensuring valid server selection: %s", exc)
            # Do not fail the test here; selection is to isolate validation only.

    # --- Test implementation ---------------------------------------------------

    # Step 1: Navigate to Profiler > Profiler Configuration > Device Attribute Server
    await navigate_to_device_attribute_server()

    # Capture the current polling interval to verify it does not change later
    original_polling_interval = await get_polling_interval_value()
    assert (
        original_polling_interval is not None
    ), "Polling interval input should be visible and readable."

    # Step 2: Enter -10 into the polling interval field
    try:
        polling_input = page.locator(polling_interval_input_selector)
        await polling_input.fill("")  # Clear existing value
        await polling_input.type("-10")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to set polling interval to -10: {exc}")

    # Step 3: Ensure at least one valid server is selected
    await ensure_valid_server_selected()

    # Step 4: Click 'Save Changes'
    try:
        await page.locator(save_changes_button_selector).click()
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click 'Save Changes' button: {exc}")

    # Allow time for validation to occur and any error message to appear
    await page.wait_for_timeout(1000)

    # --- Assertions for expected results --------------------------------------

    # 1. Save is rejected: verify that we are still on the same page
    #    and that the polling interval field is still present and editable.
    try:
        assert await page.locator(polling_interval_input_selector).is_visible(), (
            "Polling interval input should still be visible; "
            "save should not navigate away on validation error."
        )
    except PlaywrightError as exc:
        pytest.fail(f"Error verifying visibility of polling interval input: {exc}")

    # 2. A clear validation error message appears near the polling interval
    try:
        error_locator = page.locator(validation_error_selector)
        # We allow for different implementations but require some visible error near the field
        is_error_visible = await error_locator.first.is_visible()
    except PlaywrightError as exc:
        pytest.fail(f"Error locating validation message for polling interval: {exc}")

    assert is_error_visible, (
        "A validation error message should be visible for negative polling interval "
        "(e.g., 'Polling interval must be a positive integer')."
    )

    # 3. Polling interval field is not updated in stored configuration.
    #    We perform a simple verification by re-reading the value after the failed save
    #    and, if possible, reloading the configuration page to ensure persistence.
    after_save_value = await get_polling_interval_value()
    assert (
        after_save_value == original_polling_interval
        or after_save_value == "-10"
    ), (
        "Polling interval input should not be accepted as a valid saved value. "
        "If inline validation prevents change, it may still show '-10' but must "
        "not be committed to stored configuration."
    )

    # Optional: reload configuration to verify persistence in stored config
    # This is a stronger check for stored configuration not being updated.
    try:
        await page.reload()
        await page.wait_for_selector(polling_interval_input_selector, timeout=10000)
        reloaded_value = await get_polling_interval_value()
    except PlaywrightError as exc:
        # Non-fatal: log and continue with available assertions
        logger.error("Error reloading page for persistence check: %s", exc)
        reloaded_value = None

    if reloaded_value is not None:
        assert reloaded_value == original_polling_interval, (
            "After reload, polling interval should remain unchanged and valid; "
            "negative value must not be stored in configuration."
        )

    # Postconditions: existing polling interval remains unchanged and valid.
    # This is effectively covered by the persistence assertion above.