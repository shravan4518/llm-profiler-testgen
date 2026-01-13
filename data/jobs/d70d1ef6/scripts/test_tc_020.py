import asyncio
import re
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error, TimeoutError


@pytest.mark.asyncio
async def test_profiler_access_restricted_to_admin_users(
    browser: Browser,
    authenticated_page,
) -> None:
    """
    TC_020: Profiler access restricted to authenticated admin users

    Validates that:
      - Unauthenticated users are redirected to login when accessing Profiler Configuration.
      - Non-admin user `helpdesk1` cannot access Profiler Configuration (no menu or access denied).
      - Admin user `ppsadmin` can access Profiler Configuration.

    Assumptions:
      - `authenticated_page` is a fixture that can return an authenticated Page
        for a given username/password, e.g.:
            page = await authenticated_page(username="ppsadmin", password="...")
      - Base URL and login mechanism are configured in the fixtures/environment.
    """
    base_profiler_url = (
        "https://10.34.50.201/dana-na/auth/url_admin/profiler/configuration.cgi"
    )
    login_page_url_pattern = re.compile(r".*/dana-na/auth/url_.*?/login.*", re.IGNORECASE)

    # Helper: safely close page if still open
    async def safe_close_page(page: Optional[Page]) -> None:
        if page and not page.is_closed():
            try:
                await page.close()
            except Error:
                # Ignore close errors to avoid masking test failures
                pass

    # ----------------------------------------------------------------------
    # Step 1: Without login, attempt to access direct URL to Profiler Configuration
    # ----------------------------------------------------------------------
    unauthenticated_context = await browser.new_context(ignore_https_errors=True)
    unauthenticated_page = await unauthenticated_context.new_page()

    try:
        await unauthenticated_page.goto(base_profiler_url, wait_until="domcontentloaded")

        # ------------------------------------------------------------------
        # Step 2: Verify redirection to login page
        # ------------------------------------------------------------------
        current_url = unauthenticated_page.url

        # Assert that we did not land directly on profiler config when unauthenticated
        assert "profiler" not in current_url.lower(), (
            "Unauthenticated user should not land directly on Profiler Configuration page."
        )

        # Assert that the user is redirected to a login page
        assert re.match(login_page_url_pattern, current_url), (
            f"Unauthenticated access should be redirected to login page, "
            f"but current URL is: {current_url}"
        )

        # Optional: Check for login form elements as an additional safety net
        login_form_present = await unauthenticated_page.locator("form").count()
        assert login_form_present > 0, (
            "Login form should be present after redirect from unauthenticated access."
        )
    finally:
        await safe_close_page(unauthenticated_page)
        await unauthenticated_context.close()

    # ----------------------------------------------------------------------
    # Step 3: Log in as `helpdesk1` (limited role, no Profiler rights)
    # ----------------------------------------------------------------------
    # NOTE: Adjust password retrieval to your environment (env var, vault, etc.)
    helpdesk_username = "helpdesk1"
    helpdesk_password = "helpdesk1_password"  # placeholder

    helpdesk_page: Page = await authenticated_page(
        username=helpdesk_username,
        password=helpdesk_password,
    )

    try:
        # ------------------------------------------------------------------
        # Step 4: Attempt to navigate to Profiler > Profiler Configuration
        # ------------------------------------------------------------------
        # First, verify if the Profiler menu item is visible in the UI.
        profiler_menu_locator = helpdesk_page.locator("text=Profiler")
        profiler_config_locator = helpdesk_page.locator(
            "text=Profiler Configuration"
        )

        profiler_menu_visible = await profiler_menu_locator.is_visible()
        profiler_config_visible = await profiler_config_locator.is_visible()

        # ------------------------------------------------------------------
        # Step 5: Record access behavior or error
        # ------------------------------------------------------------------
        # Case A: Profiler menu or configuration item is visible (unexpected for limited user)
        if profiler_menu_visible or profiler_config_visible:
            # Try to click through and assert access is denied
            try:
                if profiler_menu_visible:
                    await profiler_menu_locator.click()
                if profiler_config_visible:
                    await profiler_config_locator.click()
                else:
                    # Direct navigation as fallback if config link not clickable
                    await helpdesk_page.goto(
                        base_profiler_url, wait_until="domcontentloaded"
                    )
            except (Error, TimeoutError):
                # Any navigation error here is acceptable as "access denied"
                pass

            # Look for typical authorization error indicators
            access_denied_texts = [
                "access denied",
                "not authorized",
                "insufficient privileges",
                "permission denied",
            ]
            page_content = (await helpdesk_page.text_content("body")) or ""
            page_content_lower = page_content.lower()

            has_denied_message = any(
                msg in page_content_lower for msg in access_denied_texts
            )

            # Assert that the user does NOT see a functional Profiler configuration page
            assert has_denied_message or "profiler configuration" not in page_content_lower, (  # noqa: E501
                "helpdesk1 should not have access to Profiler Configuration; "
                "expected an authorization error or no configuration content."
            )

        # Case B: Profiler menu item is completely hidden (expected/acceptable)
        else:
            # As a defense-in-depth check, direct URL access should still be denied
            await helpdesk_page.goto(base_profiler_url, wait_until="domcontentloaded")
            current_url = helpdesk_page.url

            # We should not successfully land on the profiler configuration
            assert "profiler" not in current_url.lower() or re.match(
                login_page_url_pattern, current_url
            ), (
                "helpdesk1 should not be able to directly access Profiler Configuration "
                f"via URL. Current URL: {current_url}"
            )

            page_content = (await helpdesk_page.text_content("body")) or ""
            page_content_lower = page_content.lower()

            access_denied_texts = [
                "access denied",
                "not authorized",
                "insufficient privileges",
                "permission denied",
            ]
            has_denied_message = any(
                msg in page_content_lower for msg in access_denied_texts
            )

            assert has_denied_message or re.match(
                login_page_url_pattern, current_url
            ), (
                "helpdesk1 should be either redirected or see an authorization error "
                "when accessing Profiler Configuration directly."
            )

        # ------------------------------------------------------------------
        # Step 6: Log out `helpdesk1`
        # ------------------------------------------------------------------
        # Attempt a generic logout; adjust selectors to your actual app.
        try:
            # Common patterns: a logout link or button
            logout_locator = helpdesk_page.locator(
                "text=/logout|sign out|log off/i"
            )
            if await logout_locator.is_visible():
                await logout_locator.click()
            else:
                # Fallback: direct logout URL if available
                await helpdesk_page.goto(
                    "https://10.34.50.201/dana-na/auth/logout.cgi",
                    wait_until="domcontentloaded",
                )
        except Error:
            # If logout fails, we still proceed but note that no unauthorized sessions
            # should remain due to context isolation per fixture.
            pass

    finally:
        await safe_close_page(helpdesk_page)

    # ----------------------------------------------------------------------
    # Step 7: Log in as `ppsadmin` and access Profiler Configuration
    # ----------------------------------------------------------------------
    admin_username = "ppsadmin"
    admin_password = "ppsadmin_password"  # placeholder

    admin_page: Page = await authenticated_page(
        username=admin_username,
        password=admin_password,
    )

    try:
        # Navigate through UI if possible
        profiler_menu_locator = admin_page.locator("text=Profiler")
        profiler_config_locator = admin_page.locator("text=Profiler Configuration")

        # Try UI navigation first
        if await profiler_menu_locator.is_visible():
            await profiler_menu_locator.click()
        if await profiler_config_locator.is_visible():
            await profiler_config_locator.click()
        else:
            # Fallback to direct URL if menu item not found
            await admin_page.goto(base_profiler_url, wait_until="domcontentloaded")

        # ------------------------------------------------------------------
        # Expected: `ppsadmin` can access full Profiler Configuration
        # ------------------------------------------------------------------
        # Assert URL indicates profiler configuration
        current_url = admin_page.url
        assert "profiler" in current_url.lower(), (
            "Admin user should reach Profiler Configuration page. "
            f"Current URL: {current_url}"
        )

        # Assert that some expected UI elements for configuration are present
        # (selectors are placeholders; adjust to actual DOM)
        config_header_locator = admin_page.locator(
            "h1:has-text('Profiler Configuration'), "
            "h2:has-text('Profiler Configuration')"
        )
        assert await config_header_locator.first.is_visible(), (
            "Profiler Configuration header should be visible for admin user."
        )

        # Ensure there is no authorization error on the page
        page_content = (await admin_page.text_content("body")) or ""
        page_content_lower = page_content.lower()
        for denied_phrase in [
            "access denied",
            "not authorized",
            "insufficient privileges",
            "permission denied",
        ]:
            assert denied_phrase not in page_content_lower, (
                "Admin user should not see authorization errors on Profiler "
                "Configuration page."
            )

    finally:
        # Postconditions: ensure no unauthorized sessions remain
        # Attempt to log out admin as well
        try:
            logout_locator = admin_page.locator(
                "text=/logout|sign out|log off/i"
            )
            if await logout_locator.is_visible():
                await logout_locator.click()
            else:
                await admin_page.goto(
                    "https://10.34.50.201/dana-na/auth/logout.cgi",
                    wait_until="domcontentloaded",
                )
        except Error:
            pass
        await safe_close_page(admin_page)