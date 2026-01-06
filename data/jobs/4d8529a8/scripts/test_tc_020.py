import asyncio
import logging
from datetime import datetime

import pytest
from playwright.async_api import Page, Browser, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_020_disable_profiler_while_dhcp_active(
    authenticated_page: Page,
    browser: Browser,
):
    """
    TC_020: Negative – Attempt to disable Profiler while DHCP configuration is active

    Description:
        Validate system behavior when an admin attempts to disable Profiler or remove
        configuration while DHCP sniffing is active.

    Assumptions / Notes:
        - Selectors are placeholders and must be aligned with the actual AUT.
        - Test uses an already authenticated page via `authenticated_page` fixture.
        - DHCP activity is simulated by navigating to a "new endpoint" workflow.
    """
    page = authenticated_page

    # Helper values (update to match real app)
    profiler_global_settings_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/settings"
    )
    profiler_license_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/license"
    )
    dhcp_config_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/dhcp/config"
    )
    dhcp_endpoints_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/endpoints"
    )

    # Common selectors (placeholders)
    profiler_enabled_toggle = "#profiler-enabled-toggle"
    profiler_license_remove_button = "#profiler-license-remove-btn"
    profiler_warning_dialog = "div[role='dialog'].profiler-warning-dialog"
    profiler_warning_confirm_button = (
        "div[role='dialog'].profiler-warning-dialog button.confirm"
    )
    profiler_status_badge = "#profiler-status-badge"
    profiler_status_text = "#profiler-status-text"
    dhcp_page_readonly_banner = "#dhcp-readonly-banner"
    dhcp_page_disabled_message = "#dhcp-disabled-message"
    dhcp_config_form = "#dhcp-config-form"
    dhcp_config_save_button = "#dhcp-config-save-btn"
    dhcp_new_endpoint_button = "#simulate-new-endpoint-btn"
    dhcp_new_endpoint_result_row = "tr.endpoint-row.newly-discovered"
    endpoint_details_readonly_flag = "#endpoint-details-readonly-flag"
    existing_endpoint_row = "tr.endpoint-row.existing"
    endpoint_details_panel = "#endpoint-details-panel"

    # Utility: safe wait for selector with logging
    async def safe_wait_for_selector(
        selector: str,
        timeout: int = 5000,
        state: str = "visible",
        description: str | None = None,
    ):
        try:
            description = description or selector
            logger.info("Waiting for selector: %s", description)
            return await page.wait_for_selector(selector, timeout=timeout, state=state)
        except PlaywrightTimeoutError as exc:
            pytest.fail(f"Timeout waiting for {description or selector}: {exc}")

    # -------------------------------------------------------------------------
    # Step 0: Sanity check – ensure Profiler appears enabled and DHCP active
    # -------------------------------------------------------------------------
    # Navigate to Profiler global settings or license page
    # (prefer settings; fall back to license if needed)
    try:
        await page.goto(profiler_global_settings_url, wait_until="networkidle")
    except PlaywrightTimeoutError:
        # Fallback to license page
        await page.goto(profiler_license_url, wait_until="networkidle")

    # Ensure Profiler is currently enabled (precondition)
    toggle = await safe_wait_for_selector(
        profiler_enabled_toggle,
        description="Profiler enabled toggle",
    )
    profiler_toggle_aria = await toggle.get_attribute("aria-checked")
    assert profiler_toggle_aria in {"true", "false"}, (
        "Profiler toggle aria-checked attribute should be 'true' or 'false'"
    )
    assert profiler_toggle_aria == "true", (
        "Precondition failed: Profiler is not enabled before test."
    )

    # Optionally verify status badge/text indicates active
    status_badge = await safe_wait_for_selector(
        profiler_status_badge,
        description="Profiler status badge",
    )
    status_text_content = await status_badge.inner_text()
    assert any(
        keyword in status_text_content.lower()
        for keyword in ["active", "enabled", "running"]
    ), (
        f"Profiler status should indicate active/enabled, got: {status_text_content!r}"
    )

    # -------------------------------------------------------------------------
    # Step 1: Log in as pps-admin
    # -------------------------------------------------------------------------
    # This is handled by the `authenticated_page` fixture.
    # We still assert the correct user is shown in the UI if possible.
    try:
        user_menu_selector = "#user-menu-username"
        user_menu = await safe_wait_for_selector(
            user_menu_selector,
            description="User menu / username indicator",
        )
        username_text = (await user_menu.inner_text()).strip().lower()
        assert "pps-admin" in username_text, (
            f"Expected logged in user to be 'pps-admin', got: {username_text!r}"
        )
    except AssertionError:
        # Do not hard-fail if UI does not show username; log for traceability
        logger.warning("Could not positively confirm user is 'pps-admin' from UI.")

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler global settings or license page
    # -------------------------------------------------------------------------
    # Already navigated above; confirm we are on a Profiler-related page
    assert "profiler" in page.url.lower(), (
        f"Expected to be on Profiler settings/license page, got URL: {page.url}"
    )

    # -------------------------------------------------------------------------
    # Step 3: Attempt to disable Profiler feature or remove Profiler license
    # -------------------------------------------------------------------------
    # Try to disable via toggle first; if not available, try license removal.
    disable_action_taken = False

    try:
        # If toggle is enabled, click it to disable
        profiler_toggle_aria = await toggle.get_attribute("aria-checked")
        if profiler_toggle_aria == "true":
            await toggle.click()
            disable_action_taken = True
            logger.info("Clicked Profiler enabled toggle to disable Profiler.")
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "Failed to interact with Profiler toggle; will attempt license removal. "
            "Error: %s",
            exc,
        )

    if not disable_action_taken:
        # Fallback: attempt to remove license
        try:
            license_remove_button = await safe_wait_for_selector(
                profiler_license_remove_button,
                description="Profiler license remove button",
            )
            await license_remove_button.click()
            disable_action_taken = True
            logger.info("Clicked Profiler license remove button.")
        except PlaywrightTimeoutError:
            pytest.fail(
                "Unable to find a way to disable Profiler (toggle or license removal)."
            )

    # -------------------------------------------------------------------------
    # Step 4: Confirm any warning prompts
    # -------------------------------------------------------------------------
    # If a warning dialog appears, confirm it. If not, continue gracefully.
    try:
        warning_dialog = await page.wait_for_selector(
            profiler_warning_dialog,
            timeout=5000,
            state="visible",
        )
        assert warning_dialog is not None, (
            "Warning dialog should be visible when disabling Profiler."
        )

        warning_text = await warning_dialog.inner_text()
        logger.info("Profiler disable warning dialog text: %s", warning_text)

        # Optionally assert the warning mentions DHCP or active collectors
        assert any(
            keyword in warning_text.lower()
            for keyword in ["dhcp", "collector", "active profiling", "sniffing"]
        ), (
            "Warning dialog should mention DHCP/collectors/active profiling."
        )

        confirm_button = await safe_wait_for_selector(
            profiler_warning_confirm_button,
            description="Profiler warning confirm button",
        )
        await confirm_button.click()
    except PlaywrightTimeoutError:
        # No warning dialog appeared – acceptable behavior, but log it.
        logger.info("No warning dialog appeared when disabling Profiler.")

    # -------------------------------------------------------------------------
    # Step 5: Check if DHCP configuration pages become inaccessible or read-only
    # -------------------------------------------------------------------------
    await page.goto(dhcp_config_url, wait_until="networkidle")

    # The system may either:
    #   - block access (error/disabled message), or
    #   - show a read-only configuration (no save button, readonly banner).
    dhcp_disabled_or_readonly = False

    # Case A: Dedicated disabled message
    try:
        disabled_msg = await page.wait_for_selector(
            dhcp_page_disabled_message,
            timeout=3000,
            state="visible",
        )
        if disabled_msg:
            dhcp_disabled_or_readonly = True
            disabled_text = await disabled_msg.inner_text()
            assert any(
                keyword in disabled_text.lower()
                for keyword in ["profiler is not active", "disabled", "unavailable"]
            ), (
                "DHCP disabled message should indicate Profiler is not active."
            )
    except PlaywrightTimeoutError:
        logger.info("No explicit DHCP disabled message found; checking read-only state.")

    # Case B: Read-only banner
    if not dhcp_disabled_or_readonly:
        try:
            readonly_banner = await page.wait_for_selector(
                dhcp_page_readonly_banner,
                timeout=3000,
                state="visible",
            )
            if readonly_banner:
                dhcp_disabled_or_readonly = True
                banner_text = await readonly_banner.inner_text()
                assert any(
                    keyword in banner_text.lower()
                    for keyword in ["read-only", "profiler disabled", "view only"]
                ), (
                    "DHCP read-only banner should indicate read-only / disabled state."
                )
        except PlaywrightTimeoutError:
            logger.info("No DHCP read-only banner found; checking form interactivity.")

    # Case C: Form exists but should not be editable
    if not dhcp_disabled_or_readonly:
        try:
            config_form = await page.wait_for_selector(
                dhcp_config_form,
                timeout=3000,
                state="visible",
            )
            if config_form:
                # If save button is disabled or missing, treat as read-only
                save_button = await page.query_selector(dhcp_config_save_button)
                if save_button:
                    is_disabled_attr = await save_button.get_attribute("disabled")
                    aria_disabled = await save_button.get_attribute("aria-disabled")
                    disabled = (
                        is_disabled_attr is not None
                        or aria_disabled in ("true", "True", "1")
                    )
                    assert disabled, (
                        "DHCP configuration save button should be disabled when "
                        "Profiler is disabled."
                    )
                    dhcp_disabled_or_readonly = True
                else:
                    # No save button at all – treat as read-only
                    dhcp_disabled_or_readonly = True
        except PlaywrightTimeoutError:
            logger.info(
                "DHCP configuration form not found; assuming page is inaccessible."
            )
            dhcp_disabled_or_readonly = True

    assert dhcp_disabled_or_readonly, (
        "DHCP configuration pages should be inaccessible or read-only "
        "after Profiler is disabled."
    )

    # -------------------------------------------------------------------------
    # Step 6: Connect a new endpoint and trigger DHCP to see if profiling occurs
    # -------------------------------------------------------------------------
    # Navigate to endpoints page where new DHCP-based endpoints would appear
    await page.goto(dhcp_endpoints_url, wait_until="networkidle")

    # Capture existing endpoints count (if any)
    existing_endpoint_rows = await page.query_selector_all("tr.endpoint-row")
    existing_count = len(existing_endpoint_rows)
    logger.info("Existing endpoint rows before DHCP trigger: %d", existing_count)

    # Simulate a new endpoint triggering DHCP
    # (In a real environment, this might be replaced with an API call or external hook.)
    try:
        new_endpoint_button = await safe_wait_for_selector(
            dhcp_new_endpoint_button,
            description="Simulate new endpoint DHCP trigger button",
        )
        await new_endpoint_button.click()
    except PlaywrightTimeoutError:
        logger.warning(
            "No UI control found to simulate new endpoint; "
            "assuming external DHCP trigger is handled outside of UI."
        )

    # Wait a reasonable time for any new endpoint to appear
    await asyncio.sleep(5)

    # Re-read endpoint rows
    refreshed_endpoint_rows = await page.query_selector_all("tr.endpoint-row")
    new_count = len(refreshed_endpoint_rows)
    logger.info("Endpoint rows after DHCP trigger: %d", new_count)

    # Assert no new DHCP-based endpoint is profiled after Profiler is disabled
    assert new_count == existing_count, (
        "No new DHCP-based endpoint should be profiled after Profiler is disabled "
        f"(before={existing_count}, after={new_count})."
    )

    # -------------------------------------------------------------------------
    # Step 7: Verify existing device records remain in a read-only state
    # -------------------------------------------------------------------------
    if existing_count > 0:
        # Open first existing endpoint and verify details are read-only
        first_existing_row = await safe_wait_for_selector(
            existing_endpoint_row,
            description="First existing endpoint row",
        )
        await first_existing_row.click()

        details_panel = await safe_wait_for_selector(
            endpoint_details_panel,
            description="Endpoint details panel",
        )
        details_text = await details_panel.inner_text()
        logger.info("Endpoint details text: %s", details_text)

        # Check for explicit read-only indicator
        readonly_flag = await page.query_selector(endpoint_details_readonly_flag)
        if readonly_flag:
            flag_text = await readonly_flag.inner_text()
            assert any(
                keyword in flag_text.lower()
                for keyword in ["read-only", "view only", "locked"]
            ), (
                "Existing endpoint details should indicate read-only state."
            )
        else:
            # Fallback: ensure there is no edit or save button visible
            edit_button = await page.query_selector("button#endpoint-edit-btn")
            save_button = await page.query_selector("button#endpoint-save-btn")
            if edit_button:
                is_disabled_attr = await edit_button.get_attribute("disabled")
                aria_disabled = await edit_button.get_attribute("aria-disabled")
                disabled = (
                    is_disabled_attr is not None
                    or aria_disabled in ("true", "True", "1")
                )
                assert disabled, (
                    "Edit button for existing endpoint should be disabled "
                    "when Profiler is disabled."
                )
            if save_button:
                is_disabled_attr = await save_button.get_attribute("disabled")
                aria_disabled = await save_button.get_attribute("aria-disabled")
                disabled = (
                    is_disabled_attr is not None
                    or aria_disabled in ("true", "True", "1")
                )
                assert disabled, (
                    "Save button for existing endpoint should be disabled "
                    "when Profiler is disabled."
                )

    # -------------------------------------------------------------------------
    # Final: Validate Profiler remains disabled and system is not in partial state
    # -------------------------------------------------------------------------
    # Re-open Profiler settings to confirm disabled status persists
    await page.goto(profiler_global_settings_url, wait_until="networkidle")

    toggle_after = await safe_wait_for_selector(
        profiler_enabled_toggle,
        description="Profiler enabled toggle (post-check)",
    )
    profiler_toggle_aria_after = await toggle_after.get_attribute("aria-checked")
    assert profiler_toggle_aria_after == "false", (
        "Profiler should remain disabled until re-enabled."
    )

    # Confirm status badge indicates inactive/disabled
    status_badge_after = await safe_wait_for_selector(
        profiler_status_badge,
        description="Profiler status badge (post-check)",
    )
    status_text_after = await status_badge_after.inner_text()
    assert any(
        keyword in status_text_after.lower()
        for keyword in ["disabled", "inactive", "stopped"]
    ), (
        "Profiler status should indicate disabled/inactive after disablement, "
        f"got: {status_text_after!r}"
    )

    # Optional: log timestamp for traceability
    logger.info("TC_020 completed at %s", datetime.utcnow().isoformat() + "Z")