import asyncio
import logging
from typing import List

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_enable_additional_data_collectors_ldap_mdm(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_006: Enable additional data collectors (LDAP and MDM)

    Validates configuration of additional data collectors for endpoint attributes
    through MDM and LDAP servers.

    Steps:
        1. Navigate to Profiler > Profiler Configuration > Additional Data Collectors.
        2. In the LDAP section, select LDAP-ACME from available list and move it
           to selected list.
        3. In the MDM section, select MDM-AirWatch and move it to selected list.
        4. Click Save Changes.
        5. Verify that a success message is shown.
        6. Reload the page and verify both servers remain in selected lists.

    Expected:
        - Additional data collectors are successfully configured.
        - Settings persist after reload.
        - No validation or connectivity errors are thrown at save-time
          (unless connectivity checks are synchronous and fail).
    """
    page = authenticated_page

    # Test data
    ldap_collector_name = "LDAP-ACME"
    mdm_collector_name = "MDM-AirWatch"

    # Helper selectors (update to match actual application DOM)
    profiler_menu_selector = "text=Profiler"
    profiler_config_menu_selector = "text=Profiler Configuration"
    additional_collectors_menu_selector = "text=Additional Data Collectors"

    ldap_available_list_selector = "select#ldap-available"
    ldap_selected_list_selector = "select#ldap-selected"
    ldap_move_to_selected_button_selector = "button#ldap-add"

    mdm_available_list_selector = "select#mdm-available"
    mdm_selected_list_selector = "select#mdm-selected"
    mdm_move_to_selected_button_selector = "button#mdm-add"

    save_changes_button_selector = "button:has-text('Save Changes')"
    success_message_selector = ".alert-success, .message-success, text=Success"
    error_message_selector = ".alert-danger, .message-error, .validation-error"

    async def select_option_and_move(
        available_selector: str,
        selected_selector: str,
        move_button_selector: str,
        option_label: str,
    ) -> None:
        """Select an option from available list and move it to selected list."""
        try:
            # Ensure the available list is visible
            await page.wait_for_selector(available_selector, state="visible", timeout=10000)

            # Verify the option exists in the available list
            available_options: List[str] = await page.eval_on_selector(
                available_selector,
                """(select) => Array.from(select.options).map(o => o.textContent.trim())""",
            )
            assert option_label in available_options, (
                f"Option '{option_label}' not found in available list "
                f"({available_selector}). Available: {available_options}"
            )

            # Select the option in the available list
            await page.select_option(
                available_selector,
                label=option_label,
            )

            # Click the move button
            await page.click(move_button_selector)

            # Verify the option is now in the selected list
            selected_options: List[str] = await page.eval_on_selector(
                selected_selector,
                """(select) => Array.from(select.options).map(o => o.textContent.trim())""",
            )
            assert option_label in selected_options, (
                f"Option '{option_label}' was not moved to selected list "
                f"({selected_selector}). Selected: {selected_options}"
            )

        except PlaywrightError as exc:
            logger.error(
                "Error while moving option '%s' from '%s' to '%s': %s",
                option_label,
                available_selector,
                selected_selector,
                exc,
            )
            raise

    async def assert_option_in_selected(
        selected_selector: str,
        option_label: str,
    ) -> None:
        """Assert that an option is present in the selected list."""
        await page.wait_for_selector(selected_selector, state="visible", timeout=10000)
        selected_options: List[str] = await page.eval_on_selector(
            selected_selector,
            """(select) => Array.from(select.options).map(o => o.textContent.trim())""",
        )
        assert option_label in selected_options, (
            f"Option '{option_label}' not present in selected list "
            f"({selected_selector}) after reload. Selected: {selected_options}"
        )

    # -------------------------------------------------------------------------
    # Step 1: Navigate to Profiler > Profiler Configuration > Additional Data Collectors
    # -------------------------------------------------------------------------
    try:
        # Navigate via menu (adjust selectors to actual UI)
        await page.wait_for_selector(profiler_menu_selector, state="visible", timeout=15000)
        await page.click(profiler_menu_selector)

        await page.wait_for_selector(profiler_config_menu_selector, state="visible", timeout=15000)
        await page.click(profiler_config_menu_selector)

        await page.wait_for_selector(
            additional_collectors_menu_selector,
            state="visible",
            timeout=15000,
        )
        await page.click(additional_collectors_menu_selector)

        # Wait for the Additional Data Collectors page to fully load
        await page.wait_for_load_state("networkidle")
        await page.wait_for_selector(ldap_available_list_selector, timeout=20000)
        await page.wait_for_selector(mdm_available_list_selector, timeout=20000)
    except PlaywrightError as exc:
        logger.error("Failed to navigate to Additional Data Collectors page: %s", exc)
        raise

    # -------------------------------------------------------------------------
    # Step 2: In the LDAP section, select LDAP-ACME and move it to selected list
    # -------------------------------------------------------------------------
    await select_option_and_move(
        available_selector=ldap_available_list_selector,
        selected_selector=ldap_selected_list_selector,
        move_button_selector=ldap_move_to_selected_button_selector,
        option_label=ldap_collector_name,
    )

    # -------------------------------------------------------------------------
    # Step 3: In the MDM section, select MDM-AirWatch and move it to selected list
    # -------------------------------------------------------------------------
    await select_option_and_move(
        available_selector=mdm_available_list_selector,
        selected_selector=mdm_selected_list_selector,
        move_button_selector=mdm_move_to_selected_button_selector,
        option_label=mdm_collector_name,
    )

    # -------------------------------------------------------------------------
    # Step 4: Click Save Changes
    # -------------------------------------------------------------------------
    try:
        await page.wait_for_selector(save_changes_button_selector, state="visible", timeout=10000)
        await page.click(save_changes_button_selector)
    except PlaywrightError as exc:
        logger.error("Failed to click 'Save Changes' button: %s", exc)
        raise

    # -------------------------------------------------------------------------
    # Step 5: Verify that a success message is shown
    #         and that no validation/connectivity errors are displayed.
    # -------------------------------------------------------------------------
    try:
        # Wait for either success or error message to appear
        success_or_error = await asyncio.wait_for(
            asyncio.gather(
                page.wait_for_selector(success_message_selector, timeout=15000),
                return_exceptions=True,
            ),
            timeout=16000,
        )
    except asyncio.TimeoutError:
        success_or_error = [None]

    # Check for explicit error messages first
    error_visible = await page.is_visible(error_message_selector)
    assert not error_visible, "Validation or connectivity error message is visible after save."

    # Check success message
    success_visible = await page.is_visible(success_message_selector)
    assert success_visible, (
        "Expected a success message after saving additional data collectors, "
        "but none was found."
    )

    # -------------------------------------------------------------------------
    # Step 6: Reload the page and verify both servers remain in selected lists
    # -------------------------------------------------------------------------
    try:
        await page.reload()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_selector(ldap_selected_list_selector, timeout=20000)
        await page.wait_for_selector(mdm_selected_list_selector, timeout=20000)
    except PlaywrightError as exc:
        logger.error("Failed to reload Additional Data Collectors page: %s", exc)
        raise

    # Verify LDAP collector persists
    await assert_option_in_selected(
        selected_selector=ldap_selected_list_selector,
        option_label=ldap_collector_name,
    )

    # Verify MDM collector persists
    await assert_option_in_selected(
        selected_selector=mdm_selected_list_selector,
        option_label=mdm_collector_name,
    )