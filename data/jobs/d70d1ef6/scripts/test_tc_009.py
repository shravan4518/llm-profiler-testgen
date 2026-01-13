import asyncio
from typing import List

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_009_basic_config_required_fields_validation(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_009: Attempt to save basic configuration without required fields

    Title:
        Attempt to save basic configuration without required fields

    Category:
        Negative

    Priority:
        High

    Description:
        Validate that required fields (e.g., Profiler Name or IP) cannot be left
        blank when saving configuration. The system must show validation errors
        and must not persist any partial configuration.

    Preconditions:
        - User is logged in as `ppsadmin` via authenticated_page fixture.
        - User has access to Basic Configuration page.

    Postconditions:
        - Previous configuration is preserved; no new configuration is saved.
    """
    page: Page = authenticated_page

    # -------------------------------------------------------------------------
    # Helper selectors (adjust as needed to match actual application)
    # -------------------------------------------------------------------------
    basic_config_nav_selector = "a:has-text('Basic Configuration')"
    save_changes_button_selector = "button:has-text('Save Changes')"

    # Example required field selectors (update to real selectors in AUT)
    profiler_name_input_selector = "input[name='profilerName']"
    profiler_ip_input_selector = "input[name='profilerIp']"

    # Example validation messages (update to real messages in AUT)
    profiler_name_error_selector = "text=Profiler Name is required"
    profiler_ip_error_selector = "text=IP is required"

    # A generic selector for required field indicators (e.g., asterisk)
    # This can be refined based on actual markup:
    required_field_indicator_selector = "label:has-text('*')"

    # -------------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin`
    # -------------------------------------------------------------------------
    # The authenticated_page fixture is assumed to have already performed login
    # and landed on a post-login page. We add a sanity assertion.
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reach post-login state: {exc}")

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Basic Configuration page
    # -------------------------------------------------------------------------
    try:
        await page.click(basic_config_nav_selector)
        await page.wait_for_load_state("networkidle", timeout=10000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Basic Configuration page: {exc}")

    # Optional check that we are on the correct page (adjust to real locator)
    # e.g., heading text or breadcrumb
    basic_config_heading_selector = "h1:has-text('Basic Configuration')"
    try:
        await page.wait_for_selector(basic_config_heading_selector, timeout=10000)
    except PlaywrightError as exc:
        pytest.fail(f"Basic Configuration page did not load as expected: {exc}")

    # -------------------------------------------------------------------------
    # Capture current configuration to validate that it is preserved later
    # -------------------------------------------------------------------------
    previous_profiler_name: str = ""
    previous_profiler_ip: str = ""
    try:
        previous_profiler_name = await page.locator(
            profiler_name_input_selector
        ).input_value()
        previous_profiler_ip = await page.locator(
            profiler_ip_input_selector
        ).input_value()
    except PlaywrightError:
        # If fields are not present or not readable, fail fast
        pytest.fail("Unable to read current Basic Configuration values.")

    # -------------------------------------------------------------------------
    # Step 3: Clear all fields that appear required
    #         (e.g., Profiler Name, IP)
    # -------------------------------------------------------------------------
    required_input_selectors: List[str] = [
        profiler_name_input_selector,
        profiler_ip_input_selector,
    ]

    for selector in required_input_selectors:
        try:
            locator = page.locator(selector)
            await locator.wait_for(state="visible", timeout=5000)
            await locator.fill("")  # Clear the field
        except PlaywrightError as exc:
            pytest.fail(f"Failed to clear required field '{selector}': {exc}")

    # -------------------------------------------------------------------------
    # Step 4: Ensure all required checkboxes are in default state
    # -------------------------------------------------------------------------
    # This is application-specific. Below is a template approach:
    # - Identify required checkboxes by a data attribute or label pattern.
    # - Ensure they are set to a default (e.g., unchecked).
    #
    # Adjust the selector to match the AUT. For now, this is defensive and
    # will not fail if no such checkboxes exist.
    required_checkbox_locator = page.locator(
        "input[type='checkbox'][data-required='true']"
    )

    try:
        checkbox_count = await required_checkbox_locator.count()
        for idx in range(checkbox_count):
            checkbox = required_checkbox_locator.nth(idx)
            is_checked = await checkbox.is_checked()
            # Assuming default state is unchecked; change as needed:
            if is_checked:
                await checkbox.uncheck()
    except PlaywrightError as exc:
        pytest.fail(f"Failed while normalizing required checkbox states: {exc}")

    # -------------------------------------------------------------------------
    # Step 5: Click `Save Changes`
    # -------------------------------------------------------------------------
    try:
        await page.click(save_changes_button_selector)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click 'Save Changes' button: {exc}")

    # Give the UI a moment to respond with validation messages
    await asyncio.sleep(1)

    # -------------------------------------------------------------------------
    # Expected Result 1:
    #   System prevents saving and shows validation errors for each missing
    #   required field (e.g., “Profiler Name is required”).
    # -------------------------------------------------------------------------
    try:
        # Assert profiler name validation message
        await page.wait_for_selector(
            profiler_name_error_selector,
            timeout=5000,
            state="visible",
        )

        # Assert profiler IP validation message
        await page.wait_for_selector(
            profiler_ip_error_selector,
            timeout=5000,
            state="visible",
        )
    except PlaywrightError as exc:
        pytest.fail(
            "Expected validation errors for required fields were not displayed: "
            f"{exc}"
        )

    # Optional: assert that we are still on the same page (no redirect)
    try:
        await page.wait_for_selector(
            basic_config_heading_selector,
            timeout=5000,
            state="visible",
        )
    except PlaywrightError as exc:
        pytest.fail(
            "User was unexpectedly redirected after invalid save attempt: "
            f"{exc}"
        )

    # -------------------------------------------------------------------------
    # Expected Result 2:
    #   No partial configuration is stored.
    #   Postcondition:
    #       Previous configuration is preserved; no new configuration saved.
    # -------------------------------------------------------------------------
    # Reload or re-open the Basic Configuration page to confirm values.
    try:
        await page.reload(wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reload Basic Configuration page: {exc}")

    # Re-read values after the failed save attempt
    try:
        current_profiler_name = await page.locator(
            profiler_name_input_selector
        ).input_value()
        current_profiler_ip = await page.locator(
            profiler_ip_input_selector
        ).input_value()
    except PlaywrightError as exc:
        pytest.fail(f"Unable to read Basic Configuration values after save: {exc}")

    # Assert that previous configuration is preserved
    # If the system intentionally clears them on validation failure but does
    # not persist, adapt this assertion accordingly.
    assert (
        current_profiler_name == previous_profiler_name
    ), (
        "Profiler Name configuration was changed or partially saved despite "
        "validation errors."
    )

    assert (
        current_profiler_ip == previous_profiler_ip
    ), (
        "Profiler IP configuration was changed or partially saved despite "
        "validation errors."
    )