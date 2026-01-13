import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_maximum_valid_polling_interval_value(authenticated_page: Page, browser):
    """
    TC_013: Boundary test – maximum valid polling interval value

    Title:
        Boundary test – maximum valid polling interval value

    Description:
        Validate behavior at the upper limit of the allowed polling interval
        (assumed 10080 minutes = 7 days). Ensures the value is accepted,
        no validation errors are shown, and the value persists after reload.

    Preconditions:
        - Admin is logged in (provided by authenticated_page fixture).
        - Known maximum allowed polling interval: 10080.

    Steps:
        1. Navigate to Device Attribute Server configuration page.
        2. Enter 10080 into polling interval field.
        3. Ensure at least one server is selected.
        4. Click "Save Changes".
        5. Verify no validation errors.
        6. Reload configuration and verify polling interval remains 10080.

    Expected Results:
        - Value 10080 is accepted as valid.
        - No validation error messages are displayed.
        - After reload, polling interval field shows 10080.
    """
    page: Page = authenticated_page
    max_polling_interval = "10080"

    # NOTE:
    # The following selectors are assumptions and should be updated to match
    # the actual application DOM:
    device_attr_server_nav_selector = "a[href*='device_attribute_server']"
    polling_interval_input_selector = "input[name='polling_interval']"
    server_checkbox_selector = "input[type='checkbox'][name='server_selected']"
    save_changes_button_selector = "button:has-text('Save Changes'), input[type='submit'][value='Save Changes']"
    validation_error_selector = ".error, .validation-error, [role='alert']"
    success_message_selector = ".success, .alert-success, .message-success"

    # Helper function to log and raise a more descriptive error
    async def safe_click(selector: str, description: str) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10_000)
            await page.click(selector)
        except PlaywrightError as exc:
            logger.error("Failed to click %s using selector '%s': %s", description, selector, exc)
            raise AssertionError(f"Could not click {description} (selector: {selector})") from exc

    async def safe_fill(selector: str, value: str, description: str) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10_000)
            await page.fill(selector, value)
        except PlaywrightError as exc:
            logger.error(
                "Failed to fill %s using selector '%s' with value '%s': %s",
                description,
                selector,
                value,
                exc,
            )
            raise AssertionError(f"Could not fill {description} (selector: {selector})") from exc

    async def ensure_at_least_one_server_selected() -> None:
        """Ensure at least one server checkbox is selected."""
        try:
            await page.wait_for_selector(server_checkbox_selector, timeout=10_000)
            server_checkboxes = await page.query_selector_all(server_checkbox_selector)
        except PlaywrightError as exc:
            logger.error("Failed to locate server checkboxes: %s", exc)
            raise AssertionError("Server checkboxes not found on configuration page") from exc

        if not server_checkboxes:
            raise AssertionError("No server checkboxes found; cannot ensure selection")

        # Check if any checkbox is already selected
        for checkbox in server_checkboxes:
            try:
                is_checked = await checkbox.is_checked()
            except PlaywrightError as exc:
                logger.warning("Failed to read checkbox state: %s", exc)
                continue
            if is_checked:
                # At least one server is already selected
                return

        # If none are selected, select the first one
        try:
            await server_checkboxes[0].check()
        except PlaywrightError as exc:
            logger.error("Failed to check first server checkbox: %s", exc)
            raise AssertionError("Could not select a server checkbox") from exc

    # Step 1: Navigate to Device Attribute Server configuration page
    # If the fixture already lands on the correct page, this navigation
    # will simply ensure we are on the right section.
    await safe_click(
        device_attr_server_nav_selector,
        description="Device Attribute Server configuration navigation link",
    )

    # Optional: wait for a known element on the configuration page to ensure it loaded
    try:
        await page.wait_for_selector(polling_interval_input_selector, state="visible", timeout=10_000)
    except PlaywrightError as exc:
        logger.error("Polling interval input not visible after navigation: %s", exc)
        raise AssertionError("Device Attribute Server configuration page did not load correctly") from exc

    # Step 2: Enter 10080 into polling interval field
    await safe_fill(
        polling_interval_input_selector,
        max_polling_interval,
        description="Polling interval input field",
    )

    # Step 3: Ensure at least one server is selected
    await ensure_at_least_one_server_selected()

    # Step 4: Click "Save Changes"
    await safe_click(save_changes_button_selector, description="'Save Changes' button")

    # Step 5: Verify no validation errors and (optionally) a success message
    # Give the page some time to process the save
    await asyncio.sleep(1)

    # Assert that no obvious validation error messages are visible
    try:
        error_elements = await page.query_selector_all(validation_error_selector)
    except PlaywrightError as exc:
        logger.warning("Error while querying validation error elements: %s", exc)
        error_elements = []

    visible_errors = []
    for element in error_elements:
        try:
            if await element.is_visible():
                text = (await element.text_content()) or ""
                visible_errors.append(text.strip())
        except PlaywrightError:
            # Ignore elements that cannot be inspected
            continue

    assert not visible_errors, (
        "Validation errors were displayed after saving polling interval: "
        f"{visible_errors}"
    )

    # Optionally check for a success message (if the app uses one)
    success_message: Optional[str] = None
    try:
        success_element = await page.query_selector(success_message_selector)
        if success_element and await success_element.is_visible():
            success_message = (await success_element.text_content() or "").strip()
    except PlaywrightError:
        # Lack of success message is not a hard failure unless required
        success_message = None

    # Step 6: Reload configuration and verify polling interval remains 10080
    await page.reload(wait_until="networkidle")

    try:
        await page.wait_for_selector(polling_interval_input_selector, state="visible", timeout=10_000)
        current_value = await page.input_value(polling_interval_input_selector)
    except PlaywrightError as exc:
        logger.error("Failed to read polling interval after reload: %s", exc)
        raise AssertionError("Could not verify polling interval after reload") from exc

    assert (
        current_value == max_polling_interval
    ), f"Polling interval did not persist; expected {max_polling_interval}, got {current_value}"

    # Optional informational logging
    logger.info(
        "TC_013 passed: polling interval set to %s and persisted after reload. "
        "Success message: %s",
        max_polling_interval,
        success_message,
    )