import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_minimum_valid_polling_interval_boundary(authenticated_page: Page) -> None:
    """
    TC_012: Boundary test – minimum valid polling interval value

    Title:
        Boundary test – minimum valid polling interval value

    Objective:
        Verify that the system accepts the minimum allowed polling interval value
        (1 minute) without validation errors and correctly persists the value.

    Prerequisites:
        - Admin user is logged in (handled by `authenticated_page` fixture).
        - Business rule: minimum interval is 1 minute unless specified otherwise.

    Steps:
        1. Navigate to Device Attribute Server configuration page.
        2. Enter `1` in the polling interval field.
        3. Ensure at least one server is selected.
        4. Click `Save Changes`.
        5. Check for any warnings about too frequent polling.
        6. Confirm that the saved value is `1`.

    Expected Results:
        - Value `1` is accepted if within specification.
        - Configuration is saved, and interval shows as `1`.
        - No validation errors occur.
    """
    page: Page = authenticated_page

    # Helper selectors (update these to match actual application DOM)
    device_attr_menu_selector = "a#menu-device-attribute-server"
    config_page_header_selector = "h1:has-text('Device Attribute Server')"
    polling_interval_input_selector = "input#pollingInterval"
    server_checkbox_selector = "input[name='serverEnabled']"
    save_button_selector = "button:has-text('Save Changes')"
    success_message_selector = "text=Configuration saved"
    validation_error_selector = ".error-message, .validation-error"
    warning_message_selector = "text=too frequent polling, text=high load, text=minimum interval"  # generic
    polling_interval_display_selector = "#pollingInterval, input#pollingInterval"

    minimum_valid_interval = "1"

    async def safe_wait_for_selector(
        selector: str,
        timeout: int = 10000,
        state: str = "visible",
    ) -> Optional[object]:
        """Safely wait for a selector; return locator or None on timeout."""
        try:
            locator = page.locator(selector)
            await locator.wait_for(timeout=timeout, state=state)  # type: ignore[arg-type]
            return locator
        except PlaywrightError as exc:
            logger.error("Timeout waiting for selector '%s': %s", selector, exc)
            return None

    # Step 1: Navigate to Device Attribute Server configuration page.
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open admin welcome page: {exc}")

    # If the configuration page is accessible via a menu link, click it.
    # If not required, this block can be removed or adjusted.
    try:
        if await page.locator(device_attr_menu_selector).count() > 0:
            await page.click(device_attr_menu_selector)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Device Attribute Server page: {exc}")

    header_locator = await safe_wait_for_selector(config_page_header_selector, timeout=15000)
    assert header_locator is not None, (
        "Device Attribute Server configuration page header not found; "
        "navigation to configuration page may have failed."
    )

    # Step 2: Enter `1` in the polling interval field.
    polling_interval_input = await safe_wait_for_selector(polling_interval_input_selector)
    assert polling_interval_input is not None, (
        "Polling interval input field not found on the configuration page."
    )

    try:
        await polling_interval_input.fill("")  # type: ignore[union-attr]
        await polling_interval_input.type(minimum_valid_interval)  # type: ignore[union-attr]
    except PlaywrightError as exc:
        pytest.fail(f"Failed to set polling interval to '{minimum_valid_interval}': {exc}")

    # Optional: assert the input value immediately after typing.
    current_value = await page.locator(polling_interval_input_selector).input_value()
    assert (
        current_value == minimum_valid_interval
    ), f"Polling interval input value mismatch: expected '{minimum_valid_interval}', got '{current_value}'."

    # Step 3: Ensure at least one server is selected.
    server_checkbox = await safe_wait_for_selector(server_checkbox_selector)
    assert server_checkbox is not None, (
        "No server selection checkbox found; at least one server must be selectable."
    )

    try:
        is_checked = await server_checkbox.is_checked()  # type: ignore[union-attr]
        if not is_checked:
            await server_checkbox.check()  # type: ignore[union-attr]
    except PlaywrightError as exc:
        pytest.fail(f"Failed to ensure at least one server is selected: {exc}")

    # Step 4: Click `Save Changes`.
    save_button = await safe_wait_for_selector(save_button_selector)
    assert save_button is not None, "Save Changes button not found on the configuration page."

    try:
        await save_button.click()  # type: ignore[union-attr]
        # Wait briefly for any post-save operations (navigation, reload, etc.)
        await page.wait_for_timeout(2000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click Save Changes button: {exc}")

    # Step 5: Check for any warnings about too frequent polling.
    # Note: A warning may or may not be expected depending on business rules.
    # Here we assert that no *blocking* validation errors occur, but tolerate
    # non-blocking informational warnings if they appear.
    await asyncio.sleep(1)  # small delay to allow messages to render

    # Assert there are no validation errors visible
    try:
        error_locators = page.locator(validation_error_selector)
        error_count = await error_locators.count()
    except PlaywrightError as exc:
        pytest.fail(f"Failed while checking for validation errors: {exc}")

    assert error_count == 0, (
        "Validation errors were displayed after saving with minimum polling interval. "
        f"Found {error_count} error message element(s)."
    )

    # Optionally log any non-blocking warnings if they exist (do not fail test)
    try:
        warning_locators = page.locator(warning_message_selector)
        warning_count = await warning_locators.count()
        if warning_count > 0:
            logger.warning(
                "Non-blocking warnings about frequent polling detected (%d). "
                "Verify if this is expected per specification.",
                warning_count,
            )
    except PlaywrightError as exc:
        logger.error("Error while checking for warnings: %s", exc)

    # Step 6: Confirm that the saved value is `1`.
    # Wait for a success message or some indication that save completed.
    success_msg = await safe_wait_for_selector(success_message_selector, timeout=10000)
    # If the system does not display a success message, this assertion can be relaxed.
    assert success_msg is not None, (
        "Configuration success message not found after saving. "
        "Verify if the application uses a different indicator for successful save."
    )

    # Re-read the polling interval field to ensure the value persisted.
    try:
        # Some UIs may re-render as a read-only display; hence the combined selector.
        interval_display_locator = page.locator(polling_interval_display_selector).first
        await interval_display_locator.wait_for(timeout=10000)
        saved_value = await interval_display_locator.input_value()
    except PlaywrightError:
        # Fallback: try to read text content if input_value is not supported.
        try:
            saved_value = (await interval_display_locator.text_content() or "").strip()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to read saved polling interval value: {exc}")

    assert (
        saved_value == minimum_valid_interval
    ), f"Saved polling interval value mismatch: expected '{minimum_valid_interval}', got '{saved_value}'."

    # Final assertion summary:
    # - No validation errors were present.
    # - The polling interval was saved and persisted as '1'.
    # - Any warnings, if present, are non-blocking and logged for review.