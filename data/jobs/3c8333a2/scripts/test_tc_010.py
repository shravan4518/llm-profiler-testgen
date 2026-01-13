import asyncio
import logging
from typing import List

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_no_device_attribute_server_selected_validation(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_010: Validation when no Device Attribute Server selected

    Ensure profiler does not accept configuration with polling enabled but no
    selected Device Attribute Servers when at least one is required.

    Preconditions:
        - Admin is logged in (handled by authenticated_page fixture).
        - At least one Device Attribute Server is listed under Available Servers.

    Steps:
        1. Navigate to Device Attribute Server configuration page.
        2. Ensure that all servers are in Available Servers and none are in Selected Servers.
        3. Set polling interval to `720`.
        4. Click `Save Changes`.

    Expected:
        - Save is rejected with a validation error message.
        - No new configuration is applied (previous effective configuration remains).
    """
    page = authenticated_page

    # Locators (update selectors as needed to match actual application DOM)
    device_attr_nav_selector = "a#nav-device-attribute-server, a[href*='device_attribute_servers']"
    available_servers_list_selector = "#available-servers, select#availableServers"
    selected_servers_list_selector = "#selected-servers, select#selectedServers"
    move_to_selected_button_selector = "button#btn-move-to-selected, button#btn-add"
    move_to_available_button_selector = "button#btn-move-to-available, button#btn-remove"
    polling_interval_input_selector = "input#polling-interval, input[name='pollingInterval']"
    save_changes_button_selector = "button#btn-save, input[type='submit'][value='Save Changes']"
    validation_error_selector = (
        ".validation-error, .error, div[role='alert'], span.error-message"
    )

    # Some UIs show current effective configuration in a label or text field.
    # This is used to verify that no new configuration is applied.
    effective_config_summary_selector = "#effective-config-summary, #current-config"

    try:
        # ---------------------------------------------------------------------
        # Step 1: Navigate to Device Attribute Server configuration page
        # ---------------------------------------------------------------------
        await page.wait_for_load_state("networkidle")

        # Click navigation link to Device Attribute Server configuration
        nav_link = page.locator(device_attr_nav_selector).first
        await nav_link.wait_for(state="visible", timeout=10_000)
        await nav_link.click()
        await page.wait_for_load_state("networkidle")

        # Basic sanity check that we are on the expected page
        await page.wait_for_timeout(500)  # small delay for DOM to settle
        assert await page.locator("text=Device Attribute Server").first.is_visible(), (
            "Device Attribute Server configuration page did not load as expected."
        )

        # Capture current effective configuration summary (if available)
        previous_effective_config: str = ""
        if await page.locator(effective_config_summary_selector).first.is_visible():
            previous_effective_config = (
                await page.locator(effective_config_summary_selector).inner_text()
            )

        # ---------------------------------------------------------------------
        # Step 2: Ensure all servers are in Available Servers and none in Selected
        # ---------------------------------------------------------------------
        available_list = page.locator(available_servers_list_selector)
        selected_list = page.locator(selected_servers_list_selector)

        await available_list.wait_for(state="visible", timeout=10_000)
        await selected_list.wait_for(state="visible", timeout=10_000)

        # Helper to get option texts from a <select> element
        async def get_option_texts(select_locator) -> List[str]:
            option_elements = select_locator.locator("option")
            count = await option_elements.count()
            texts: List[str] = []
            for i in range(count):
                texts.append(await option_elements.nth(i).inner_text())
            return texts

        # Ensure there is at least one available server (precondition)
        available_servers_before = await get_option_texts(available_list)
        assert available_servers_before, (
            "Precondition failed: No Device Attribute Servers are listed under Available Servers."
        )

        # Move any selected servers back to available (if any)
        selected_servers_before = await get_option_texts(selected_list)
        if selected_servers_before:
            logger.info(
                "Moving %d servers from Selected to Available: %s",
                len(selected_servers_before),
                ", ".join(selected_servers_before),
            )
            # Select all options in selected list
            await selected_list.select_option(
                value=[await selected_list.locator("option").nth(i).get_attribute("value")
                       for i in range(len(selected_servers_before))]
            )
            move_to_available_button = page.locator(move_to_available_button_selector).first
            await move_to_available_button.wait_for(state="visible", timeout=5_000)
            await move_to_available_button.click()
            await page.wait_for_timeout(500)

        # Verify postcondition of step 2: no servers in Selected, at least one in Available
        available_servers_after = await get_option_texts(available_list)
        selected_servers_after = await get_option_texts(selected_list)

        assert available_servers_after, (
            "All Device Attribute Servers disappeared from Available list; "
            "test cannot continue."
        )
        assert not selected_servers_after, (
            "There are still servers in Selected Servers list; expected none."
        )

        # ---------------------------------------------------------------------
        # Step 3: Set polling interval to 720
        # ---------------------------------------------------------------------
        polling_input = page.locator(polling_interval_input_selector).first
        await polling_input.wait_for(state="visible", timeout=10_000)

        # Clear existing value and set to 720
        await polling_input.fill("")
        await polling_input.type("720")

        # Optional: verify the value is set correctly
        polling_value = await polling_input.input_value()
        assert polling_value == "720", (
            f"Polling interval value is '{polling_value}', expected '720'."
        )

        # ---------------------------------------------------------------------
        # Step 4: Click Save Changes
        # ---------------------------------------------------------------------
        save_button = page.locator(save_changes_button_selector).first
        await save_button.wait_for(state="visible", timeout=10_000)
        await save_button.click()

        # Wait briefly for validation to occur
        await page.wait_for_timeout(1_000)

        # ---------------------------------------------------------------------
        # Expected Result 1: Save is rejected with validation error
        # ---------------------------------------------------------------------
        validation_error_locator = page.locator(validation_error_selector)
        await validation_error_locator.first.wait_for(state="visible", timeout=10_000)

        error_text = (await validation_error_locator.inner_text()).strip()
        assert error_text, "Validation error element is visible but contains no text."

        # Accept a range of likely messages; adjust as needed to match system
        expected_phrases = [
            "at least one device attribute server must be selected",
            "select at least one device attribute server",
            "no device attribute server selected",
        ]
        error_text_lower = error_text.lower()
        assert any(phrase in error_text_lower for phrase in expected_phrases), (
            "Unexpected validation error message.\n"
            f"Actual: {error_text}\n"
            f"Expected to contain one of: {expected_phrases}"
        )

        # ---------------------------------------------------------------------
        # Expected Result 2: No new configuration is applied
        # ---------------------------------------------------------------------
        # If the UI exposes a current/effective configuration summary, verify it
        if previous_effective_config:
            # Allow a short delay in case UI re-renders
            await page.wait_for_timeout(1_000)
            current_effective_config = (
                await page.locator(effective_config_summary_selector).inner_text()
            )
            assert current_effective_config == previous_effective_config, (
                "Effective configuration changed despite validation error.\n"
                f"Before: {previous_effective_config}\n"
                f"After:  {current_effective_config}"
            )
        else:
            # If there was no previous configuration summary, we can at least
            # assert that the polling interval field still shows 720 and that
            # the validation error is present, indicating save did not succeed.
            # Depending on the application, you might also assert that the page
            # did not navigate away or that a 'success' message is absent.
            assert await validation_error_locator.first.is_visible(), (
                "Validation error is no longer visible; save may have succeeded unexpectedly."
            )

    except PlaywrightError as playwright_error:
        logger.error("Playwright error during test execution: %s", playwright_error)
        # Optionally capture screenshot for debugging
        try:
            await page.screenshot(path="tc_010_no_device_attr_server_error.png", full_page=True)
        except Exception:
            # If screenshot fails, do not mask the original error
            pass
        raise
    except AssertionError:
        # Capture screenshot on assertion failures as well
        try:
            await page.screenshot(path="tc_010_no_device_attr_server_assertion.png", full_page=True)
        except Exception:
            pass
        raise
    finally:
        # Small delay for stability / debugging; not strictly required
        await asyncio.sleep(0.5)