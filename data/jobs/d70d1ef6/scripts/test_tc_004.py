import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_004_configure_advanced_profiler_wmi(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_004: Configure advanced Profiler settings including WMI profiling.

    Validates that an admin can access and configure advanced Profiler settings,
    including WMI profiling, via:
    Profiler > Profiler Configuration > Advance.

    Preconditions:
        - Basic Profiler configured and saved (TC_001).
        - WMI-accessible Windows endpoint `win-host01.domain.local` reachable.

    Expected:
        - Advanced configuration page loads correctly.
        - WMI profiling can be enabled and settings saved without validation errors.
        - Success message is displayed.
        - Status/logs indicate successful WMI polling to `win-host01.domain.local`
          at the defined interval.
    """
    page = authenticated_page

    # Test data
    wmi_host = "win-host01.domain.local"
    wmi_username = "domain\\profilerwmi"
    wmi_password = "WmiP@ssw0rd!"
    wmi_poll_interval = "60"

    # NOTE:
    # The selectors below are placeholders and should be updated to match
    # the actual application under test (data-testid, name, id, etc.).

    # Locators for navigation
    profiler_menu_locator = page.get_by_role("link", name="Profiler")
    profiler_config_menu_locator = page.get_by_role(
        "link", name="Profiler Configuration"
    )
    advanced_tab_locator = page.get_by_role("tab", name="Advance")

    # Locators for WMI configuration section
    wmi_section_locator = page.get_by_role("region", name="WMI Configuration")
    wmi_enable_checkbox_locator = wmi_section_locator.get_by_role(
        "checkbox", name="Enable WMI Profiling"
    )
    wmi_host_input_locator = wmi_section_locator.get_by_label("WMI Host")
    wmi_username_input_locator = wmi_section_locator.get_by_label("Username")
    wmi_password_input_locator = wmi_section_locator.get_by_label("Password")
    wmi_interval_input_locator = wmi_section_locator.get_by_label(
        "Polling Interval (seconds)"
    )

    # Locators for save and success message
    save_changes_button_locator = page.get_by_role("button", name="Save Changes")
    success_message_locator = page.get_by_role(
        "status", name="Configuration saved successfully"
    )

    # Locators for logs/status verification
    logs_menu_locator = page.get_by_role("link", name="Logs")
    profiler_logs_menu_locator = page.get_by_role("link", name="Profiler")
    # Example: a table row or log entry that shows successful WMI polling
    wmi_log_entry_locator = page.get_by_text(
        f"WMI polling successful for host {wmi_host}", exact=False
    )

    # -------------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin`
    # -------------------------------------------------------------------------
    # This step is handled by the `authenticated_page` fixture from conftest.py.
    # We still validate that we are on an authenticated/admin page.

    try:
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightError as exc:
        logger.error("Page did not reach networkidle state after login: %s", exc)
        pytest.fail("Login did not complete or page failed to load after authentication")

    # Basic sanity check that we see an admin-specific element
    assert await profiler_menu_locator.is_visible(), (
        "Profiler menu not visible after login; "
        "user may not be authenticated as admin or UI changed."
    )

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Advance
    # -------------------------------------------------------------------------
    try:
        # Click Profiler menu
        await profiler_menu_locator.click()
        # Click Profiler Configuration submenu
        await profiler_config_menu_locator.click()
        # Wait for configuration page to load
        await page.wait_for_load_state("networkidle", timeout=15_000)

        # Click on Advance tab
        await advanced_tab_locator.click()
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightError as exc:
        logger.error("Failed to navigate to Advanced Profiler configuration: %s", exc)
        pytest.fail("Navigation to Profiler > Profiler Configuration > Advance failed")

    # Assert advanced configuration page is loaded
    assert await advanced_tab_locator.get_attribute("aria-selected") in (
        "true",
        "1",
    ), "Advanced tab is not selected; advanced configuration page may not be loaded"

    # -------------------------------------------------------------------------
    # Step 3: Locate the WMI Configuration section
    # -------------------------------------------------------------------------
    try:
        await wmi_section_locator.wait_for(state="visible", timeout=10_000)
    except PlaywrightError as exc:
        logger.error("WMI Configuration section not visible: %s", exc)
        pytest.fail("WMI Configuration section not found on Advanced configuration page")

    assert await wmi_section_locator.is_visible(), (
        "WMI Configuration section should be visible on Advanced configuration page"
    )

    # -------------------------------------------------------------------------
    # Step 4: Enable WMI profiling by checking the relevant checkbox/option
    # -------------------------------------------------------------------------
    try:
        if not await wmi_enable_checkbox_locator.is_checked():
            await wmi_enable_checkbox_locator.check()
    except PlaywrightError as exc:
        logger.error("Failed to enable WMI profiling checkbox: %s", exc)
        pytest.fail("Could not enable WMI profiling option")

    assert await wmi_enable_checkbox_locator.is_checked(), (
        "WMI profiling checkbox should be checked after enabling"
    )

    # -------------------------------------------------------------------------
    # Step 5: Enter WMI host
    # -------------------------------------------------------------------------
    try:
        await wmi_host_input_locator.fill(wmi_host)
    except PlaywrightError as exc:
        logger.error("Failed to fill WMI host field: %s", exc)
        pytest.fail("Could not enter WMI host value")

    # Basic assertion on field value
    assert (
        await wmi_host_input_locator.input_value()
    ) == wmi_host, "WMI host field value does not match expected"

    # -------------------------------------------------------------------------
    # Step 6: Enter username and password
    # -------------------------------------------------------------------------
    try:
        await wmi_username_input_locator.fill(wmi_username)
        await wmi_password_input_locator.fill(wmi_password)
    except PlaywrightError as exc:
        logger.error("Failed to fill WMI credentials: %s", exc)
        pytest.fail("Could not enter WMI username/password")

    assert (
        await wmi_username_input_locator.input_value()
    ) == wmi_username, "WMI username field value does not match expected"
    # For password fields, we usually cannot read the value back; we just assume fill succeeded.

    # -------------------------------------------------------------------------
    # Step 7: Set WMI polling interval
    # -------------------------------------------------------------------------
    try:
        await wmi_interval_input_locator.fill(wmi_poll_interval)
    except PlaywrightError as exc:
        logger.error("Failed to fill WMI polling interval: %s", exc)
        pytest.fail("Could not enter WMI polling interval")

    assert (
        await wmi_interval_input_locator.input_value()
    ) == wmi_poll_interval, "WMI polling interval value does not match expected"

    # -------------------------------------------------------------------------
    # Step 8: Click "Save Changes"
    # -------------------------------------------------------------------------
    try:
        await save_changes_button_locator.click()
    except PlaywrightError as exc:
        logger.error("Failed to click Save Changes button: %s", exc)
        pytest.fail("Could not trigger save operation for advanced profiler settings")

    # -------------------------------------------------------------------------
    # Step 9: Observe success/error message
    # -------------------------------------------------------------------------
    # Wait for either a success status or an error notification
    success_message: Optional[bool] = None
    try:
        await success_message_locator.wait_for(state="visible", timeout=15_000)
        success_message = True
    except PlaywrightError:
        # We did not see the exact success message; try to gather any error messages
        success_message = False

    if not success_message:
        # Try to capture any generic error feedback on the page
        error_message_locator = page.get_by_role("alert")
        error_visible = await error_message_locator.is_visible()
        error_text = await error_message_locator.inner_text() if error_visible else ""
        logger.error(
            "Expected success message not found. Error visible: %s, text: %s",
            error_visible,
            error_text,
        )
        pytest.fail(
            "Advanced Profiler WMI configuration did not report success; "
            f"error: {error_text or 'no error message visible'}"
        )

    # At this point, success message is visible
    assert await success_message_locator.is_visible(), (
        "Success message should be visible after saving advanced WMI configuration"
    )

    # -------------------------------------------------------------------------
    # Step 10: Verify WMI profiling status/logs show successful polling
    # -------------------------------------------------------------------------
    # Wait for a reasonable time (> polling interval) before checking logs
    # In practice, you may want to mock or shorten the interval for test stability.
    wait_seconds = int(wmi_poll_interval) + 10
    try:
        await asyncio.sleep(wait_seconds)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sleep interrupted while waiting for WMI polling: %s", exc)

    # Navigate to Logs > Profiler
    try:
        await logs_menu_locator.click()
        await profiler_logs_menu_locator.click()
        await page.wait_for_load_state("networkidle", timeout=15_000)
    except PlaywrightError as exc:
        logger.error("Failed to navigate to Logs > Profiler: %s", exc)
        pytest.fail("Could not open Profiler logs to verify WMI polling status")

    # Verify at least one log entry indicates successful WMI polling
    try:
        await wmi_log_entry_locator.wait_for(state="visible", timeout=60_000)
    except PlaywrightError as exc:
        logger.error(
            "No successful WMI polling log entry found for host %s: %s", wmi_host, exc
        )
        pytest.fail(
            "Profiler logs do not show successful WMI polling for "
            f"host {wmi_host} after configured interval"
        )

    assert await wmi_log_entry_locator.is_visible(), (
        "A log entry indicating successful WMI polling should be visible "
        f"for host {wmi_host}"
    )