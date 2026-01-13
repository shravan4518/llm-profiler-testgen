import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Error, expect


@pytest.mark.asyncio
async def test_zero_polling_interval_boundary(authenticated_page: Page, browser):
    """
    TC_014: Boundary test – zero polling interval

    Verify that a polling interval of `0` is either:
      - Disallowed with a clear validation error; OR
      - Treated as a special value meaning "disabled polling", with clear indication.

    Preconditions:
        - Admin user is already logged in (handled by authenticated_page fixture).

    Postconditions:
        - If invalid, previous interval is retained.
        - If used as “disabled”, profiler stops polling the Attribute Server.
    """
    page: Page = authenticated_page

    # Locators - adjust selectors to match the actual application under test.
    device_attr_server_link = page.get_by_role(
        "link", name="Device Attribute Server", exact=True
    )
    polling_interval_input = page.get_by_label(
        "Polling interval", exact=True
    )  # e.g. <input aria-label="Polling interval">
    save_changes_button = page.get_by_role(
        "button", name="Save Changes", exact=True
    )
    validation_error_locator = page.locator(
        "text=Polling interval must be greater than 0"
    )
    polling_disabled_indicator = page.locator(
        "text=Polling disabled"
    )  # e.g. label or status text
    profiler_status_indicator = page.locator(
        "text=Profiler status: Stopped"
    )  # e.g. label showing profiler stopped

    # -------------------------------------------------------------------------
    # Step 1: Navigate to Device Attribute Server configuration page
    # -------------------------------------------------------------------------
    try:
        await expect(device_attr_server_link).to_be_visible(timeout=10_000)
        await device_attr_server_link.click()
    except Error as exc:
        pytest.fail(f"Failed to navigate to Device Attribute Server page: {exc}")

    # Ensure the configuration page has loaded by checking for polling field
    try:
        await expect(polling_interval_input).to_be_visible(timeout=10_000)
    except Error as exc:
        pytest.fail(
            f"Polling interval field not visible on Device Attribute Server page: {exc}"
        )

    # -------------------------------------------------------------------------
    # Capture the current (previous) polling interval for postcondition checks
    # -------------------------------------------------------------------------
    previous_interval_value: Optional[str]
    try:
        previous_interval_value = await polling_interval_input.input_value()
    except Error as exc:
        pytest.fail(
            f"Unable to read current polling interval value before test: {exc}"
        )

    # -------------------------------------------------------------------------
    # Step 2: Enter `0` into the polling interval field
    # -------------------------------------------------------------------------
    try:
        await polling_interval_input.fill("")
        await polling_interval_input.type("0")
    except Error as exc:
        pytest.fail(f"Failed to enter zero into polling interval field: {exc}")

    # -------------------------------------------------------------------------
    # Step 3: Click `Save Changes`
    # -------------------------------------------------------------------------
    try:
        await expect(save_changes_button).to_be_enabled(timeout=5_000)
        await save_changes_button.click()
    except Error as exc:
        pytest.fail(f"Failed to click 'Save Changes' button: {exc}")

    # -------------------------------------------------------------------------
    # Expected Result Branching:
    #   A) Validation error shown and value not saved, OR
    #   B) 0 is accepted and polling clearly shown as disabled.
    #
    # We detect which behavior occurs and assert that at least one is true.
    # -------------------------------------------------------------------------

    # Give the UI a brief moment to respond
    await asyncio.sleep(1)

    # Check if validation error appears
    validation_error_visible = await validation_error_locator.is_visible()

    if validation_error_visible:
        # ---------------------------------------------------------------------
        # Branch A: 0 is invalid, validation error must be shown, value not saved
        # ---------------------------------------------------------------------
        await expect(validation_error_locator).to_be_visible()
        error_text = await validation_error_locator.inner_text()
        assert (
            "Polling interval must be greater than 0" in error_text
        ), "Validation error text does not match expected requirement."

        # Confirm that the previous interval is retained (no change committed)
        # Reload the page or re-open the section to ensure we read persisted value.
        # Here we simply re-query the field; adapt if actual app requires reload.
        await page.reload()
        await expect(polling_interval_input).to_be_visible(timeout=10_000)

        current_value_after_error = await polling_interval_input.input_value()
        assert (
            current_value_after_error == previous_interval_value
        ), (
            "Polling interval value changed despite validation error; "
            "previous interval should be retained."
        )

    else:
        # ---------------------------------------------------------------------
        # Branch B: 0 is accepted as "disabled polling"
        # ---------------------------------------------------------------------

        # Re-query the field to ensure the saved value is 0
        await expect(polling_interval_input).to_be_visible(timeout=10_000)
        current_value_after_save = await polling_interval_input.input_value()
        assert current_value_after_save in ("0", "0.0"), (
            "Polling interval was saved without validation error, "
            "but the persisted value is not 0."
        )

        # Assert that the UI clearly indicates polling is disabled
        await expect(polling_disabled_indicator).to_be_visible(
            timeout=10_000
        )

        # Optionally check profiler status indicator if available
        if await profiler_status_indicator.is_visible():
            status_text = await profiler_status_indicator.inner_text()
            assert "Stopped" in status_text or "Disabled" in status_text, (
                "Profiler status does not indicate polling is stopped/disabled "
                "after setting interval to 0."
            )

    # Note:
    # Final state (whether validation error or disabled polling) must align
    # with system documentation. That documentation check is typically done
    # outside of automated tests, but this test ensures the behavior is
    # deterministic and clearly observable.