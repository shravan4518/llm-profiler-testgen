import asyncio
import logging
from typing import List

import pytest
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_configure_device_attribute_server_polling_interval_valid(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_005: Configure Device Attribute Server polling interval with valid value

    Description:
        Validate that a valid polling interval (720 minutes) for the Device
        Attribute Server can be set, saved, and persists after page refresh.

    Preconditions:
        - Admin is logged in (handled by authenticated_page fixture).
        - At least one Device Attribute Server (controller) configured as
          HTTP Attribute Server and reachable.

    Steps:
        1. Navigate to Device Attribute Server Configuration section.
        2. Set polling interval to 720 minutes.
        3. Select "Controller-01 (10.1.1.100)" in Available Servers.
        4. Move it to Selected Servers using the ">>" button.
        5. Click "Save Changes".
        6. Verify success message.
        7. Refresh page and verify interval and selected server are preserved.

    Expected Results:
        - Polling interval and server list changes save successfully.
        - After refresh, polling interval is 720 and "Controller-01" appears
          under Selected Servers.
    """
    page: Page = authenticated_page
    polling_interval_value = "720"
    controller_display_name = "Controller-01 (10.1.1.100)"
    controller_short_name = "Controller-01"

    # Helper: robust click with logging
    async def safe_click(selector: str, description: str, timeout: int = 10000) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            await page.click(selector)
            logger.info("Clicked %s (%s)", description, selector)
        except (TimeoutError, PlaywrightError) as exc:
            logger.error("Failed to click %s (%s): %s", description, selector, exc)
            pytest.fail(f"Unable to click {description}: {exc}")

    # Helper: get text content safely
    async def safe_text(selector: str, description: str, timeout: int = 10000) -> str:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=timeout)
            text = await page.inner_text(selector)
            logger.info("Read text from %s (%s): %s", description, selector, text)
            return text.strip()
        except (TimeoutError, PlaywrightError) as exc:
            logger.error("Failed to read text from %s (%s): %s", description, selector, exc)
            pytest.fail(f"Unable to read text from {description}: {exc}")

    # Helper: get all option texts from a <select>
    async def get_select_option_texts(selector: str, description: str) -> List[str]:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            option_elements = await page.query_selector_all(f"{selector} option")
            texts: List[str] = []
            for option in option_elements:
                text = (await option.inner_text()).strip()
                texts.append(text)
            logger.info("Options in %s (%s): %s", description, selector, texts)
            return texts
        except (TimeoutError, PlaywrightError) as exc:
            logger.error(
                "Failed to get options from %s (%s): %s", description, selector, exc
            )
            pytest.fail(f"Unable to get options from {description}: {exc}")

    # STEP 1: Navigate to `Profiler > Profiler Configuration > Device Attribute Server`
    # NOTE: Exact selectors may need adjustment for the real UI.
    # Example assumes a left navigation menu with text-based links.

    try:
        # Navigate to Profiler section
        await safe_click("text=Profiler", "Profiler top-level menu")

        # Navigate to Profiler Configuration
        await safe_click("text=Profiler Configuration", "Profiler Configuration submenu")

        # Navigate to Device Attribute Server Configuration
        await safe_click(
            "text=Device Attribute Server Configuration",
            "Device Attribute Server Configuration section",
        )

        # Wait for Device Attribute Server configuration panel to be visible
        await page.wait_for_selector(
            "text=Device Attribute Server Configuration",
            state="visible",
            timeout=15000,
        )
    except AssertionError:
        # pytest.fail already called in helpers
        raise

    # STEP 2: Set the polling interval to `720` minutes.
    # Assume there is an input with a label or name for polling interval.
    # Example selectors (adjust to real DOM):
    polling_interval_input_selector_candidates = [
        "input[name='pollingInterval']",
        "input#pollingInterval",
        "input[data-testid='polling-interval']",
        "input[aria-label='Polling Interval (minutes)']",
    ]

    polling_interval_input_selector = None
    for selector in polling_interval_input_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=3000)
            polling_interval_input_selector = selector
            break
        except TimeoutError:
            continue

    if polling_interval_input_selector is None:
        pytest.fail("Polling interval input field not found with known selectors.")

    try:
        await page.fill(polling_interval_input_selector, "")
        await page.fill(polling_interval_input_selector, polling_interval_value)
        logger.info(
            "Set polling interval to %s using selector %s",
            polling_interval_value,
            polling_interval_input_selector,
        )
    except PlaywrightError as exc:
        logger.error("Failed to set polling interval: %s", exc)
        pytest.fail(f"Unable to set polling interval: {exc}")

    # Assert that the input value is correctly set
    try:
        current_value = await page.get_attribute(
            polling_interval_input_selector, "value"
        )
        assert current_value == polling_interval_value, (
            f"Expected polling interval value '{polling_interval_value}', "
            f"but found '{current_value}'"
        )
    except PlaywrightError as exc:
        logger.error("Failed to read polling interval value: %s", exc)
        pytest.fail(f"Unable to verify polling interval value: {exc}")

    # STEP 3: In “Available Servers” list, select `Controller-01 (10.1.1.100)`.
    # Assume two <select> elements: available and selected servers.
    available_servers_selector_candidates = [
        "select[name='availableServers']",
        "select#availableServers",
        "select[data-testid='available-servers']",
    ]
    selected_servers_selector_candidates = [
        "select[name='selectedServers']",
        "select#selectedServers",
        "select[data-testid='selected-servers']",
    ]

    available_servers_selector = None
    for selector in available_servers_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=3000)
            available_servers_selector = selector
            break
        except TimeoutError:
            continue

    if available_servers_selector is None:
        pytest.fail("Available Servers list not found with known selectors.")

    selected_servers_selector = None
    for selector in selected_servers_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=3000)
            selected_servers_selector = selector
            break
        except TimeoutError:
            continue

    if selected_servers_selector is None:
        pytest.fail("Selected Servers list not found with known selectors.")

    # Verify that the controller is present in Available Servers
    available_servers = await get_select_option_texts(
        available_servers_selector, "Available Servers"
    )
    assert any(
        controller_display_name in option or controller_short_name in option
        for option in available_servers
    ), (
        f"Expected controller '{controller_display_name}' to be present in "
        f"Available Servers, but found: {available_servers}"
    )

    # Select the controller in Available Servers
    try:
        await page.select_option(
            available_servers_selector,
            label=controller_display_name,
        )
    except PlaywrightError:
        # Fallback: try selecting by partial label (short name)
        try:
            await page.select_option(
                available_servers_selector,
                label=controller_short_name,
            )
        except PlaywrightError as exc:
            logger.error("Failed to select controller in Available Servers: %s", exc)
            pytest.fail(
                f"Unable to select controller '{controller_display_name}' "
                f"in Available Servers: {exc}"
            )

    # STEP 4: Add it to “Selected Servers” using the `>>` button.
    # Assume a button between the lists with text ">>" or an aria-label.
    add_to_selected_button_selector_candidates = [
        "button:has-text('>>')",
        "button[aria-label='Add to Selected Servers']",
        "button[data-testid='move-to-selected']",
    ]

    add_to_selected_button_selector = None
    for selector in add_to_selected_button_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=3000)
            add_to_selected_button_selector = selector
            break
        except TimeoutError:
            continue

    if add_to_selected_button_selector is None:
        pytest.fail("Button to move server to Selected Servers not found.")

    await safe_click(
        add_to_selected_button_selector,
        "Add to Selected Servers (>> button)",
    )

    # Verify controller appears in Selected Servers list
    selected_servers = await get_select_option_texts(
        selected_servers_selector, "Selected Servers"
    )
    assert any(
        controller_display_name in option or controller_short_name in option
        for option in selected_servers
    ), (
        f"Expected controller '{controller_display_name}' to be present in "
        f"Selected Servers after moving, but found: {selected_servers}"
    )

    # STEP 5: Click `Save Changes`.
    save_button_selector_candidates = [
        "button:has-text('Save Changes')",
        "input[type='submit'][value='Save Changes']",
        "button[data-testid='save-device-attribute-server-config']",
    ]

    save_button_selector = None
    for selector in save_button_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=5000)
            save_button_selector = selector
            break
        except TimeoutError:
            continue

    if save_button_selector is None:
        pytest.fail("Save Changes button not found with known selectors.")

    await safe_click(save_button_selector, "Save Changes")

    # STEP 6: Verify success message.
    # Assume a generic success banner; adjust selectors to real app.
    success_message_selector_candidates = [
        ".alert-success",
        "div[role='alert'].success",
        "text=Changes saved successfully",
        "text=Configuration updated successfully",
    ]

    success_message_found = False
    success_message_text = ""
    for selector in success_message_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            success_message_text = await safe_text(selector, "Success Message")
            success_message_found = True
            break
        except AssertionError:
            # safe_text already failed the test
            raise
        except TimeoutError:
            continue

    if not success_message_found:
        pytest.fail("Success message not displayed after saving changes.")

    # Basic assertion that message is non-empty and indicates success
    assert any(
        keyword in success_message_text.lower()
        for keyword in ["success", "saved", "updated", "applied"]
    ), (
        "Success message does not clearly indicate success: "
        f"'{success_message_text}'"
    )

    # STEP 7: Refresh the page and confirm the interval and selected server are preserved.
    try:
        await page.reload(wait_until="networkidle")
    except PlaywrightError as exc:
        logger.error("Failed to reload page: %s", exc)
        pytest.fail(f"Unable to reload page for verification: {exc}")

    # Wait briefly to ensure UI is fully re-initialized
    await asyncio.sleep(1)

    # Re-locate polling interval input (in case DOM changed)
    polling_interval_input_selector_refreshed = None
    for selector in polling_interval_input_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=5000)
            polling_interval_input_selector_refreshed = selector
            break
        except TimeoutError:
            continue

    if polling_interval_input_selector_refreshed is None:
        pytest.fail(
            "Polling interval input field not found after page refresh with known selectors."
        )

    try:
        current_value_after_refresh = await page.get_attribute(
            polling_interval_input_selector_refreshed, "value"
        )
    except PlaywrightError as exc:
        logger.error("Failed to read polling interval after refresh: %s", exc)
        pytest.fail(f"Unable to verify polling interval after refresh: {exc}")

    assert current_value_after_refresh == polling_interval_value, (
        "Polling interval value did not persist after refresh. "
        f"Expected '{polling_interval_value}', found '{current_value_after_refresh}'."
    )

    # Re-locate Selected Servers list
    selected_servers_selector_refreshed = None
    for selector in selected_servers_selector_candidates:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=5000)
            selected_servers_selector_refreshed = selector
            break
        except TimeoutError:
            continue

    if selected_servers_selector_refreshed is None:
        pytest.fail(
            "Selected Servers list not found after page refresh with known selectors."
        )

    selected_servers_after_refresh = await get_select_option_texts(
        selected_servers_selector_refreshed, "Selected Servers after refresh"
    )
    assert any(
        controller_display_name in option or controller_short_name in option
        for option in selected_servers_after_refresh
    ), (
        "Selected Servers list did not persist after refresh. "
        f"Expected '{controller_display_name}' to be present, "
        f"but found: {selected_servers_after_refresh}"
    )