import asyncio
import pytest
from playwright.async_api import Page, Error


@pytest.mark.asyncio
async def test_polling_interval_rejects_non_numeric_value(authenticated_page: Page, browser):
    """
    TC_010: Enter non-numeric value in polling interval field

    Validate that the polling interval field for Device Attribute Server or Profiler
    configuration rejects non-numeric input.

    Preconditions:
        - User is logged in as `ppsadmin` via authenticated_page fixture.
        - User has access to Device Attribute Server configuration page.

    Steps:
        1. Log in as `ppsadmin`.  (handled by authenticated_page fixture)
        2. Navigate to Device Attribute Server configuration page.
        3. In the Polling interval field, type `sixty`.
        4. Click `Save Changes`.

    Expected:
        - System rejects the value and displays a validation error.
        - Field may auto-correct or clear invalid input.
        - No change to stored polling interval (remains last valid numeric value).
    """

    page: Page = authenticated_page

    # NOTE:
    # The actual selectors/URLs below are assumptions.
    # Replace CSS/xpath/text selectors with the real ones from your AUT.

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Device Attribute Server configuration page
    # -------------------------------------------------------------------------
    try:
        # Example: navigate via direct URL or through UI navigation
        # If navigation is via menu, replace with appropriate clicks instead.
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/device_attribute_server.cgi",
            wait_until="domcontentloaded",
        )
    except Error as exc:
        pytest.fail(f"Failed to navigate to Device Attribute Server configuration page: {exc}")

    # Ensure we are on the expected configuration page
    # Adjust selector/text to match actual page heading or unique element.
    await page.wait_for_timeout(500)  # small stabilization delay
    assert await page.locator("text=Device Attribute Server Configuration").first.is_visible(), (
        "Device Attribute Server Configuration page did not load as expected."
    )

    # -------------------------------------------------------------------------
    # Capture the current (valid) polling interval before negative test
    # -------------------------------------------------------------------------
    polling_interval_input = page.locator("input[name='pollingInterval']")

    try:
        await polling_interval_input.wait_for(state="visible", timeout=5000)
    except Error as exc:
        pytest.fail(f"Polling interval field not found or not visible: {exc}")

    # Read the currently stored valid numeric value
    last_valid_value = await polling_interval_input.input_value()
    assert last_valid_value.strip() != "", (
        "Precondition failure: polling interval field is empty; expected a valid numeric value."
    )

    # -------------------------------------------------------------------------
    # Step 3: Enter non-numeric value 'sixty' into polling interval field
    # -------------------------------------------------------------------------
    await polling_interval_input.fill("")  # clear existing value
    await polling_interval_input.type("sixty")

    # Optionally blur the field to trigger client-side validation
    await polling_interval_input.blur()

    # -------------------------------------------------------------------------
    # Step 4: Click "Save Changes"
    # -------------------------------------------------------------------------
    save_button = page.get_by_role("button", name="Save Changes")

    try:
        await save_button.wait_for(state="visible", timeout=5000)
    except Error as exc:
        pytest.fail(f'Save Changes button not found or not visible: {exc}')

    await save_button.click()

    # -------------------------------------------------------------------------
    # Expected Result 1: Validation error is displayed
    # -------------------------------------------------------------------------
    # Adjust selector/text for your actual validation message.
    # We allow for slight text variations but check for numeric requirement.
    validation_locator = page.locator(
        "text=/Polling interval.*(must be a number|numeric|invalid)/i"
    )

    try:
        await validation_locator.wait_for(state="visible", timeout=5000)
    except Error:
        # If specific text not found, try a more generic error indicator
        generic_error = page.locator(".error-message, .validation-error, .error")
        try:
            await generic_error.wait_for(state="visible", timeout=3000)
        except Error as exc:
            pytest.fail(
                "Expected a validation error message for non-numeric polling interval, "
                f"but none was found: {exc}"
            )
        else:
            # At least some error is visible; assert its content mentions polling interval
            error_text = (await generic_error.first.text_content() or "").lower()
            assert "polling" in error_text or "interval" in error_text, (
                "An error message appeared, but it does not reference the polling interval field."
            )
    else:
        assert await validation_locator.is_visible(), (
            "Validation message for polling interval is not visible."
        )

    # -------------------------------------------------------------------------
    # Expected Result 2: Field may auto-correct or clear invalid input
    # -------------------------------------------------------------------------
    # After validation, the field should not contain the non-numeric string "sixty".
    current_field_value = await polling_interval_input.input_value()
    assert current_field_value != "sixty", (
        "Polling interval field still contains the invalid non-numeric value 'sixty'."
    )

    # -------------------------------------------------------------------------
    # Expected Result 3: No change to stored polling interval
    # -------------------------------------------------------------------------
    # To be robust, re-load or re-open the page to ensure persisted value is unchanged.
    # This assumes that a failed validation does not commit changes.
    try:
        await page.reload(wait_until="domcontentloaded")
    except Error as exc:
        pytest.fail(f"Failed to reload configuration page to verify stored value: {exc}")

    # Re-locate the polling interval field after reload
    polling_interval_input_after_reload = page.locator("input[name='pollingInterval']")
    try:
        await polling_interval_input_after_reload.wait_for(state="visible", timeout=5000)
    except Error as exc:
        pytest.fail(
            f"Polling interval field not visible after reload when verifying stored value: {exc}"
        )

    stored_value_after_reload = await polling_interval_input_after_reload.input_value()

    # Assert that the value after reload is the same as the last valid numeric value
    assert stored_value_after_reload == last_valid_value, (
        "Stored polling interval changed after entering non-numeric value; "
        f"expected '{last_valid_value}', got '{stored_value_after_reload}'."
    )