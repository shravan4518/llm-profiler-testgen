import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_configure_polling_interval_above_maximum(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_014: Configure polling interval above maximum allowed value

    Title:
        Configure polling interval above maximum allowed value

    Description:
        Validate that setting polling interval above documented maximum
        (e.g., 1440 minutes) is rejected or clamped.

    Preconditions:
        - User is logged in as `ppsadmin` via `authenticated_page` fixture.
        - Maximum allowed interval is assumed to be 1440 minutes.

    Steps:
        1. Navigate to Device Attribute Server configuration.
        2. Read current polling interval (for later comparison).
        3. Enter `10000` in Polling interval field.
        4. Click `Save Changes`.

    Expected Results:
        - System rejects the value and shows an error (e.g.,
          “Polling interval must be between X and Y minutes”)
          OR automatically adjusts to the maximum allowed (e.g., 1440).
        - No value above max is persisted.
        - Postcondition: Polling interval is either unchanged or set to
          max allowed value (1440).

    Notes:
        - This test assumes specific selectors for navigation and fields.
          Adjust selectors to match the actual DOM of the target system.
    """
    page: Page = authenticated_page
    max_allowed_interval = 1440
    invalid_interval_value = 10000

    # Helper: robustly get integer value from polling interval field
    async def get_polling_interval_value() -> Optional[int]:
        try:
            input_locator = page.locator("#pollingInterval")
            await input_locator.wait_for(state="visible", timeout=5000)
            raw_value = (await input_locator.input_value()).strip()
            if not raw_value:
                return None
            return int(raw_value)
        except ValueError:
            logger.error("Polling interval value is not an integer.")
            return None
        except PlaywrightError as exc:
            logger.error("Failed to read polling interval value: %s", exc)
            return None

    # Helper: safely click and log errors
    async def safe_click(selector: str, description: str) -> None:
        try:
            await page.locator(selector).click()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click {description} ({selector}): {exc}")

    # ------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin`.
    # ------------------------------------------------------------------
    # This step is handled by the `authenticated_page` fixture.
    # Validate we are on the admin landing page.
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightError as exc:
        pytest.fail(f"Page did not reach network idle state after login: {exc}")

    # Optional sanity check that we are on the expected domain/URL.
    current_url = page.url
    assert "welcome.cgi" in current_url, (
        f"Unexpected URL after login: {current_url}"
    )

    # ------------------------------------------------------------------
    # Step 2: Navigate to Device Attribute Server configuration.
    # ------------------------------------------------------------------
    # NOTE: These selectors are examples and must be aligned with the
    # actual application under test.
    try:
        # Example navigation through admin menu
        await safe_click("text=Configuration", "Configuration menu")
        await safe_click("text=Device Attribute Server", "Device Attribute Server menu")

        # Wait for the Device Attribute Server configuration section
        await page.locator("text=Device Attribute Server Configuration").wait_for(
            state="visible", timeout=10000
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Device Attribute Server configuration: {exc}")

    # ------------------------------------------------------------------
    # Step 3 (pre-step): Capture current polling interval for comparison.
    # ------------------------------------------------------------------
    original_interval_value = await get_polling_interval_value()

    # It is acceptable if it's None, but we log it for debugging.
    logger.info("Original polling interval value: %s", original_interval_value)

    # ------------------------------------------------------------------
    # Step 3: Enter `10000` in Polling interval field.
    # ------------------------------------------------------------------
    try:
        polling_input = page.locator("#pollingInterval")
        await polling_input.wait_for(state="visible", timeout=5000)
        await polling_input.fill(str(invalid_interval_value))
    except PlaywrightError as exc:
        pytest.fail(f"Failed to set polling interval to {invalid_interval_value}: {exc}")

    # ------------------------------------------------------------------
    # Step 4: Click `Save Changes`.
    # ------------------------------------------------------------------
    await safe_click("button:has-text('Save Changes')", "Save Changes button")

    # Wait briefly for any validation or save operation to complete
    await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Expected Result: Either validation error OR clamping to max value.
    # ------------------------------------------------------------------

    # Potential selectors for error message (adjust as needed).
    error_locators = [
        page.locator(".error-message:has-text('Polling interval')"),
        page.locator("text=Polling interval must be between"),
        page.locator("#pollingInterval-error"),
    ]

    error_message_found = False
    for locator in error_locators:
        try:
            if await locator.is_visible():
                error_message_found = True
                break
        except PlaywrightError:
            # Ignore locator-specific errors and continue checking others
            continue

    # Re-read the value after save attempt
    current_interval_value = await get_polling_interval_value()
    logger.info("Current polling interval value after save: %s", current_interval_value)

    # ------------------------------------------------------------------
    # Assertion logic:
    #
    # Valid outcomes:
    #   A) Error message is shown and value is not persisted above max.
    #   B) No error message, but value is clamped to max_allowed_interval.
    #
    # Invalid outcomes:
    #   - Value above max is persisted.
    # ------------------------------------------------------------------
    if error_message_found:
        # Path A: Validation error is displayed.
        assert (
            current_interval_value is None
            or current_interval_value <= max_allowed_interval
        ), (
            "Polling interval is above maximum even though an error "
            f"was displayed. Value: {current_interval_value}, "
            f"max allowed: {max_allowed_interval}"
        )
    else:
        # Path B: No explicit error message; verify clamping behavior.
        assert current_interval_value is not None, (
            "Polling interval value could not be read after save; "
            "expected it to be clamped or unchanged."
        )
        assert current_interval_value <= max_allowed_interval, (
            "Polling interval was persisted above maximum without an "
            f"error message. Value: {current_interval_value}, "
            f"max allowed: {max_allowed_interval}"
        )

    # ------------------------------------------------------------------
    # Postcondition: Polling interval is unchanged or set to max allowed.
    # ------------------------------------------------------------------
    if original_interval_value is not None:
        assert current_interval_value in (
            original_interval_value,
            max_allowed_interval,
        ), (
            "Polling interval postcondition not met. Expected value to "
            "remain unchanged or be clamped to max allowed. "
            f"Original: {original_interval_value}, "
            f"Current: {current_interval_value}, "
            f"Max allowed: {max_allowed_interval}"
        )
    else:
        # If original was undefined/empty, we at least ensure clamping.
        assert current_interval_value <= max_allowed_interval, (
            "Polling interval postcondition not met; value above max "
            f"was persisted. Current: {current_interval_value}, "
            f"Max allowed: {max_allowed_interval}"
        )