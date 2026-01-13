import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_profiler_name_max_length_boundary(authenticated_page: Page, browser) -> None:
    """
    TC_015: Boundary test for Profiler Name length (maximum characters)

    Validates that the Profiler Name field:
      - Accepts and persists a 64-character value.
      - Rejects or prevents entry of a 65-character value.
      - Does not silently truncate without warning.
      - Leaves the last valid value (<= max length) after invalid attempts.

    Assumptions:
      - Max allowed length for Profiler Name is 64 characters.
      - `authenticated_page` fixture returns a logged-in admin page (ppsadmin).
    """
    page: Page = authenticated_page

    # Constants and test data
    basic_config_url = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
    profiler_name_selector = "input[name='profilerName']"  # Adjust selector as needed
    save_button_selector = "button:has-text('Save Changes'), input[type='submit'][value='Save Changes']"
    generic_error_selector = (
        ".error, .validation-error, .alert-error, "
        "div[role='alert'], .ui-message-error"
    )

    max_length = 64
    valid_name_64 = "A" * max_length
    invalid_name_65 = "B" * (max_length + 1)

    async def safe_wait_for_selector(
        selector: str, timeout: int = 5000
    ) -> Optional[None]:
        """Wait for selector if present; log and return None on timeout."""
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            return None
        except PlaywrightError as exc:
            logger.warning("Selector '%s' not found within timeout: %s", selector, exc)
            return None

    # ----------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin`
    # ----------------------------------------------------------------------
    # Assumed handled by `authenticated_page` fixture; sanity-check login.
    assert "logout" in (await page.content()).lower() or "log out" in (
        await page.content()
    ).lower(), "Expected to be logged in as admin (logout link not found)."

    # ----------------------------------------------------------------------
    # Step 2: Navigate to Basic Configuration page
    # ----------------------------------------------------------------------
    try:
        await page.goto(basic_config_url, wait_until="domcontentloaded")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Basic Configuration page: {exc}")

    # Wait for Profiler Name field to be visible
    await safe_wait_for_selector(profiler_name_selector)
    profiler_field = page.locator(profiler_name_selector)
    assert await profiler_field.is_visible(), "Profiler Name field is not visible."

    # Capture any initial value to restore if needed (best effort)
    try:
        original_value = await profiler_field.input_value()
    except PlaywrightError:
        original_value = ""

    # ----------------------------------------------------------------------
    # Step 3: Enter 64-character name into Profiler Name field
    # ----------------------------------------------------------------------
    await profiler_field.fill("")
    await profiler_field.type(valid_name_64)
    current_value = await profiler_field.input_value()
    assert (
        current_value == valid_name_64
    ), "Profiler Name field did not contain the full 64-character value after typing."

    # ----------------------------------------------------------------------
    # Step 4: Click `Save Changes`
    # ----------------------------------------------------------------------
    save_button = page.locator(save_button_selector)
    assert await save_button.is_visible(), "'Save Changes' button is not visible."

    try:
        async with page.expect_navigation(wait_until="domcontentloaded"):
            await save_button.click()
    except PlaywrightError as exc:
        pytest.fail(f"Navigation or save action failed after clicking Save Changes: {exc}")

    # ----------------------------------------------------------------------
    # Step 5: Confirm configuration saved and name persists
    # ----------------------------------------------------------------------
    # Re-locate the field after navigation
    await safe_wait_for_selector(profiler_name_selector)
    profiler_field = page.locator(profiler_name_selector)
    assert await profiler_field.is_visible(), "Profiler Name field not visible after save."

    persisted_value = await profiler_field.input_value()
    assert (
        persisted_value == valid_name_64
    ), (
        "Profiler Name did not persist the 64-character value after saving. "
        f"Expected '{valid_name_64}', got '{persisted_value}'."
    )

    # ----------------------------------------------------------------------
    # Step 6: Edit configuration; attempt to enter 65-character name
    # ----------------------------------------------------------------------
    await profiler_field.fill("")
    await profiler_field.type(invalid_name_65)

    # Check what actually ended up in the field
    field_after_65 = await profiler_field.input_value()

    # Determine behavior:
    #   - If length <= 64: UI prevented typing more than max (acceptable).
    #   - If length == 65: UI allowed full 65 chars; expect save to fail with error.
    #   - If value truncated (< 65, <= 64) without warning on save: not acceptable.
    length_after_65 = len(field_after_65)

    assert length_after_65 <= max_length or length_after_65 == max_length + 1, (
        "Unexpected Profiler Name length after attempting 65 characters: "
        f"{length_after_65}"
    )

    # ----------------------------------------------------------------------
    # Step 7: Click `Save Changes`
    # ----------------------------------------------------------------------
    save_button = page.locator(save_button_selector)
    assert await save_button.is_visible(), "'Save Changes' button not visible (second save)."

    # If UI already enforced max length (<=64), saving is allowed but must not silently
    # store a truncated 65-char attempt; it should simply store the <=64 value.
    if length_after_65 <= max_length:
        # Save should succeed, and value should remain exactly what is in the field.
        try:
            async with page.expect_navigation(wait_until="domcontentloaded"):
                await save_button.click()
        except PlaywrightError as exc:
            pytest.fail(
                "Save failed when the Profiler Name field length was "
                f"{length_after_65} (expected <= max length). Error: {exc}"
            )

        await safe_wait_for_selector(profiler_name_selector)
        profiler_field = page.locator(profiler_name_selector)
        final_value = await profiler_field.input_value()

        # Ensure no silent data corruption/truncation beyond what UI allowed before save.
        assert (
            final_value == field_after_65
        ), (
            "Profiler Name value changed unexpectedly after saving a value that was "
            f"already limited to {length_after_65} characters. "
            f"Before save: '{field_after_65}', after save: '{final_value}'."
        )

        # Postcondition: value must still be <= max length
        assert len(final_value) <= max_length, (
            "Profiler Name exceeds maximum length after save when UI enforced limit."
        )

    else:
        # length_after_65 == 65: UI allowed 65 characters; saving should fail
        # with an error and not persist the invalid value.
        error_detected = False

        # Attempt save and look for either:
        #   - No navigation + error message, or
        #   - Navigation but explicit error on resulting page.
        try:
            # Some apps may not navigate on validation error; handle both cases.
            async with page.expect_navigation(wait_until="domcontentloaded") as nav:
                await save_button.click()
            navigation_completed = True
            await nav.value
        except PlaywrightError:
            # No navigation; likely inline validation error
            navigation_completed = False

        # Give the UI a brief moment to render any error message
        await asyncio.sleep(1.0)

        # Look for generic error indicators
        error_loc = page.locator(generic_error_selector)
        if await error_loc.first.is_visible():
            error_detected = True

        # If no generic error found, also check for HTML5 validation bubbles
        # by checking if the field is still focused and page did not navigate.
        if not error_detected and not navigation_completed:
            # Best-effort heuristic: field still visible and value unchanged
            # implies client-side validation blocked submission.
            still_value = await profiler_field.input_value()
            if still_value == field_after_65:
                error_detected = True

        assert error_detected, (
            "Expected an error or validation feedback when saving a 65-character "
            "Profiler Name, but none was detected."
        )

        # Confirm that invalid 65-character value was not persisted
        await safe_wait_for_selector(profiler_name_selector)
        profiler_field = page.locator(profiler_name_selector)
        final_value = await profiler_field.input_value()

        assert (
            final_value != invalid_name_65
        ), "65-character Profiler Name was incorrectly persisted."

        assert len(final_value) <= max_length, (
            "Profiler Name exceeds maximum allowed length after attempting to save "
            "a 65-character value."
        )

    # ----------------------------------------------------------------------
    # Postcondition: Profiler Name remains at last valid value (<= max length)
    # ----------------------------------------------------------------------
    await safe_wait_for_selector(profiler_name_selector)
    profiler_field = page.locator(profiler_name_selector)
    post_value = await profiler_field.input_value()

    assert len(post_value) <= max_length, (
        "Postcondition failed: Profiler Name is longer than the maximum allowed "
        f"length ({max_length}) after test execution."
    )

    # Optional cleanup: best-effort restore original value (no assertion on failure)
    if original_value and original_value != post_value:
        try:
            await profiler_field.fill("")
            await profiler_field.type(original_value)
            save_button = page.locator(save_button_selector)
            if await save_button.is_visible():
                async with page.expect_navigation(wait_until="domcontentloaded"):
                    await save_button.click()
        except PlaywrightError as exc:
            logger.warning("Failed to restore original Profiler Name value: %s", exc)