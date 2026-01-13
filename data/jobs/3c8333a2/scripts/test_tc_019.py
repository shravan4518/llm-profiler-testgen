import asyncio
import re
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error, Response


@pytest.mark.asyncio
async def test_tc_019_profiler_configuration_access_control(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_019: Security – verify only authorized admin can access Profiler Configuration.

    This test verifies that:
    - A limited user (PulseUser) cannot access Profiler Configuration via UI or direct URL.
    - An admin user (TPSAdmin) can access and modify Profiler Configuration pages normally.

    Assumptions:
    - `authenticated_page` fixture returns a logged-in page for a default user.
      For this test, we explicitly log out and log in as required users.
    - Login page is at:
        https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi
    """

    base_url = "https://10.34.50.201"
    login_url = f"{base_url}/dana-na/auth/url_admin/welcome.cgi"
    # This is an example target URL; adjust path if your app uses a different route
    profiler_basic_config_url = (
        f"{base_url}/dana-na/admin/profiler/config/basic_configuration.cgi"
    )

    page: Page = authenticated_page

    async def login(username: str, password: str) -> None:
        """Log into the application with the given credentials."""
        await page.goto(login_url, wait_until="networkidle")

        # Replace selectors below with actual login form selectors
        await page.fill("input[name='username']", username)
        await page.fill("input[name='password']", password)
        await page.click("button[type='submit']")

        # Assert login succeeded by checking for a known post-login element
        # (e.g., header, user menu, or dashboard element)
        try:
            await page.wait_for_selector(
                "nav[role='navigation'], #mainMenu, text=/Dashboard/i",
                timeout=10_000,
            )
        except Error as exc:
            pytest.fail(f"Login failed for user '{username}': {exc}")

    async def logout() -> None:
        """Log out of the application if possible, ignore errors if already logged out."""
        try:
            # Replace selector with actual logout link/button
            await page.click("text=/Log Out|Sign Out|Logout/i", timeout=5_000)
            await page.wait_for_url(re.compile(r".*welcome\.cgi.*"), timeout=10_000)
        except Error:
            # If logout control is not found, attempt direct navigation to login page
            await page.goto(login_url, wait_until="networkidle")

    async def open_new_page() -> Page:
        """Open a new page from the existing browser instance."""
        context = page.context
        return await context.new_page()

    async def assert_access_denied(
        target_page: Page,
        expected_url_fragment: str,
        error_text_patterns: Optional[list[str]] = None,
    ) -> None:
        """
        Assert that access to a page is denied either by:
        - redirecting away from the target URL, or
        - showing an explicit 'Access Denied' / authorization error.
        """
        if error_text_patterns is None:
            error_text_patterns = [
                "Access Denied",
                "Unauthorized",
                "Not authorized",
                "Insufficient privileges",
                "You do not have permission",
            ]

        # Check that we are not actually on the target URL
        current_url = target_page.url
        assert expected_url_fragment not in current_url, (
            "Limited user should not remain on Profiler Configuration URL, "
            f"but current URL is '{current_url}'."
        )

        # Look for any authorization error message
        error_locator = target_page.locator(
            "text=/(" + "|".join(error_text_patterns) + ")/i"
        )
        has_error_message = await error_locator.first.is_visible()

        # If no explicit error message, ensure we were redirected to a safe page
        assert has_error_message or re.search(
            r"welcome\.cgi|home|dashboard|error", current_url, re.IGNORECASE
        ), (
            "Limited user neither sees an authorization error nor is clearly "
            f"redirected away from Profiler Configuration. Current URL: {current_url}"
        )

    # ----------------------------------------------------------------------
    # STEP 1: Log in as PulseUser (limited user)
    # ----------------------------------------------------------------------
    await logout()
    await login(username="PulseUser", password="PulseUser")  # adjust password as needed

    # ----------------------------------------------------------------------
    # STEP 2: Attempt to navigate to Profiler Configuration via UI
    # ----------------------------------------------------------------------
    # Try to open Profiler menu and look for Profiler Configuration entries
    profiler_menu_selector = "text=/Profiler/i"
    profiler_config_menu_selector = "text=/Profiler Configuration|Profiler Config/i"
    settings_menu_selector = "text=/Settings/i"
    basic_config_menu_selector = "text=/Basic Configuration/i"

    profiler_menu_visible = await page.locator(profiler_menu_selector).first.is_visible()
    pulseuser_ui_accessible = False

    if profiler_menu_visible:
        await page.click(profiler_menu_selector)
        await asyncio.sleep(0.5)

        profiler_config_visible = await page.locator(
            profiler_config_menu_selector
        ).first.is_visible()

        if profiler_config_visible:
            await page.click(profiler_config_menu_selector)
            await asyncio.sleep(0.5)

            settings_visible = await page.locator(
                settings_menu_selector
            ).first.is_visible()
            if settings_visible:
                await page.click(settings_menu_selector)
                await asyncio.sleep(0.5)

                basic_config_visible = await page.locator(
                    basic_config_menu_selector
                ).first.is_visible()
                if basic_config_visible:
                    pulseuser_ui_accessible = True

    # Assert that limited user does NOT see the Profiler Configuration menu path
    assert not pulseuser_ui_accessible, (
        "Limited user 'PulseUser' should not see Profiler Configuration menu items "
        "via the UI."
    )

    # ----------------------------------------------------------------------
    # STEP 3: If link not visible, attempt direct URL entry to config page
    # ----------------------------------------------------------------------
    # Use a new page so we can intercept response status cleanly
    limited_user_page = await open_new_page()
    response: Response | None = None
    try:
        response = await limited_user_page.goto(
            profiler_basic_config_url, wait_until="networkidle"
        )
    except Error:
        # Navigation errors are acceptable here; we will assert via URL and content
        pass

    # If we got a response, ensure we did not get a successful 2xx/3xx to the config page
    if response is not None:
        assert response.status not in {200, 201, 202, 204}, (
            "Limited user 'PulseUser' should not receive a successful response "
            f"({response.status}) when accessing Profiler Configuration directly."
        )

    await assert_access_denied(
        target_page=limited_user_page,
        expected_url_fragment="/profiler/config/basic_configuration",
    )

    # ----------------------------------------------------------------------
    # STEP 4: Log out and then log in as TPSAdmin (admin user)
    # ----------------------------------------------------------------------
    await limited_user_page.close()
    await logout()
    await login(username="TPSAdmin", password="TPSAdmin")  # adjust password as needed

    # ----------------------------------------------------------------------
    # STEP 5: Navigate to the same Profiler Configuration pages as admin
    # ----------------------------------------------------------------------
    admin_profiler_page = await open_new_page()

    # Navigate via UI
    await admin_profiler_page.goto(login_url, wait_until="networkidle")

    try:
        # Profiler main menu
        await admin_profiler_page.click(profiler_menu_selector, timeout=10_000)

        # Profiler Configuration
        await admin_profiler_page.click(profiler_config_menu_selector, timeout=10_000)

        # Settings
        await admin_profiler_page.click(settings_menu_selector, timeout=10_000)

        # Basic Configuration
        await admin_profiler_page.click(basic_config_menu_selector, timeout=10_000)

        # Wait for basic configuration page to load; check URL and key elements
        await admin_profiler_page.wait_for_load_state("networkidle")

    except Error as exc:
        pytest.fail(
            "Admin user 'TPSAdmin' should be able to navigate to Profiler "
            f"Configuration via UI, but navigation failed: {exc}"
        )

    # Assert URL indicates we are on Profiler Basic Configuration
    assert re.search(
        r"/profiler/.+basic", admin_profiler_page.url, re.IGNORECASE
    ), (
        "Admin user 'TPSAdmin' should be on Profiler Basic Configuration page, "
        f"but current URL is '{admin_profiler_page.url}'."
    )

    # Assert presence of a configuration form or controls
    # Replace selectors with actual configuration UI elements
    config_form_locator = admin_profiler_page.locator(
        "form#profilerBasicConfig, form[name='profilerBasicConfig']"
    )
    save_button_locator = admin_profiler_page.locator(
        "button:has-text('Save'), input[type='submit'][value*='Save']"
    )

    assert await config_form_locator.first.is_visible(), (
        "Profiler Basic Configuration form should be visible to admin user 'TPSAdmin'."
    )
    assert await save_button_locator.first.is_visible(), (
        "Save/Apply button should be visible on Profiler Basic Configuration page "
        "for admin user 'TPSAdmin'."
    )

    # (Optional) Try a non-destructive modification check: verify that controls
    # are enabled and editable, but do not actually submit changes.
    example_input_locator = admin_profiler_page.locator(
        "input[name*='profiler']", has_text=None
    ).first
    if await example_input_locator.is_visible():
        assert await example_input_locator.is_enabled(), (
            "Configuration inputs on Profiler Basic Configuration should be editable "
            "for admin user 'TPSAdmin'."
        )

    # ----------------------------------------------------------------------
    # Postconditions: Ensure we end in a logged-out state
    # ----------------------------------------------------------------------
    await admin_profiler_page.close()
    await logout()