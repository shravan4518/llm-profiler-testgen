import asyncio
import re
import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_008_non_numeric_polling_interval_not_accepted(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_008: Attempt to save configuration with non-numeric polling interval

    Objective:
        Verify that non-numeric input (e.g., text) in polling interval is not
        accepted and that the previous numeric value remains unchanged.

    Precondition:
        - Admin is already logged in via `authenticated_page` fixture.

    Steps:
        1. Navigate to the polling interval configuration page.
        2. Enter "seven hundred" in the polling interval field.
        3. Click "Save Changes".

    Expected Results:
        - Validation error is displayed, specifying that the value must be numeric.
        - No changes are saved to system configuration.
        - Polling interval remains at the previous numeric value.
    """

    page = authenticated_page

    # Locators (update selectors to match actual application under test)
    polling_config_nav_selector = "a#nav-polling-interval"  # example
    polling_interval_input_selector = "input#pollingInterval"  # example
    save_changes_button_selector = "button#saveChanges"  # example
    validation_error_selector = "div.validation-error"  # example

    # Helper: robustly get numeric value from the polling interval field
    async def get_polling_interval_value() -> int:
        """Return the current numeric polling interval value as int."""
        try:
            value_text = await page.locator(polling_interval_input_selector).input_value()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to read polling interval input value: {exc}")

        value_text = value_text.strip()
        if not value_text:
            pytest.fail("Polling interval input is empty; expected numeric value.")

        # Extract digits to be resilient to formatting like "700 ms"
        digits = re.findall(r"\d+", value_text)
        if not digits:
            pytest.fail(
                f"Polling interval value is not numeric as expected: '{value_text}'"
            )

        return int(digits[0])

    # -------------------------------------------------------------------------
    # Step 1: Navigate to the polling interval configuration page
    # -------------------------------------------------------------------------
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to load admin welcome page: {exc}")

    try:
        await page.locator(polling_config_nav_selector).click()
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to polling interval configuration page: {exc}")

    # Ensure the polling interval input is visible
    try:
        await page.locator(polling_interval_input_selector).wait_for(state="visible")
    except PlaywrightError as exc:
        pytest.fail(
            f"Polling interval input field not visible on configuration page: {exc}"
        )

    # Capture the current (valid) polling interval value for later comparison
    original_polling_interval = await get_polling_interval_value()

    # -------------------------------------------------------------------------
    # Step 2: Enter `seven hundred` in the polling interval field
    # -------------------------------------------------------------------------
    non_numeric_value = "seven hundred"
    polling_interval_input = page.locator(polling_interval_input_selector)

    try:
        await polling_interval_input.fill("")  # clear any existing value
        await polling_interval_input.type(non_numeric_value)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to enter non-numeric polling interval value: {exc}")

    # Verify that the field actually contains the non-numeric text
    current_value = await polling_interval_input.input_value()
    assert current_value == non_numeric_value, (
        f"Expected polling interval input to contain '{non_numeric_value}', "
        f"but found '{current_value}'."
    )

    # -------------------------------------------------------------------------
    # Step 3: Click `Save Changes`
    # -------------------------------------------------------------------------
    save_button = page.locator(save_changes_button_selector)
    try:
        await save_button.wait_for(state="visible")
        await save_button.click()
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click 'Save Changes' button: {exc}")

    # -------------------------------------------------------------------------
    # Expected Result 1:
    # Validation error is displayed, specifying that the value must be numeric.
    # -------------------------------------------------------------------------
    validation_error_locator = page.locator(validation_error_selector)

    try:
        await validation_error_locator.wait_for(timeout=5000, state="visible")
    except PlaywrightError:
        pytest.fail(
            "Validation error message was not displayed after submitting "
            "non-numeric polling interval."
        )

    validation_error_text = (await validation_error_locator.inner_text()).strip().lower()
    # Adjust keywords to match actual application error message
    numeric_keywords = ["numeric", "number", "digits"]
    assert any(keyword in validation_error_text for keyword in numeric_keywords), (
        "Validation error message does not clearly indicate that the value must "
        f"be numeric. Actual message: '{validation_error_text}'"
    )

    # -------------------------------------------------------------------------
    # Expected Result 2 & Postcondition:
    # No changes are saved to system configuration.
    # Polling interval remains at the previous numeric value.
    # -------------------------------------------------------------------------
    # Refresh or re-open the configuration page to ensure we read persisted value
    try:
        await page.reload(wait_until="networkidle")
        await page.locator(polling_interval_input_selector).wait_for(state="visible")
    except PlaywrightError as exc:
        pytest.fail(
            f"Failed to reload configuration page to verify persisted value: {exc}"
        )

    persisted_polling_interval = await get_polling_interval_value()

    assert (
        persisted_polling_interval == original_polling_interval
    ), (
        "Polling interval configuration was changed despite validation error. "
        f"Expected '{original_polling_interval}', but found "
        f"'{persisted_polling_interval}'."
    )

    # Additional safety check: field should not persist the non-numeric text
    persisted_raw_value = await page.locator(polling_interval_input_selector).input_value()
    assert persisted_raw_value != non_numeric_value, (
        "Non-numeric value was persisted in the polling interval field, "
        f"found '{persisted_raw_value}'."
    )