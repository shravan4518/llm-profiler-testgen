import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_019_forward_and_sync_endpoint_data_between_profiler_and_remote_pps(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_019: Integration of Forward and Sync Endpoint Data between Profiler and external PPS/PCS

    Validates that endpoint data can be forwarded and synchronized from Profiler to a
    remote PPS/PCS instance (pps-remote.domain.local).

    Preconditions:
        - Remote PPS/PCS is reachable and configured to accept endpoint data.
        - Trust/credentials are configured and valid.

    Steps:
        1. Log in as ppsadmin on local Profiler (handled by authenticated_page fixture).
        2. Navigate to Profiler > Profiler Configuration > Forward and Sync Endpoint Data.
        3. Enable endpoint data forwarding.
        4. Add target pps-remote.domain.local with appropriate credentials.
        5. Configure sync schedule or trigger "sync now".
        6. Save configuration.
        7. Trigger a sync (if not automatic).
        8. On remote PPS, log in and navigate to endpoints/profiler section.
        9. Verify endpoint records from local Profiler appear on remote system with
           accurate attributes.

    Expected Results:
        - Configuration saves successfully.
        - Sync completes without errors; logs show successful data transfer.
        - Remote system receives and displays endpoint data consistent with local Profiler.
        - Ongoing synchronization remains configured and active (if scheduled).
    """

    page = authenticated_page

    # Test configuration / data
    remote_pps_host = "pps-remote.domain.local"
    remote_pps_url = "https://pps-remote.domain.local/dana-na/auth/url_admin/welcome.cgi"
    remote_admin_username = "ppsadmin"          # Adjust as needed
    remote_admin_password = "ChangeMe123!"      # Adjust as needed
    test_endpoint_identifier = "test-endpoint-automation-019"  # Unique marker for verification
    sync_timeout_seconds = 180                  # Max wait time for sync completion

    # Helper: wait for a locator with timeout and good error reporting
    async def safe_wait_for(locator, state: str = "visible", timeout: int = 15000):
        try:
            await locator.wait_for(state=state, timeout=timeout)
        except PlaywrightError as e:
            raise AssertionError(
                f"Expected element did not reach state '{state}' within {timeout} ms: {locator}"
            ) from e

    # -------------------------------------------------------------------------
    # STEP 2: Navigate to Profiler > Profiler Configuration > Forward and Sync Endpoint Data
    # -------------------------------------------------------------------------
    # NOTE: The actual selectors will depend on the UI; these are examples and
    #       should be adjusted to match real application markup.

    try:
        # Open Profiler configuration menu
        profiler_menu = page.get_by_role("link", name="Profiler")
        await safe_wait_for(profiler_menu)
        await profiler_menu.click()

        profiler_config_menu = page.get_by_role("link", name="Profiler Configuration")
        await safe_wait_for(profiler_config_menu)
        await profiler_config_menu.click()

        forward_sync_link = page.get_by_role(
            "link", name="Forward and Sync Endpoint Data"
        )
        await safe_wait_for(forward_sync_link)
        await forward_sync_link.click()
    except PlaywrightError as e:
        raise AssertionError(
            "Failed to navigate to 'Forward and Sync Endpoint Data' configuration page."
        ) from e

    # Verify we are on the correct page
    forward_sync_header = page.get_by_role("heading", name="Forward and Sync Endpoint Data")
    await safe_wait_for(forward_sync_header)
    assert await forward_sync_header.is_visible(), (
        "Forward and Sync Endpoint Data configuration page did not load correctly."
    )

    # -------------------------------------------------------------------------
    # STEP 3: Enable endpoint data forwarding
    # -------------------------------------------------------------------------
    try:
        forwarding_toggle = page.get_by_role(
            "checkbox", name="Enable endpoint data forwarding"
        )
        await safe_wait_for(forwarding_toggle, state="attached")

        is_checked = await forwarding_toggle.is_checked()
        if not is_checked:
            await forwarding_toggle.check()
    except PlaywrightError as e:
        raise AssertionError(
            "Unable to enable endpoint data forwarding. Forwarding toggle not accessible."
        ) from e

    assert await forwarding_toggle.is_checked(), (
        "Endpoint data forwarding should be enabled but is not checked."
    )

    # -------------------------------------------------------------------------
    # STEP 4: Add target pps-remote.domain.local with appropriate credentials
    # -------------------------------------------------------------------------
    try:
        add_target_button = page.get_by_role("button", name="Add Target")
        await safe_wait_for(add_target_button)
        await add_target_button.click()
    except PlaywrightError as e:
        raise AssertionError("Failed to open 'Add Target' dialog.") from e

    # Fill in target details (host, credentials, etc.)
    try:
        target_name_input = page.get_by_label("Target Name")
        target_host_input = page.get_by_label("Host / FQDN")
        username_input = page.get_by_label("Username")
        password_input = page.get_by_label("Password")

        await safe_wait_for(target_name_input)
        await target_name_input.fill("Remote PPS - Automation")

        await safe_wait_for(target_host_input)
        await target_host_input.fill(remote_pps_host)

        await safe_wait_for(username_input)
        await username_input.fill(remote_admin_username)

        await safe_wait_for(password_input)
        await password_input.fill(remote_admin_password)

        save_target_button = page.get_by_role("button", name="Save Target")
        await safe_wait_for(save_target_button)
        await save_target_button.click()
    except PlaywrightError as e:
        raise AssertionError("Failed to configure remote PPS target in Profiler.") from e

    # Assert that target appears in the targets table
    target_row = page.get_by_role("row", name=remote_pps_host)
    await safe_wait_for(target_row)
    assert await target_row.is_visible(), (
        f"Configured remote PPS target '{remote_pps_host}' not listed in targets table."
    )

    # -------------------------------------------------------------------------
    # STEP 5: Configure sync schedule or set to “sync now” if manual option exists
    # -------------------------------------------------------------------------
    # Prefer manual "sync now" if available; otherwise, configure a near-future schedule.

    manual_sync_available = True
    sync_now_button = page.get_by_role("button", name="Sync Now")

    try:
        await sync_now_button.wait_for(state="visible", timeout=5000)
    except PlaywrightError:
        manual_sync_available = False

    if not manual_sync_available:
        # Fallback: set a schedule (e.g., every 5 minutes)
        try:
            schedule_dropdown = page.get_by_label("Sync Schedule")
            await safe_wait_for(schedule_dropdown)
            await schedule_dropdown.select_option("every_5_minutes")
        except PlaywrightError as e:
            raise AssertionError(
                "Neither 'Sync Now' nor a configurable sync schedule was available."
            ) from e

    # -------------------------------------------------------------------------
    # STEP 6: Save configuration
    # -------------------------------------------------------------------------
    try:
        save_config_button = page.get_by_role("button", name="Save")
        await safe_wait_for(save_config_button)
        await save_config_button.click()
    except PlaywrightError as e:
        raise AssertionError("Failed to save forward/sync configuration.") from e

    # Confirm save success via notification or banner
    save_success_banner = page.get_by_text("Configuration saved successfully", exact=False)
    await safe_wait_for(save_success_banner)
    assert await save_success_banner.is_visible(), (
        "Configuration save did not display a success confirmation banner."
    )

    # -------------------------------------------------------------------------
    # STEP 7: Trigger a sync (if not automatic)
    # -------------------------------------------------------------------------
    if manual_sync_available:
        try:
            await sync_now_button.click()
        except PlaywrightError as e:
            raise AssertionError("Failed to trigger manual synchronization (Sync Now).") from e

    # Wait for sync completion indicator/log message
    # Example: a status label or log entry like "Last sync: Success"
    sync_complete = False
    sync_deadline = datetime.utcnow() + timedelta(seconds=sync_timeout_seconds)

    while datetime.utcnow() < sync_deadline and not sync_complete:
        await asyncio.sleep(5)
        await page.reload()
        sync_status = page.get_by_text("Last sync status: Success", exact=False)
        if await sync_status.is_visible():
            sync_complete = True

    assert sync_complete, (
        f"Synchronization did not complete successfully within {sync_timeout_seconds} seconds."
    )

    # -------------------------------------------------------------------------
    # STEP 8: On remote PPS, log in and navigate to endpoints/profiler section
    # -------------------------------------------------------------------------
    # Open a new context/page for the remote PPS system to avoid sharing session/cookies.
    remote_context = await browser.new_context(ignore_https_errors=True)
    remote_page = await remote_context.new_page()

    try:
        await remote_page.goto(remote_pps_url, wait_until="domcontentloaded", timeout=60000)
    except PlaywrightError as e:
        await remote_context.close()
        raise AssertionError(
            f"Failed to navigate to remote PPS URL: {remote_pps_url}"
        ) from e

    # Login to remote PPS
    try:
        username_field = remote_page.get_by_label("Username")
        password_field = remote_page.get_by_label("Password")
        sign_in_button = remote_page.get_by_role("button", name="Sign In")

        await safe_wait_for(username_field)
        await username_field.fill(remote_admin_username)

        await safe_wait_for(password_field)
        await password_field.fill(remote_admin_password)

        await safe_wait_for(sign_in_button)
        await sign_in_button.click()
    except PlaywrightError as e:
        await remote_context.close()
        raise AssertionError("Failed to log in to remote PPS as admin.") from e

    # Verify remote admin home/dashboard is visible
    remote_dashboard_header = remote_page.get_by_role("heading", name="Admin Console")
    await safe_wait_for(remote_dashboard_header)
    assert await remote_dashboard_header.is_visible(), (
        "Remote PPS admin dashboard did not load after login."
    )

    # Navigate to endpoints/profiler section
    try:
        endpoints_menu = remote_page.get_by_role("link", name="Endpoints")
        await safe_wait_for(endpoints_menu)
        await endpoints_menu.click()

        profiler_submenu = remote_page.get_by_role("link", name="Profiler")
        await safe_wait_for(profiler_submenu)
        await profiler_submenu.click()
    except PlaywrightError as e:
        await remote_context.close()
        raise AssertionError(
            "Failed to navigate to the endpoints/profiler section on remote PPS."
        ) from e

    profiler_header_remote = remote_page.get_by_role("heading", name="Profiler Endpoints")
    await safe_wait_for(profiler_header_remote)
    assert await profiler_header_remote.is_visible(), (
        "Profiler endpoints page did not load correctly on remote PPS."
    )

    # -------------------------------------------------------------------------
    # STEP 9: Verify endpoint records from local Profiler appear on remote system
    # -------------------------------------------------------------------------
    # This assumes there is at least one endpoint with a known identifier.
    # For robust testing, ensure such an endpoint exists before running the test.
    # Here we search using a known identifier (test_endpoint_identifier).
    try:
        search_input = remote_page.get_by_placeholder("Search endpoints")
        await safe_wait_for(search_input)
        await search_input.fill(test_endpoint_identifier)
        await search_input.press("Enter")
    except PlaywrightError as e:
        await remote_context.close()
        raise AssertionError(
            "Failed to search for endpoint on remote PPS profiler endpoints page."
        ) from e

    # Wait for endpoint row to appear
    endpoint_row_remote = remote_page.get_by_role("row", name=test_endpoint_identifier)
    try:
        await safe_wait_for(endpoint_row_remote)
    except AssertionError as e:
        await remote_context.close()
        raise AssertionError(
            f"Endpoint with identifier '{test_endpoint_identifier}' not found on remote PPS."
        ) from e

    assert await endpoint_row_remote.is_visible(), (
        "Synchronized endpoint record is not visible in remote PPS endpoints table."
    )

    # Optionally verify key attributes match expected values
    # Example: IP, OS, last seen, etc. Adjust selectors/labels to match actual UI.
    try:
        ip_cell = endpoint_row_remote.get_by_role("cell", name="IP Address", exact=False)
        os_cell = endpoint_row_remote.get_by_role("cell", name="OS", exact=False)

        # Example assertions – replace with real expected values if known
        assert await ip_cell.is_visible(), "IP address cell not visible for synchronized endpoint."
        assert await os_cell.is_visible(), "OS cell not visible for synchronized endpoint."
    except PlaywrightError:
        # Do not fail on attribute visibility selector issues, but log via assertion
        raise AssertionError(
            "Unable to verify endpoint attribute cells on remote PPS; "
            "check table structure and selectors."
        )

    # -------------------------------------------------------------------------
    # POSTCONDITION: Ongoing synchronization remains configured and active
    # -------------------------------------------------------------------------
    # Re-check on local Profiler that forwarding is still enabled and target is present.
    await page.bring_to_front()

    forwarding_toggle = page.get_by_role(
        "checkbox", name="Enable endpoint data forwarding"
    )
    await safe_wait_for(forwarding_toggle, state="attached")
    assert await forwarding_toggle.is_checked(), (
        "Endpoint data forwarding should remain enabled after sync."
    )

    target_row = page.get_by_role("row", name=remote_pps_host)
    await safe_wait_for(target_row)
    assert await target_row.is_visible(), (
        "Remote PPS target configuration should remain present after sync."
    )

    # Clean up remote context
    await remote_context.close()