import asyncio
import re
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_configure_device_attribute_server_polling_interval_and_servers(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_006: Configure Device Attribute Server polling interval and servers

    Validate that Device Attribute Server configuration can be set with a custom
    polling interval and server selection and that Profiler polls servers accordingly.

    Prerequisites:
        - At least two HTTP Attribute Servers configured in PPS: `das1` and `das2`.
        - Profiler integrated with controller as HTTP Attribute Server per admin guide.

    This test:
        1. Navigates to Profiler > Profiler Configuration > Device Attribute Server settings.
        2. Sets Polling interval to 60 minutes.
        3. Moves `das1` to Selected Servers and ensures `das2` remains in Available Servers.
        4. Saves changes and verifies persistence of settings.
        5. Forces/awaits polling and validates logs show polling to `das1` only.
    """

    page = authenticated_page

    # Helper selectors (update these to match actual application DOM)
    profiler_menu_selector = "a[href*='profiler']"
    profiler_config_menu_selector = "a[href*='profiler-config']"
    das_settings_tab_selector = "a[href*='device-attribute-server']"

    polling_interval_input_selector = "input[name='poll_interval']"
    available_servers_list_selector = "#available_servers"
    selected_servers_list_selector = "#selected_servers"
    add_server_button_selector = "button#add_server"
    save_changes_button_selector = "button#save_changes"

    # Optional: a way to trigger immediate polling if supported (placeholder)
    force_poll_button_selector = "button#force_poll"

    # Log-related selectors/placeholders (update to real selectors/endpoints)
    logs_menu_selector = "a[href*='profiler-logs']"
    logs_frame_selector = "iframe#logs_frame"
    logs_container_selector = "#logs_container"

    das1_name = "das1"
    das2_name = "das2"
    desired_polling_interval = "60"

    # 1. Log in as `ppsadmin`.
    #    This is handled by the `authenticated_page` fixture from conftest.py.
    #    We still verify that we are on the admin landing page.
    try:
        await page.wait_for_url(
            re.compile(r".*/dana-na/auth/url_admin/.*"),
            timeout=15_000,
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to confirm authenticated admin session: {exc}")

    # 2. Navigate to Profiler > Profiler Configuration > Device Attribute Server settings page.
    try:
        # Open Profiler section
        await page.click(profiler_menu_selector)
        await page.wait_for_load_state("networkidle")

        # Open Profiler Configuration
        await page.click(profiler_config_menu_selector)
        await page.wait_for_load_state("networkidle")

        # Open Device Attribute Server settings tab/page
        await page.click(das_settings_tab_selector)
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Device Attribute Server settings: {exc}")

    # 3. Set Polling interval to `60`.
    try:
        polling_interval_input = page.locator(polling_interval_input_selector)
        await polling_interval_input.wait_for(state="visible", timeout=10_000)
        await polling_interval_input.fill("")  # Clear any existing value
        await polling_interval_input.type(desired_polling_interval)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to set polling interval to {desired_polling_interval}: {exc}")

    # 4. Move `das1` from Available Servers to Selected Servers.
    try:
        available_servers_list = page.locator(available_servers_list_selector)
        selected_servers_list = page.locator(selected_servers_list_selector)

        await available_servers_list.wait_for(state="visible", timeout=10_000)
        await selected_servers_list.wait_for(state="visible", timeout=10_000)

        # Select `das1` in Available Servers list
        das1_option = available_servers_list.locator(f"option[value='{das1_name}'], option:has-text('{das1_name}')")
        await das1_option.wait_for(state="visible", timeout=5_000)
        await das1_option.click()

        # Click the "Add" button to move it to Selected Servers
        await page.click(add_server_button_selector)

        # Verify `das1` is now in Selected Servers list
        das1_in_selected = selected_servers_list.locator(
            f"option[value='{das1_name}'], option:has-text('{das1_name}')"
        )
        await das1_in_selected.wait_for(state="visible", timeout=5_000)

    except PlaywrightError as exc:
        pytest.fail(f"Failed to move {das1_name} to Selected Servers: {exc}")

    # 5. Ensure `das2` remains in Available Servers list.
    try:
        das2_in_available = page.locator(available_servers_list_selector).locator(
            f"option[value='{das2_name}'], option:has-text('{das2_name}')"
        )
        await das2_in_available.wait_for(state="visible", timeout=5_000)
    except PlaywrightError as exc:
        pytest.fail(f"{das2_name} is not present in Available Servers as expected: {exc}")

    # 6. Click `Save Changes`.
    try:
        await page.click(save_changes_button_selector)
        # Wait for any save confirmation or page reload.
        # Adjust selector/message to match actual UI.
        await page.wait_for_load_state("networkidle")

        # Example: wait for a generic success message if available
        # success_message = page.locator("text=Changes saved successfully")
        # await success_message.wait_for(timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to save Device Attribute Server configuration: {exc}")

    # 7. Verify that after saving, Selected Servers shows only `das1`.
    try:
        selected_servers_list = page.locator(selected_servers_list_selector)
        await selected_servers_list.wait_for(state="visible", timeout=10_000)

        selected_options = selected_servers_list.locator("option")
        selected_count = await selected_options.count()
        selected_values = [
            await selected_options.nth(i).inner_text()
            for i in range(selected_count)
        ]

        assert selected_count == 1, (
            f"Expected exactly one selected server, found {selected_count}: {selected_values}"
        )
        assert any(das1_name in value for value in selected_values), (
            f"Expected '{das1_name}' in Selected Servers, got: {selected_values}"
        )

        # Verify polling interval persisted as 60
        polling_interval_input = page.locator(polling_interval_input_selector)
        polling_value = await polling_interval_input.input_value()
        assert polling_value == desired_polling_interval, (
            f"Polling interval did not persist. Expected {desired_polling_interval}, got {polling_value}"
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed to validate saved Device Attribute Server configuration: {exc}")

    # 8. After > 60 minutes or by forcing poll (if supported), check Profiler logs
    #    for successful polling of `das1` and absence of polling to `das2`.
    #
    # NOTE: In a real environment, waiting 60 minutes is impractical for a test.
    #       If the system supports a 'Force Poll' action, we use that; otherwise,
    #       this part should be adapted to the environment (e.g., mocked logs or
    #       shorter polling interval in a test configuration).

    # Attempt to force polling if a control is available.
    try:
        force_poll_button = page.locator(force_poll_button_selector)
        if await force_poll_button.count() > 0:
            await force_poll_button.click()
        else:
            # Fallback: wait a shorter time and assume polling happens frequently in test env.
            # Adjust this if you have a known shorter interval for tests.
            await asyncio.sleep(10)
    except PlaywrightError as exc:
        pytest.fail(f"Failed while attempting to trigger or wait for polling: {exc}")

    # Navigate to Profiler logs
    try:
        await page.click(profiler_menu_selector)
        await page.wait_for_load_state("networkidle")
        await page.click(logs_menu_selector)
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Profiler logs: {exc}")

    # Read logs and assert polling behavior
    try:
        # If logs are inside an iframe, switch to it
        if await page.locator(logs_frame_selector).count() > 0:
            logs_frame = await page.frame_locator(logs_frame_selector).frame()
        else:
            logs_frame = page

        logs_container = logs_frame.locator(logs_container_selector)
        await logs_container.wait_for(state="visible", timeout=20_000)
        logs_text = await logs_container.inner_text()

        # Basic assertions on log content. Update patterns to match real log format.
        das1_polled_pattern = re.compile(rf"\b{re.escape(das1_name)}\b.*poll", re.IGNORECASE | re.DOTALL)
        das2_polled_pattern = re.compile(rf"\b{re.escape(das2_name)}\b.*poll", re.IGNORECASE | re.DOTALL)

        assert das1_polled_pattern.search(logs_text), (
            f"Expected logs to show polling of '{das1_name}', but no matching entry was found."
        )
        assert not das2_polled_pattern.search(logs_text), (
            f"Logs show unexpected polling of '{das2_name}' while it should remain unselected."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed to read or validate Profiler logs: {exc}")