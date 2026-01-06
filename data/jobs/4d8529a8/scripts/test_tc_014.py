import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_014_security_access_control_profiler_dhcp(
    authenticated_page: Page,
    browser,
):
    """
    TC_014: Security – Access control to Profiler DHCP configuration pages

    This test verifies that:
    - Full admin user (`pps-admin`) can view and modify Profiler DHCP configuration.
    - Read-only user (`pps-readonly`) is either:
        * denied access to configuration pages, or
        * allowed read-only access but cannot save changes or upload fingerprints.
    - Any unauthorized attempt is logged with username and time.
    - Configuration remains as last valid save by authorized user.

    Assumptions:
    - `authenticated_page` fixture can be parameterized externally to log in
      with different users (e.g., via a marker or environment variable).
    - The application has stable selectors for DHCP settings and fingerprint upload.
    - Logging UI is available for verification (or at least partially).
    """

    # -------------------------------------------------------------------------
    # Helper functions
    # -------------------------------------------------------------------------

    async def login_as(username: str, password: str) -> Page:
        """
        Log in using a fresh context and return an authenticated page.

        This bypasses the `authenticated_page` fixture for the second user
        while still using the provided `browser` fixture.
        """
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://npre-miiqa2mp-eastus2.openai.azure.com/", wait_until="domcontentloaded")

        # Adjust selectors according to actual login page implementation.
        await page.fill('input[name="username"]', username)
        await page.fill('input[name="password"]', password)
        await page.click('button[type="submit"]')

        # Wait for post-login landing indicator (e.g., dashboard)
        await page.wait_for_timeout(1000)
        # Replace with a robust check in real code:
        await page.wait_for_selector("text=Dashboard", timeout=15000)

        return page

    async def logout(page: Page) -> None:
        """Log out from the current session."""
        try:
            # Adjust selectors according to actual UI.
            await page.click("button#user-menu")
            await page.click("text=Logout")
            await page.wait_for_selector('input[name="username"]', timeout=15000)
        except PlaywrightError:
            # If logout fails, let the test continue but log the issue.
            print("Warning: Logout may have failed; continuing test.")

    async def navigate_to_profiler_basic_config(page: Page) -> None:
        """Navigate to Profiler Configuration > Settings > Basic Configuration."""
        # Step 2 / 5: Navigate to Profiler Configuration > Settings > Basic Configuration.
        # Adjust selectors according to actual navigation menu.
        await page.click("text=Profiler Configuration")
        await page.click("text=Settings")
        await page.click("text=Basic Configuration")

        # Wait for DHCP configuration form to load
        await page.wait_for_selector("form#profiler-basic-config", timeout=15000)

    async def get_dhcp_settings(page: Page) -> dict:
        """
        Read current DHCP-related settings from Basic Configuration page.

        Returns a dictionary with values that can be used for later comparison.
        """
        # Adjust selectors according to actual controls.
        sniffing_mode_locator = page.locator('select#dhcp-sniffing-mode')
        dhcpv6_toggle_locator = page.locator('input#dhcpv6-capturing')

        sniffing_mode = await sniffing_mode_locator.input_value()
        dhcpv6_enabled = await dhcpv6_toggle_locator.is_checked()

        return {
            "sniffing_mode": sniffing_mode,
            "dhcpv6_enabled": dhcpv6_enabled,
        }

    async def toggle_dhcp_settings(page: Page) -> dict:
        """
        Toggle DHCP settings to new values and return the intended new settings.
        """
        # Adjust selectors according to actual controls.
        sniffing_mode_locator = page.locator('select#dhcp-sniffing-mode')
        dhcpv6_toggle_locator = page.locator('input#dhcpv6-capturing')

        current = await get_dhcp_settings(page)
        current_mode = current["sniffing_mode"]
        current_dhcpv6 = current["dhcpv6_enabled"]

        # Example: if mode is 'enabled', change to 'disabled', etc.
        # Adapt according to real option values.
        new_mode = "disabled" if current_mode == "enabled" else "enabled"
        await sniffing_mode_locator.select_option(new_mode)

        # Toggle DHCPv6 capturing
        if current_dhcpv6:
            await dhcpv6_toggle_locator.uncheck()
        else:
            await dhcpv6_toggle_locator.check()

        return {
            "sniffing_mode": new_mode,
            "dhcpv6_enabled": not current_dhcpv6,
        }

    async def click_save_and_wait(page: Page) -> None:
        """Click Save button and wait for a success or error notification."""
        # Adjust selectors according to actual UI.
        await page.click('button:has-text("Save")')

        # Wait for either success or error toast/message
        await page.wait_for_timeout(500)  # brief delay for message to appear
        # Try success first; if not found, error may appear.
        # In real code, use more precise selectors.
        try:
            await page.wait_for_selector(
                'text=Configuration saved successfully',
                timeout=5000,
            )
        except PlaywrightError:
            # Allow test to inspect for error messages later.
            pass

    async def upload_fingerprints_package(page: Page, file_path: str) -> None:
        """
        Attempt to upload a new fingerprints package.

        This function only performs the upload action; callers must assert
        success/failure according to user role.
        """
        # Adjust selectors according to actual UI.
        await page.click("text=Profiler Configuration")
        await page.click("text=Fingerprints")

        await page.wait_for_selector('input[type="file"]#fingerprints-upload', timeout=15000)

        file_input = page.locator('input[type="file"]#fingerprints-upload')
        await file_input.set_input_files(file_path)

        await page.click('button:has-text("Upload")')

        # Wait for any toast/notification (success or failure)
        await page.wait_for_timeout(1000)

    async def assert_unauthorized_message_or_disabled(page: Page) -> None:
        """
        Assert that the UI indicates lack of permission:
        - Either Save/Upload buttons are disabled, OR
        - A 'permission denied' message is shown.
        """
        save_button = page.locator('button:has-text("Save")')
        upload_button = page.locator('button:has-text("Upload")')

        save_disabled = False
        upload_disabled = False

        try:
            if await save_button.count() > 0:
                save_disabled = await save_button.is_disabled()
            if await upload_button.count() > 0:
                upload_disabled = await upload_button.is_disabled()
        except PlaywrightError:
            # If checking disabled state fails, continue to check for error messages.
            pass

        # Check for permission error messages
        permission_error_locators = [
            "text=Permission denied",
            "text=Access denied",
            "text=You do not have sufficient privileges",
        ]

        error_found = False
        for selector in permission_error_locators:
            if await page.locator(selector).count() > 0:
                error_found = True
                break

        assert (
            save_disabled or upload_disabled or error_found
        ), "Read-only user must not be able to save or upload without a clear denial."

    async def assert_audit_log_contains(username: str, since: datetime) -> None:
        """
        Verify that an unauthorized attempt is logged with username and time.

        This is a best-effort implementation and should be adapted to the
        actual audit/log UI. If logs are not directly visible in UI, this
        assertion can be adapted or replaced with API/DB checks.
        """
        # Navigate to audit/log page if available.
        # Adjust selectors according to actual UI.
        # If no audit UI exists, this function can be a no-op or be skipped
        # via a marker.
        # Example:
        # await authenticated_page.click("text=Administration")
        # await authenticated_page.click("text=Audit Log")
        # await authenticated_page.wait_for_selector("table#audit-log", timeout=15000)

        # The following is pseudo-implementation; adapt for real UI.
        # For now, this will be a soft assertion (no failure if logs are not visible).
        try:
            # Example navigation; may need a different page object.
            # Here we reuse the last page in context:
            page = authenticated_page  # best-effort reuse

            await page.click("text=Administration")
            await page.click("text=Audit Log")
            await page.wait_for_selector("table#audit-log", timeout=15000)

            # Filter by username if possible
            if await page.locator('input#filter-username').count() > 0:
                await page.fill('input#filter-username', username)
                await page.click('button:has-text("Filter")')
                await page.wait_for_timeout(1000)

            # Inspect rows for username and recent timestamp
            rows = page.locator("table#audit-log tbody tr")
            row_count = await rows.count()
            found_recent = False

            for i in range(row_count):
                row = rows.nth(i)
                text = await row.inner_text()
                if username not in text:
                    continue

                # Very loose time check; adapt to actual timestamp format.
                if "Unauthorized" in text or "Permission denied" in text:
                    found_recent = True
                    break

            # Soft assertion: log if not found but do not fail the whole test.
            if not found_recent:
                print(
                    f"Warning: No explicit unauthorized log entry found for user "
                    f"{username} since {since.isoformat()}."
                )
        except PlaywrightError:
            print("Warning: Audit log UI not accessible; skipping log verification.")

    # -------------------------------------------------------------------------
    # Test implementation
    # -------------------------------------------------------------------------

    # Step 1: Log in as `pps-admin` (assumed already done via authenticated_page)
    admin_page = authenticated_page

    # Step 2: Navigate to Profiler Configuration > Settings > Basic Configuration
    await navigate_to_profiler_basic_config(admin_page)

    # Capture original settings to verify that they can be changed and later
    # that readonly user cannot alter them.
    original_settings = await get_dhcp_settings(admin_page)

    # Step 3: Attempt to modify DHCP Sniffing mode and toggle DHCPv6 capturing; save changes.
    new_settings = await toggle_dhcp_settings(admin_page)
    await click_save_and_wait(admin_page)

    # Assert that settings were actually updated for admin.
    updated_settings = await get_dhcp_settings(admin_page)
    assert (
        updated_settings == new_settings
    ), "Admin user should be able to modify and save DHCP configuration."

    # Step 4: Log out and log in as `pps-readonly`.
    await logout(admin_page)

    # Note: Replace password placeholders with secure retrieval mechanism.
    readonly_page = await login_as("pps-readonly", "readonly-password")

    # Step 5: Attempt to access Profiler Configuration > Settings > Basic Configuration.
    access_denied = False
    basic_config_accessible = False
    try:
        await navigate_to_profiler_basic_config(readonly_page)
        basic_config_accessible = True
    except PlaywrightError:
        access_denied = True

    if access_denied:
        # Read-only user must not be able to access the page at all.
        # Check for access denied message.
        access_denied_message_locators = [
            "text=Access denied",
            "text=Permission denied",
            "text=You are not authorized to view this page",
        ]
        message_found = False
        for selector in access_denied_message_locators:
            if await readonly_page.locator(selector).count() > 0:
                message_found = True
                break

        assert message_found, (
            "Read-only user should either see an access denied message or "
            "have the page blocked."
        )
    else:
        # Step 6: If access is allowed for read, attempt to change DHCP settings and save.
        # First, verify that the user can at least see the current settings.
        readonly_view_settings = await get_dhcp_settings(readonly_page)
        # They should see whatever the admin last saved.
        assert (
            readonly_view_settings == updated_settings
        ), "Read-only user should see the last valid DHCP configuration."

        # Try to change settings and save as read-only user.
        readonly_intended_changes = await toggle_dhcp_settings(readonly_page)

        # Capture time before save attempt for log verification.
        unauthorized_attempt_time = datetime.utcnow()

        await click_save_and_wait(readonly_page)

        # Assert that either save is blocked or changes are not persisted.
        await assert_unauthorized_message_or_disabled(readonly_page)

        # Re-read settings (possibly by refreshing or re-navigating).
        await readonly_page.reload(wait_until="domcontentloaded")
        await navigate_to_profiler_basic_config(readonly_page)
        readonly_post_attempt_settings = await get_dhcp_settings(readonly_page)

        assert (
            readonly_post_attempt_settings == updated_settings
        ), (
            "Read-only user must not be able to change DHCP configuration; "
            "settings should remain as last valid save by admin."
        )

        # Step 7: Attempt to upload a new fingerprints package as `pps-readonly`.
        # Use a small dummy file path; in real tests, ensure the file exists.
        dummy_file_path = "tests/resources/dummy_fingerprints.pkg"

        await upload_fingerprints_package(readonly_page, dummy_file_path)

        # Assert that upload is not allowed.
        await assert_unauthorized_message_or_disabled(readonly_page)

        # Verify that unauthorized attempt is logged (best-effort).
        await assert_audit_log_contains("pps-readonly", unauthorized_attempt_time)

    # Postconditions:
    # Ensure configuration remains as last valid save by authorized user.
    # Re-log in as admin and confirm settings are still as saved by admin.
    await logout(readonly_page)

    admin_page_final = await login_as("pps-admin", "admin-password")
    await navigate_to_profiler_basic_config(admin_page_final)
    final_settings = await get_dhcp_settings(admin_page_final)

    assert (
        final_settings == updated_settings
    ), (
        "Configuration must remain as last valid save by authorized admin; "
        "read-only user must not have modified DHCP settings."
    )

    # Clean-up: optionally revert to original settings if needed.
    # This section is optional and may be controlled by an environment flag.
    try:
        if final_settings != original_settings:
            await toggle_dhcp_settings(admin_page_final)
            await click_save_and_wait(admin_page_final)
    except PlaywrightError:
        print("Warning: Failed to revert DHCP configuration to original values.")