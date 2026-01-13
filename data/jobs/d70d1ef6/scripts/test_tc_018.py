import asyncio
import logging
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.medium
async def test_tc_018_mdm_profiler_integration(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_018: Integration of Profiler with MDM collector configuration

    Validates that configuring an additional MDM data collector allows the
    Profiler to collect mobile device attributes from the MDM server.

    Prerequisites:
        - MDM server `mdm1.domain.local` with valid API credentials.
        - Additional data collectors configuration page available.
        - `authenticated_page` fixture logs in as `ppsadmin`.

    Steps:
        1. Log in as `ppsadmin`.  (via authenticated_page fixture)
        2. Navigate to Profiler > Profiler Configuration > Additional Data Collectors.
        3. Add new MDM server with provided URL and credentials.
        4. Enable MDM collector.
        5. Click `Save Changes`.
        6. Wait for initial sync/profiling cycle.
        7. Verify Profiler endpoint list shows mobile attributes derived from MDM.

    Expected Results:
        - Settings save successfully and MDM collector becomes active.
        - Profiler logs show successful access to MDM API.
        - Endpoint records in Profiler display MDM-derived attributes.
    """

    page: Page = authenticated_page

    # --- Test data / configuration (would normally come from config/fixtures) ---
    mdm_server_name = "MDM Server - mdm1"
    mdm_server_url = "https://mdm1.domain.local/api"
    mdm_api_username = "mdm_api_user"
    mdm_api_password = "mdm_api_password"
    known_device_identifier = "device-12345"  # e.g., device name or ID enrolled in MDM

    # Timeouts and polling intervals
    navigation_timeout_ms = 30_000
    save_timeout_ms = 30_000
    sync_timeout_seconds = 300  # wait up to 5 minutes for initial sync
    sync_poll_interval_seconds = 15

    # Helper for safe click with logging and error handling
    async def safe_click(selector: str, description: str, timeout: int = 30_000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await page.click(selector)
            logger.info("Clicked: %s (%s)", selector, description)
        except PlaywrightError as exc:
            logger.error("Failed to click %s (%s): %s", selector, description, exc)
            raise

    # Helper for safe fill with logging and error handling
    async def safe_fill(selector: str, value: str, description: str, timeout: int = 30_000) -> None:
        try:
            await page.wait_for_selector(selector, timeout=timeout)
            await page.fill(selector, value)
            logger.info("Filled %s (%s) with value: %s", selector, description, value)
        except PlaywrightError as exc:
            logger.error("Failed to fill %s (%s): %s", selector, description, exc)
            raise

    # -------------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin`
    # -------------------------------------------------------------------------
    # The authenticated_page fixture is expected to provide a logged-in session
    # as `ppsadmin`. We still verify that we are on an admin/profiler page.
    try:
        await page.wait_for_load_state("networkidle", timeout=navigation_timeout_ms)
    except PlaywrightError as exc:
        logger.error("Initial page did not reach network idle state: %s", exc)
        raise

    # Basic sanity check that we are logged in (for example, admin header present)
    admin_header_locator = page.locator("text=Admin Console")
    assert await admin_header_locator.count() > 0, (
        "Admin Console header not found; user may not be logged in as ppsadmin."
    )

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Additional Data Collectors
    # -------------------------------------------------------------------------
    # NOTE: Selectors below are examples and might need adjustment to match
    # the actual application under test.

    # Navigate to Profiler main menu
    await safe_click("text=Profiler", "Profiler main menu")

    # Navigate to Profiler Configuration
    await safe_click("text=Profiler Configuration", "Profiler Configuration menu")

    # Navigate to Additional Data Collectors tab / section
    await safe_click("text=Additional Data Collectors", "Additional Data Collectors tab")

    # Verify that the Additional Data Collectors page loaded
    collectors_header = page.locator("text=Additional Data Collectors")
    assert await collectors_header.is_visible(), (
        "Additional Data Collectors page did not load correctly."
    )

    # -------------------------------------------------------------------------
    # Step 3: Add new MDM server with provided URL and credentials
    # -------------------------------------------------------------------------
    # Open "Add MDM Collector" dialog or section
    await safe_click("button:has-text('Add MDM Collector')", "Add MDM Collector button")

    # Fill in MDM server configuration form
    await safe_fill("input[name='collectorName']", mdm_server_name, "MDM Collector Name")
    await safe_fill("input[name='mdmUrl']", mdm_server_url, "MDM Server URL")
    await safe_fill("input[name='mdmUsername']", mdm_api_username, "MDM API Username")
    await safe_fill("input[name='mdmPassword']", mdm_api_password, "MDM API Password")

    # Optional: test connectivity if the UI provides such a button
    test_connection_button = page.locator("button:has-text('Test Connection')")
    if await test_connection_button.count() > 0:
        await test_connection_button.click()
        logger.info("Clicked Test Connection for MDM server.")

        # Wait for success / failure notification
        try:
            await page.wait_for_selector(
                "text=Connection successful",
                timeout=save_timeout_ms,
            )
            logger.info("MDM connection test succeeded.")
        except PlaywrightError:
            # Capture any visible error message for debugging
            error_message = await page.locator(".error, .alert-error").first.text_content()
            logger.error(
                "MDM connection test failed. Error message: %s",
                error_message or "No error text found.",
            )
            pytest.fail("MDM connection test failed; cannot proceed with configuration.")

    # -------------------------------------------------------------------------
    # Step 4: Enable MDM collector
    # -------------------------------------------------------------------------
    # Assume there is a checkbox or toggle to enable this collector
    mdm_enable_checkbox = page.locator("input[name='mdmEnabled']")
    try:
        await mdm_enable_checkbox.wait_for(state="visible", timeout=save_timeout_ms)
        is_checked = await mdm_enable_checkbox.is_checked()
        if not is_checked:
            await mdm_enable_checkbox.check()
            logger.info("Enabled MDM collector checkbox.")
    except PlaywrightError as exc:
        logger.error("Failed to enable MDM collector: %s", exc)
        raise

    # -------------------------------------------------------------------------
    # Step 5: Click `Save Changes`
    # -------------------------------------------------------------------------
    await safe_click("button:has-text('Save Changes')", "Save Changes button", timeout=save_timeout_ms)

    # Assert that a success notification appears
    try:
        await page.wait_for_selector("text=Settings saved successfully", timeout=save_timeout_ms)
        logger.info("Settings saved successfully notification detected.")
    except PlaywrightError:
        # Fallback: try generic success/error selectors
        error_banner = page.locator(".error, .alert-error").first
        if await error_banner.is_visible():
            error_text = await error_banner.text_content()
            logger.error("Error after saving MDM collector settings: %s", error_text)
            pytest.fail(f"Failed to save MDM collector settings: {error_text}")
        pytest.fail("No success message after saving MDM collector settings.")

    # Validate that the MDM collector appears as active/enabled in the list
    mdm_row_locator = page.locator("tr", has_text=mdm_server_name)
    assert await mdm_row_locator.count() > 0, (
        "MDM collector row not found in the Additional Data Collectors list."
    )

    mdm_status_cell = mdm_row_locator.locator("td.status")
    mdm_status_text = (await mdm_status_cell.text_content() or "").strip().lower()
    assert "active" in mdm_status_text or "enabled" in mdm_status_text, (
        f"MDM collector is not active/enabled. Status: {mdm_status_text}"
    )

    # -------------------------------------------------------------------------
    # Step 6: Wait for initial sync/profiling cycle
    # -------------------------------------------------------------------------
    # Strategy:
    #   - Periodically check logs or status indicator that shows successful
    #     MDM sync or last sync time.
    #   - Time out after `sync_timeout_seconds` with a clear error.

    sync_deadline = datetime.utcnow() + timedelta(seconds=sync_timeout_seconds)
    sync_success = False
    last_error_message = None

    while datetime.utcnow() < sync_deadline:
        # Refresh or navigate to a logs/status view for the MDM collector
        # (Assume there is a "View Logs" or "Details" action in the MDM row.)
        details_button = mdm_row_locator.locator("button:has-text('Details')")
        if await details_button.count() > 0:
            await details_button.click()
        else:
            # If no details button, try a generic logs tab
            await safe_click("text=Logs", "Logs tab", timeout=navigation_timeout_ms)

        # Look for evidence of successful MDM API access
        log_success_locator = page.locator(
            "text=/MDM API access (successful|completed)/i"
        )
        if await log_success_locator.count() > 0:
            sync_success = True
            logger.info("Detected successful MDM API access in logs.")
            break

        # Capture any error in logs for reporting if we eventually time out
        log_error_locator = page.locator("text=/MDM API access failed|error/i").first
        if await log_error_locator.is_visible():
            last_error_message = await log_error_locator.text_content()
            logger.warning("Detected MDM API error in logs: %s", last_error_message)

        logger.info(
            "MDM sync not yet confirmed; waiting %s seconds before next check.",
            sync_poll_interval_seconds,
        )
        await asyncio.sleep(sync_poll_interval_seconds)

        # Navigate back to the Additional Data Collectors list if needed
        await safe_click("text=Additional Data Collectors", "Additional Data Collectors tab")

    assert sync_success, (
        "MDM initial sync/profiling cycle did not complete successfully within "
        f"{sync_timeout_seconds} seconds. Last error: {last_error_message or 'None'}"
    )

    # -------------------------------------------------------------------------
    # Step 7: Verify Profiler endpoint list shows mobile attributes
    # -------------------------------------------------------------------------
    # Navigate to Profiler endpoint list
    await safe_click("text=Profiler", "Profiler main menu")
    await safe_click("text=Endpoints", "Profiler Endpoints menu")

    # Filter/search for a known enrolled device
    await safe_fill("input[name='endpointSearch']", known_device_identifier, "Endpoint search field")
    await safe_click("button:has-text('Search')", "Endpoint search button")

    # Wait for search results
    endpoint_row = page.locator("tr", has_text=known_device_identifier).first
    try:
        await endpoint_row.wait_for(state="visible", timeout=navigation_timeout_ms)
    except PlaywrightError:
        pytest.fail(
            f"Known enrolled device '{known_device_identifier}' not found in Profiler endpoints."
        )

    # Inspect device details to verify MDM-derived attributes
    # Assume there is a details view or expandable row
    details_link = endpoint_row.locator("a:has-text('Details'), button:has-text('Details')")
    if await details_link.count() > 0:
        await details_link.click()
    else:
        # If no details link, try clicking the row itself
        await endpoint_row.click()

    # Check for typical mobile attributes derived from MDM
    os_field = page.locator("text=/OS:/i")
    device_type_field = page.locator("text=/Device Type:/i")
    mdm_source_field = page.locator("text=/Source:.*MDM/i")

    assert await os_field.is_visible(), "OS attribute not visible on endpoint details (expected from MDM)."
    assert await device_type_field.is_visible(), (
        "Device Type attribute not visible on endpoint details (expected from MDM)."
    )
    assert await mdm_source_field.count() > 0, (
        "Endpoint details do not indicate MDM as a data source."
    )

    # Optionally, we can validate that OS and Device Type look like mobile values
    os_text = (await os_field.text_content() or "").lower()
    device_type_text = (await device_type_field.text_content() or "").lower()

    assert any(mobile_os in os_text for mobile_os in ["android", "ios"]), (
        f"OS attribute does not appear to be a mobile OS: '{os_text}'."
    )
    assert any(
        mobile_type in device_type_text for mobile_type in ["phone", "tablet", "mobile"]
    ), (
        f"Device Type attribute does not appear to be a mobile device: '{device_type_text}'."
    )

    # -------------------------------------------------------------------------
    # Postconditions:
    #   - MDM integration remains configured and active.
    # -------------------------------------------------------------------------
    # Verify that the MDM collector remains active after validation
    await safe_click("text=Profiler", "Profiler main menu")
    await safe_click("text=Profiler Configuration", "Profiler Configuration menu")
    await safe_click("text=Additional Data Collectors", "Additional Data Collectors tab")

    mdm_row_locator = page.locator("tr", has_text=mdm_server_name)
    assert await mdm_row_locator.count() > 0, (
        "MDM collector configuration is missing after test execution."
    )

    mdm_status_cell = mdm_row_locator.locator("td.status")
    mdm_status_text = (await mdm_status_cell.text_content() or "").strip().lower()
    assert "active" in mdm_status_text or "enabled" in mdm_status_text, (
        f"MDM collector is not active/enabled at test end. Status: {mdm_status_text}"
    )