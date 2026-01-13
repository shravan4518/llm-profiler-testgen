import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_configure_advanced_profiler_settings_local_profiler(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_004: Configure advanced profiler settings for local profiler (positive)

    Validates that the advanced configuration for the local profiler can be
    accessed, updated, and persists after a page reload.

    Prerequisites:
        - Basic profiler configuration already saved.
        - Admin logged in (handled by authenticated_page fixture).

    Steps:
        1. Use authenticated_page as TPSAdmin.
        2. Navigate to Profiler > Profiler Configuration > Advance.
        3. Locate WMI configuration section.
        4. Enable WMI profiling.
        5. Enable SNMP collection (if present).
        6. Enable CDP and LLDP (if present).
        7. Click Save Changes.
        8. Validate success message and absence of error.
        9. Refresh and verify settings persist.

    Expected:
        - Advanced settings are accepted without validation errors.
        - Success confirmation is displayed.
        - Settings persist after page reload.
    """
    page: Page = authenticated_page

    # Helper to safely click a checkbox if it exists
    async def ensure_checkbox_checked(
        locator_str: str,
        description: str,
    ) -> Optional[bool]:
        """
        Ensure a checkbox is checked if it is present.

        Returns:
            True if checkbox was found and set to checked,
            False if already checked,
            None if the checkbox was not found.
        """
        locator = page.locator(locator_str)
        try:
            if not await locator.first().is_visible():
                logger.info("Checkbox '%s' not visible; skipping.", description)
                return None
        except PlaywrightError:
            logger.info("Checkbox '%s' not found; skipping.", description)
            return None

        try:
            is_checked = await locator.first().is_checked()
            if not is_checked:
                await locator.first().check()
                logger.info("Checkbox '%s' checked.", description)
                return True
            logger.info("Checkbox '%s' already checked.", description)
            return False
        except PlaywrightError as exc:
            logger.error(
                "Failed to interact with checkbox '%s': %s", description, exc
            )
            pytest.fail(f"Unable to set checkbox '{description}': {exc}")

    # Helper to assert checkbox remains checked after reload
    async def assert_checkbox_checked(
        locator_str: str,
        description: str,
    ) -> None:
        locator = page.locator(locator_str)
        try:
            if not await locator.first().is_visible():
                logger.info(
                    "Checkbox '%s' not visible after reload; assuming optional.",
                    description,
                )
                return
            assert await locator.first().is_checked(), (
                f"Checkbox '{description}' is not checked after reload."
            )
        except PlaywrightError as exc:
            logger.error(
                "Failed to assert checkbox '%s' after reload: %s",
                description,
                exc,
            )
            pytest.fail(
                f"Unable to verify checkbox '{description}' after reload: {exc}"
            )

    # ----------------------------------------------------------------------
    # Step 1: Use authenticated_page as TPSAdmin (fixture already logged in)
    # ----------------------------------------------------------------------
    # Basic sanity check: ensure we are on an authenticated page
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightError as exc:
        pytest.fail(f"Page did not reach network idle state after login: {exc}")

    # ----------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Advance
    # ----------------------------------------------------------------------
    # NOTE: Selectors below are examples; adjust them to match the actual UI.
    try:
        # Navigate via top menu: "Profiler"
        await page.get_by_role("link", name="Profiler").click()
        await page.wait_for_load_state("networkidle")

        # Submenu: "Profiler Configuration"
        await page.get_by_role("link", name="Profiler Configuration").click()
        await page.wait_for_load_state("networkidle")

        # Tab or link: "Advance" (Advanced configuration)
        # Handle possible naming variations: "Advance" / "Advanced"
        advance_tab = page.get_by_role("link", name="Advance")
        advanced_tab = page.get_by_role("link", name="Advanced")

        if await advance_tab.is_visible():
            await advance_tab.click()
        elif await advanced_tab.is_visible():
            await advanced_tab.click()
        else:
            pytest.fail(
                "Could not find 'Advance' or 'Advanced' configuration tab."
            )

        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Navigation to advanced profiler configuration failed: {exc}")

    # ----------------------------------------------------------------------
    # Step 3: Locate WMI configuration section
    # ----------------------------------------------------------------------
    # This step is primarily a visibility/assertion step.
    # Adjust selectors to match the real application.
    try:
        wmi_section = page.get_by_role("group", name="WMI Configuration")
        # Fallback to a heading if group role is not available
        if not await wmi_section.is_visible():
            wmi_section = page.get_by_role("heading", name="WMI Configuration")
        assert await wmi_section.is_visible(), (
            "WMI configuration section is not visible on Advanced page."
        )
    except PlaywrightError:
        # If roles are not properly defined, fall back to text search
        wmi_section = page.get_by_text("WMI", exact=False)
        if not await wmi_section.is_visible():
            pytest.fail(
                "Unable to locate WMI configuration section on Advanced page."
            )

    # ----------------------------------------------------------------------
    # Step 4: Check “Enable WMI profiling”
    # ----------------------------------------------------------------------
    # Example selector assumptions:
    # - Checkbox input with label text "Enable WMI profiling"
    # You may need to adjust to match actual DOM:
    #   label:has-text("Enable WMI profiling") >> input[type="checkbox"]
    await ensure_checkbox_checked(
        locator_str='label:has-text("Enable WMI profiling") >> input[type="checkbox"]',
        description="Enable WMI profiling",
    )

    # ----------------------------------------------------------------------
    # Step 5: Check “Enable SNMP collection” (if present)
    # ----------------------------------------------------------------------
    await ensure_checkbox_checked(
        locator_str='label:has-text("Enable SNMP collection") >> input[type="checkbox"]',
        description="Enable SNMP collection",
    )

    # ----------------------------------------------------------------------
    # Step 6: Check “Enable CDP” and “Enable LLDP” (if present)
    # ----------------------------------------------------------------------
    await ensure_checkbox_checked(
        locator_str='label:has-text("Enable CDP") >> input[type="checkbox"]',
        description="Enable CDP",
    )

    await ensure_checkbox_checked(
        locator_str='label:has-text("Enable LLDP") >> input[type="checkbox"]',
        description="Enable LLDP",
    )

    # ----------------------------------------------------------------------
    # Step 7: Click `Save Changes`
    # ----------------------------------------------------------------------
    # Adjust selector to actual button text or id as needed.
    try:
        save_button = page.get_by_role("button", name="Save Changes")
        assert await save_button.is_visible(), (
            "'Save Changes' button is not visible on Advanced configuration page."
        )
        await save_button.click()
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click 'Save Changes' button: {exc}")

    # ----------------------------------------------------------------------
    # Step 8: Validate success message and absence of error
    # ----------------------------------------------------------------------
    try:
        # Example success message locator
        # Adjust text to match actual success message.
        success_message = page.locator(
            ".alert-success, .msg-success, text=Settings saved successfully"
        )

        await success_message.wait_for(timeout=15000)
        assert await success_message.is_visible(), (
            "Success message not visible after saving advanced configuration."
        )

        # Assert no visible error messages
        error_message = page.locator(
            ".alert-error, .msg-error, .validation-error, text=Error"
        )
        assert not await error_message.is_visible(), (
            "An error message is visible after saving advanced configuration."
        )
    except PlaywrightError as exc:
        pytest.fail(
            f"Unable to verify success or error messages after saving: {exc}"
        )

    # ----------------------------------------------------------------------
    # Step 9: Refresh the page and verify settings persist
    # ----------------------------------------------------------------------
    try:
        await page.reload(wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reload Advanced configuration page: {exc}")

    # Re-assert that we are still on the Advanced configuration page
    # (lightweight check, adjust as needed)
    try:
        assert await page.get_by_text("Advanced Profiler Configuration", exact=False).is_visible() or \
               await page.get_by_text("Advanced Configuration", exact=False).is_visible(), \
            "Not on Advanced configuration page after reload."
    except PlaywrightError:
        # If headings are different, we skip this soft check
        logger.warning(
            "Could not verify advanced configuration heading after reload; "
            "continuing with checkbox validations."
        )

    # Verify that all relevant checkboxes remain checked
    await assert_checkbox_checked(
        locator_str='label:has-text("Enable WMI profiling") >> input[type="checkbox"]',
        description="Enable WMI profiling",
    )

    await assert_checkbox_checked(
        locator_str='label:has-text("Enable SNMP collection") >> input[type="checkbox"]',
        description="Enable SNMP collection",
    )

    await assert_checkbox_checked(
        locator_str='label:has-text("Enable CDP") >> input[type="checkbox"]',
        description="Enable CDP",
    )

    await assert_checkbox_checked(
        locator_str='label:has-text("Enable LLDP") >> input[type="checkbox"]',
        description="Enable LLDP",
    )

    # If we reached this point, all assertions have passed and the test
    # confirms that the advanced settings were saved and persisted.
    # Postconditions:
    # - Local profiler operates with newly enabled advanced data collectors.
    # (Behavioral verification is out of scope for this UI test.)
    await asyncio.sleep(0)  # keep function async-friendly even if simplified