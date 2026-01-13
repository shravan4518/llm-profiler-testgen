import asyncio
import pytest
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError


@pytest.mark.asyncio
async def test_delete_local_profiler_configuration_successfully(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_003: Delete local Profiler configuration successfully

    Validates that clicking "Delete Profiler" deletes the local Profiler configuration
    and removes related settings, resetting the UI to the initial state.

    Prerequisites:
        - Local Profiler configured with non-default settings (e.g., LocalProfiler01).
        - No active dependencies that would block deletion.

    Steps:
        1. Use authenticated_page (logged in as ppsadmin).
        2. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
        3. Verify LocalProfiler01 is currently configured.
        4. Click "Delete Profiler".
        5. Confirm the delete action on the confirmation dialog.
        6. Observe the result page/state.
        7. Reload the Profiler Configuration page.

    Expected:
        - System prompts for confirmation before deletion.
        - After confirmation, the basic configuration page is reset to initial state.
        - Status shows “No Profiler configured” (or equivalent).
        - No errors indicating stale configuration.
    """
    page: Page = authenticated_page

    # Locators (use realistic, robust selectors where possible)
    profiler_menu_locator = page.get_by_role(
        "link", name="Profiler", exact=True
    )
    profiler_config_menu_locator = page.get_by_role(
        "link", name="Profiler Configuration", exact=True
    )
    settings_tab_locator = page.get_by_role(
        "tab", name="Settings", exact=True
    )
    basic_config_tab_locator = page.get_by_role(
        "tab", name="Basic Configuration", exact=True
    )

    # These may need adjustment to match the real DOM
    current_profiler_name_locator = page.locator(
        "text=LocalProfiler01"
    )
    delete_profiler_button_locator = page.get_by_role(
        "button", name="Delete Profiler"
    )
    confirmation_dialog_locator = page.get_by_role(
        "dialog"
    )
    confirm_delete_button_locator = page.get_by_role(
        "button", name="OK"
    ).or_(page.get_by_role("button", name="Yes"))

    # Expected post-deletion indicators
    no_profiler_configured_text_locator = page.get_by_text(
        "No Profiler configured"
    ).or_(page.get_by_text("No profiler configured"))
    error_message_locator = page.locator(
        ".error, .error-message, .alert-error"
    )

    # Step 1: authenticated_page fixture already logged in as ppsadmin
    # Validate we are on the admin UI or can reach it
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except TimeoutError:
        pytest.fail("Admin UI did not reach network idle state after login")

    # Step 2: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    try:
        # Open Profiler main menu
        await profiler_menu_locator.click(timeout=10000)

        # Navigate to Profiler Configuration
        await profiler_config_menu_locator.click(timeout=10000)

        # Ensure Profiler Configuration page is loaded
        await page.wait_for_load_state("networkidle", timeout=15000)

        # Go to Settings tab
        await settings_tab_locator.click(timeout=10000)

        # Go to Basic Configuration tab
        await basic_config_tab_locator.click(timeout=10000)

        await page.wait_for_load_state("networkidle", timeout=15000)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Navigation to Profiler Basic Configuration failed: {exc}")

    # Step 3: Verify LocalProfiler01 is currently configured
    try:
        await expect_visible_with_timeout(
            current_profiler_name_locator,
            timeout=10000,
            description="LocalProfiler01 should be configured before deletion",
        )
    except AssertionError as exc:
        pytest.fail(str(exc))

    # Step 4: Click "Delete Profiler"
    try:
        await delete_profiler_button_locator.click(timeout=10000)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to click 'Delete Profiler' button: {exc}")

    # Step 5: Confirm the delete action on any confirmation dialog
    try:
        # Assert that a confirmation dialog appears
        await confirmation_dialog_locator.wait_for(timeout=10000)
    except TimeoutError:
        pytest.fail("Expected confirmation dialog did not appear after clicking 'Delete Profiler'")

    # The dialog is present; now click confirm (OK/Yes)
    try:
        await confirm_delete_button_locator.click(timeout=10000)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to confirm deletion in confirmation dialog: {exc}")

    # Step 6: Observe the result page/state
    # Wait for possible reload or state change after deletion
    try:
        await page.wait_for_load_state("networkidle", timeout=20000)
    except TimeoutError:
        # Not necessarily fatal, but we will continue with assertions
        pass

    # Ensure no immediate error messages are displayed
    try:
        await assert_no_error_messages(
            error_message_locator,
            description="No error messages should be visible after deleting Profiler",
        )
    except AssertionError as exc:
        pytest.fail(str(exc))

    # Step 7: Reload the Profiler Configuration page
    try:
        await page.reload(wait_until="networkidle")
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to reload Profiler Configuration page: {exc}")

    # Re-ensure we are on the correct tabs after reload
    try:
        await settings_tab_locator.click(timeout=10000)
        await basic_config_tab_locator.click(timeout=10000)
        await page.wait_for_load_state("networkidle", timeout=15000)
    except (PlaywrightError, TimeoutError) as exc:
        pytest.fail(f"Failed to re-open Basic Configuration tab after reload: {exc}")

    # ===== Assertions for expected results =====

    # 1) System prompts for confirmation before deletion
    # Already asserted by waiting for confirmation_dialog_locator above.

    # 2) After confirmation, basic configuration page is reset to initial state
    #    and 3) Status shows “No Profiler configured” or equivalent.
    try:
        await expect_visible_with_timeout(
            no_profiler_configured_text_locator,
            timeout=15000,
            description="Status text indicating no Profiler is configured should be visible",
        )
    except AssertionError as exc:
        pytest.fail(str(exc))

    # Ensure the old profiler name is no longer visible
    try:
        await expect_not_visible_with_timeout(
            current_profiler_name_locator,
            timeout=5000,
            description="LocalProfiler01 should not be visible after deletion",
        )
    except AssertionError as exc:
        pytest.fail(str(exc))

    # 4) No errors indicating stale configuration
    try:
        await assert_no_error_messages(
            error_message_locator,
            description="No stale configuration errors should be visible after reload",
        )
    except AssertionError as exc:
        pytest.fail(str(exc))

    # Postconditions:
    # - Local Profiler configuration is removed (covered by absence of LocalProfiler01
    #   and presence of "No Profiler configured").
    # - Any dependent configuration references are either removed or clearly marked invalid.
    #   This can be partially validated by ensuring no error/alert is shown.
    #   If specific UI elements exist for dependencies, they can be asserted here.


async def expect_visible_with_timeout(locator, timeout: int, description: str) -> None:
    """
    Helper: assert that a locator becomes visible within timeout.

    Raises:
        AssertionError: if locator does not become visible.
    """
    try:
        await locator.wait_for(state="visible", timeout=timeout)
    except TimeoutError:
        raise AssertionError(f"Timed out waiting for visible element: {description}")


async def expect_not_visible_with_timeout(locator, timeout: int, description: str) -> None:
    """
    Helper: assert that a locator becomes hidden or detached within timeout.

    Raises:
        AssertionError: if locator remains visible.
    """
    try:
        await locator.wait_for(state="hidden", timeout=timeout)
    except TimeoutError:
        # If wait_for('hidden') times out, check if it is still visible to give a clearer error
        try:
            is_visible = await locator.is_visible()
        except PlaywrightError:
            is_visible = False
        if is_visible:
            raise AssertionError(f"Element remained visible: {description}")


async def assert_no_error_messages(locator, description: str) -> None:
    """
    Helper: assert that no error messages are visible for the given locator.

    Raises:
        AssertionError: if any error message is visible.
    """
    try:
        count = await locator.count()
    except PlaywrightError:
        # If locator query fails, treat as no visible errors (conservative)
        count = 0

    if count == 0:
        return

    # If there are elements, verify none of them are actually visible
    visible_any = False
    visible_texts = []
    for index in range(count):
        item = locator.nth(index)
        try:
            if await item.is_visible():
                visible_any = True
                text = (await item.text_content()) or ""
                visible_texts.append(text.strip())
        except PlaywrightError:
            continue

    if visible_any:
        joined_texts = "; ".join(t for t in visible_texts if t)
        raise AssertionError(
            f"{description}. Visible error messages found: {joined_texts}"
        )