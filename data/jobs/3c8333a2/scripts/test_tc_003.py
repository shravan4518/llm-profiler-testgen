import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error, TimeoutError, expect

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_delete_profiler_configuration_from_ui(authenticated_page: Page, browser):
    """
    TC_003: Delete profiler configuration from UI

    Validates that the 'Delete Profiler' action from basic configuration:
    - Shows a confirmation prompt
    - Removes profiler configuration LP-01 upon confirmation
    - Redirects the user appropriately with a status message
    - Leaves the system with no active profiler configured

    Prerequisites:
    - Profiler is configured and active (e.g., LP-01 exists)
    - Admin user 'TPSAdmin' is logged in via authenticated_page fixture
    """
    page: Page = authenticated_page

    # Helper: wait for and accept confirmation dialog
    async def accept_confirmation_dialog(expected_text_substring: Optional[str] = None) -> None:
        """
        Waits for a confirmation dialog and accepts it.

        :param expected_text_substring: Optional substring to verify in dialog message.
        """
        dialog_future = asyncio.create_task(page.wait_for_event("dialog", timeout=5000))

        try:
            dialog = await dialog_future
        except TimeoutError as exc:
            logger.error("No confirmation dialog appeared within timeout.")
            raise AssertionError("Expected a confirmation dialog, but none appeared.") from exc

        try:
            dialog_message = dialog.message
            logger.info("Confirmation dialog appeared with message: %s", dialog_message)

            if expected_text_substring:
                assert expected_text_substring in dialog_message, (
                    f"Dialog message did not contain expected text. "
                    f"Expected to find '{expected_text_substring}', got '{dialog_message}'"
                )

            await dialog.accept()
        except Error as exc:
            logger.exception("Failed to accept confirmation dialog.")
            raise AssertionError("Failed to accept confirmation dialog.") from exc

    # -------------------------------------------------------------------------
    # STEP 1: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # -------------------------------------------------------------------------
    try:
        # Example navigation using menu items; adjust selectors to your actual UI.
        # Click "Profiler" in main navigation
        await page.get_by_role("link", name="Profiler").click()

        # Click "Profiler Configuration"
        await page.get_by_role("link", name="Profiler Configuration").click()

        # Click "Settings"
        await page.get_by_role("link", name="Settings").click()

        # Click "Basic Configuration"
        await page.get_by_role("link", name="Basic Configuration").click()

        # Verify we are on the Basic Configuration page and LP-01 is visible
        await expect(page.get_by_role("heading", name="Basic Configuration")).to_be_visible()
        # Assuming LP-01 appears as a label or text on the page
        await expect(page.get_by_text("LP-01")).to_be_visible()
    except (Error, AssertionError) as exc:
        logger.exception("Failed to navigate to Basic Configuration or verify LP-01 presence.")
        raise

    # -------------------------------------------------------------------------
    # STEP 2: Click the "Delete Profiler" button
    # -------------------------------------------------------------------------
    try:
        # Adjust selector according to actual UI (text, role, id, etc.)
        delete_button = page.get_by_role("button", name="Delete Profiler")
        await expect(delete_button).to_be_enabled()
        await delete_button.click()
    except (Error, AssertionError) as exc:
        logger.exception("Failed to click 'Delete Profiler' button.")
        raise

    # -------------------------------------------------------------------------
    # STEP 3: In the confirmation dialog, select Yes/OK to confirm deletion
    # -------------------------------------------------------------------------
    await accept_confirmation_dialog(expected_text_substring="delete")

    # -------------------------------------------------------------------------
    # STEP 4: Observe system behavior and redirect
    # -------------------------------------------------------------------------
    # Expect redirect to an overview or similar page and a success/info message
    try:
        # Wait for potential navigation after deletion
        await page.wait_for_load_state("networkidle", timeout=15000)
    except TimeoutError:
        # Not necessarily a failure: some apps update in-place without full navigation
        logger.info("No full page navigation detected after deletion; checking current page state.")

    # Example: expect a general notification message
    # Adjust to the actual selector for success/notification/toast message
    try:
        # This is intentionally flexible; adapt to your app's DOM
        possible_message_locators = [
            page.get_by_role("alert"),
            page.locator(".alert-success"),
            page.get_by_text("deleted").first,
            page.get_by_text("no profiler configured", exact=False).first,
        ]

        message_found = False
        for locator in possible_message_locators:
            try:
                await locator.wait_for(timeout=5000)
                if await locator.is_visible():
                    message_text = await locator.inner_text()
                    logger.info("Status message after deletion: %s", message_text)
                    # Basic assertion that message indicates deletion or missing configuration
                    assert any(
                        phrase.lower() in message_text.lower()
                        for phrase in ["deleted", "no profiler configured", "needs configuration"]
                    ), (
                        "Status message does not clearly indicate deletion or missing configuration. "
                        f"Message: {message_text}"
                    )
                    message_found = True
                    break
            except TimeoutError:
                continue

        assert message_found, (
            "Expected a status/notification message after deletion, but none was found."
        )
    except AssertionError:
        logger.exception("Status message after deletion did not meet expectations.")
        raise

    # -------------------------------------------------------------------------
    # STEP 5: Try navigating back to Profiler > Profiler Configuration
    # -------------------------------------------------------------------------
    try:
        await page.get_by_role("link", name="Profiler").click()
        await page.get_by_role("link", name="Profiler Configuration").click()
        await page.wait_for_load_state("networkidle", timeout=10000)
    except (Error, TimeoutError) as exc:
        logger.exception("Failed to navigate back to Profiler Configuration after deletion.")
        raise

    # -------------------------------------------------------------------------
    # ASSERTIONS: No profiler configuration should be present
    # -------------------------------------------------------------------------
    # The UI should show no active profiler and/or prompt to create/configure a new profiler.
    try:
        # Example 1: LP-01 should no longer be visible
        lp01_locator = page.get_by_text("LP-01")
        assert await lp01_locator.count() == 0 or not await lp01_locator.first.is_visible(), (
            "Profiler configuration 'LP-01' still appears in the UI after deletion."
        )

        # Example 2: Look for text or control indicating no profiler is configured
        no_profiler_text_candidates = [
            "No profiler configured",
            "No profiler is configured",
            "Create Profiler",
            "Configure Profiler",
        ]

        no_profiler_indicator_found = False
        for text_candidate in no_profiler_text_candidates:
            locator = page.get_by_text(text_candidate, exact=False)
            if await locator.count() > 0 and await locator.first.is_visible():
                no_profiler_indicator_found = True
                break

        assert no_profiler_indicator_found, (
            "UI does not indicate that no profiler is configured or prompt to create/configure one."
        )
    except (Error, AssertionError) as exc:
        logger.exception("Post-deletion UI state did not match expectations.")
        raise