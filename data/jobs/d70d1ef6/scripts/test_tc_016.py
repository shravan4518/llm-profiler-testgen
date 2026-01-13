import asyncio
import re
from typing import List, Tuple

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_016_boundary_device_attribute_servers(authenticated_page: Page) -> None:
    """
    TC_016: Boundary test for enabling/disabling all Device Attribute Servers.

    Title:
        Boundary test for enabling/disabling all Device Attribute Servers

    Description:
        Validate behavior when zero servers and when all available servers are
        selected for Device Attribute Server configuration.

    Prerequisites:
        - Logged in as ppsadmin via `authenticated_page` fixture.
        - At least two configured servers: `das1`, `das2`.

    Scenarios:
        Scenario A:
            - Move all servers from Selected Servers back to Available Servers.
            - Click "Save Changes".
            - System either:
                a) Allows configuration (no polling), or
                b) Warns that at least one server must be selected.
        Scenario B:
            - Move all servers from Available to Selected Servers.
            - Set polling interval to 60.
            - Click "Save Changes".
            - System accepts configuration and polls all selected servers
              at defined interval.

    Postconditions:
        - Configuration aligns with explicit rules regarding minimum number
          of selected servers.
    """
    page = authenticated_page

    # -------------------------------------------------------------------------
    # Helper functions
    # -------------------------------------------------------------------------
    async def navigate_to_device_attribute_servers_config(page: Page) -> None:
        """
        Navigate to the Device Attribute Server configuration page.

        Note:
            The actual selectors and navigation steps are assumptions and
            must be adapted to the real UI under test.
        """
        try:
            # Example: navigation via an admin menu; adapt as needed.
            # Click "System" or "Device" menu
            await page.click("text=System")  # or "text=Devices" depending on UI
            await page.click("text=Device Attribute Servers")

            # Wait for the configuration form to be visible
            await page.wait_for_selector("form#device-attribute-server-form", timeout=10000)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to navigate to Device Attribute Server configuration: {exc}"
            ) from exc

    async def get_dual_list_elements(page: Page) -> Tuple[List[str], List[str]]:
        """
        Read the current state of Available and Selected server lists.

        Returns:
            Tuple[List[str], List[str]]:
                (available_servers, selected_servers)
        """
        # These selectors are assumptions; adjust to actual DOM:
        available_selector = "select#available-servers option"
        selected_selector = "select#selected-servers option"

        try:
            available_options = await page.query_selector_all(available_selector)
            selected_options = await page.query_selector_all(selected_selector)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Unable to locate server dual-list elements: {exc}"
            ) from exc

        available_servers = [
            (await option.text_content() or "").strip()
            for option in available_options
        ]
        selected_servers = [
            (await option.text_content() or "").strip()
            for option in selected_options
        ]

        return available_servers, selected_servers

    async def move_all_to_available(page: Page) -> None:
        """
        Move all servers from Selected to Available.
        """
        # Select all in Selected Servers listbox
        selected_list_selector = "select#selected-servers"
        move_left_button_selector = "button#btn-move-left"

        try:
            selected_list = await page.wait_for_selector(selected_list_selector, timeout=5000)
            # Select all options
            await selected_list.select_option(value="all")  # if "all" not valid, use JS
        except PlaywrightError:
            # Fallback: select via JS (handles multiple options)
            await page.evaluate(
                """
                (sel) => {
                    const select = document.querySelector(sel);
                    if (!select) throw new Error('Selected list not found');
                    for (const opt of select.options) {
                        opt.selected = true;
                    }
                }
                """,
                selected_list_selector,
            )

        # Click the "<<" button to move to Available
        try:
            await page.click(move_left_button_selector)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to move servers from Selected to Available: {exc}"
            ) from exc

        # Wait a moment for UI update
        await asyncio.sleep(0.5)

    async def move_all_to_selected(page: Page) -> None:
        """
        Move all servers from Available to Selected.
        """
        available_list_selector = "select#available-servers"
        move_right_button_selector = "button#btn-move-right"

        try:
            available_list = await page.wait_for_selector(available_list_selector, timeout=5000)
            await available_list.select_option(value="all")
        except PlaywrightError:
            # Fallback: select via JS
            await page.evaluate(
                """
                (sel) => {
                    const select = document.querySelector(sel);
                    if (!select) throw new Error('Available list not found');
                    for (const opt of select.options) {
                        opt.selected = true;
                    }
                }
                """,
                available_list_selector,
            )

        try:
            await page.click(move_right_button_selector)
        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to move servers from Available to Selected: {exc}"
            ) from exc

        await asyncio.sleep(0.5)

    async def save_changes(page: Page) -> None:
        """
        Click the 'Save Changes' button and wait for response or status area.
        """
        try:
            await page.click("button:has-text('Save Changes')")
        except PlaywrightError as exc:
            raise AssertionError(f"Failed to click 'Save Changes': {exc}") from exc

        # Wait for either a success or error message, or just for network idle
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except PlaywrightError:
            # Not fatal; UI might not trigger navigation
            pass

    async def get_feedback_messages(page: Page) -> Tuple[List[str], List[str]]:
        """
        Collect visible success and error/warning messages after save.

        Returns:
            (success_messages, error_messages)
        """
        # These selectors are assumptions and should be adapted to real app:
        success_selector = ".msg-success, .alert-success, .ui-message-success"
        error_selector = ".msg-error, .alert-danger, .alert-warning, .ui-message-error"

        success_elements = await page.query_selector_all(success_selector)
        error_elements = await page.query_selector_all(error_selector)

        success_messages = [
            (await el.text_content() or "").strip() for el in success_elements
        ]
        error_messages = [
            (await el.text_content() or "").strip() for el in error_elements
        ]

        # Filter out empty strings
        success_messages = [m for m in success_messages if m]
        error_messages = [m for m in error_messages if m]

        return success_messages, error_messages

    async def set_polling_interval(page: Page, interval: int) -> None:
        """
        Set the polling interval field to the specified value.
        """
        polling_input_selector = "input#polling-interval"

        try:
            await page.fill(polling_input_selector, "")
            await page.fill(polling_input_selector, str(interval))
        except PlaywrightError as exc:
            raise AssertionError(
                f"Unable to set polling interval to {interval}: {exc}"
            ) from exc

    # -------------------------------------------------------------------------
    # Step 1 & 2: Already logged in by fixture; navigate to configuration
    # -------------------------------------------------------------------------
    await navigate_to_device_attribute_servers_config(page)

    # Validate there are at least two servers in total across both lists
    available_servers, selected_servers = await get_dual_list_elements(page)
    total_servers = len(available_servers) + len(selected_servers)
    assert total_servers >= 2, (
        f"Expected at least 2 configured servers, found {total_servers}. "
        f"Available: {available_servers}, Selected: {selected_servers}"
    )

    # -------------------------------------------------------------------------
    # Scenario A: Move all servers from Selected to Available and save
    # -------------------------------------------------------------------------

    # Step 3: Move all servers from Selected Servers back to Available Servers
    await move_all_to_available(page)

    # Verify that Selected list is empty
    _, selected_after_move = await get_dual_list_elements(page)
    assert len(selected_after_move) == 0, (
        "Scenario A: Expected no servers in Selected list after moving all to "
        f"Available, but found: {selected_after_move}"
    )

    # Step 4: Click 'Save Changes'
    await save_changes(page)

    # Step 5: Observe errors or warnings
    success_msgs_a, error_msgs_a = await get_feedback_messages(page)

    # Expected behavior: either accept configuration or warn about at least one server
    # We accept both behaviors but assert that one of them occurs clearly.
    scenario_a_has_success = any(
        re.search(r"(saved|updated|success)", msg, re.IGNORECASE)
        for msg in success_msgs_a
    )
    scenario_a_has_min_warning = any(
        re.search(r"(at least one server|minimum.*server)", msg, re.IGNORECASE)
        for msg in error_msgs_a
    )

    assert scenario_a_has_success or scenario_a_has_min_warning, (
        "Scenario A: When zero servers are selected, expected either a clear "
        "success message or a clear warning that at least one server must be "
        "selected. "
        f"Success messages: {success_msgs_a}, Error/Warning messages: {error_msgs_a}"
    )

    # -------------------------------------------------------------------------
    # Scenario B: Move all servers from Available to Selected, set interval, save
    # -------------------------------------------------------------------------

    # Step 6: Move all servers from Available to Selected Servers
    await move_all_to_selected(page)

    available_after_b, selected_after_b = await get_dual_list_elements(page)
    assert len(selected_after_b) == total_servers, (
        "Scenario B: Expected all servers to be in Selected list, "
        f"but only {len(selected_after_b)} of {total_servers} present. "
        f"Selected: {selected_after_b}, Available: {available_after_b}"
    )

    # Optional: ensure das1 and das2 are among selected if they exist
    for expected_name in ("das1", "das2"):
        if any(expected_name in s for s in available_servers + selected_servers):
            assert any(expected_name in s for s in selected_after_b), (
                f"Scenario B: Expected server '{expected_name}' to be selected, "
                f"but it is not in Selected list: {selected_after_b}"
            )

    # Step 7: Set polling interval to 60
    await set_polling_interval(page, 60)

    # Step 8: Click 'Save Changes'
    await save_changes(page)

    success_msgs_b, error_msgs_b = await get_feedback_messages(page)

    # Scenario B expected: configuration is accepted; no blocking errors
    assert not error_msgs_b, (
        "Scenario B: Expected no error or warning messages when all servers "
        f"are selected with polling interval 60, but found: {error_msgs_b}"
    )

    assert any(
        re.search(r"(saved|updated|success)", msg, re.IGNORECASE)
        for msg in success_msgs_b
    ), (
        "Scenario B: Expected a success/confirmation message after saving "
        "configuration with all servers selected and polling interval 60, "
        f"but success messages were: {success_msgs_b}"
    )

    # Optionally verify that polling interval persisted as 60
    # (Assumes page stays on same form and value is not reformatted)
    try:
        polling_value = await page.input_value("input#polling-interval")
        assert polling_value.strip() in {"60", "60.0"}, (
            "Scenario B: Polling interval did not persist as 60 after save. "
            f"Actual value: '{polling_value}'"
        )
    except PlaywrightError:
        # If input not available after save, do not fail the test on this
        # secondary verification.
        pass