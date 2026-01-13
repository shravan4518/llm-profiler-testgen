import asyncio
import logging
from contextlib import suppress

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_enable_dhcpv6_packet_capturing_and_sniffing_over_external_port(
    authenticated_page: Page,
    browser,
):
    """
    TC_005: Enable DHCPv6 packet capturing and sniffing over external port

    Validate that both DHCPv6 collector options can be enabled from Basic
    Configuration and that the system reflects the activation state.

    Steps:
        1. Log in as `ppsadmin` (handled by `authenticated_page` fixture).
        2. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
        3. Check both:
            - Enable DHCPv6 packet capturing
            - Enable DHCPv6 sniffing over external port
        4. Click "Save Changes".
        5. Open Profiler logs or status page showing collector status (if available).
        6. Confirm DHCPv6 collector is running and bound to external port (if possible).

    Expected:
        - Settings saved successfully with no errors.
        - Both checkboxes remain checked after saving and page reload.
        - Profiler status/logs reflect DHCPv6 collector active and external
          port sniffing enabled (if such view is available).
    """
    page = authenticated_page

    # Locators – these are best guesses and should be adjusted to match actual DOM
    # Navigation menu / breadcrumbs
    profiler_menu = page.get_by_role("link", name="Profiler")
    profiler_config_menu = page.get_by_role(
        "link", name="Profiler Configuration"
    )
    settings_menu = page.get_by_role("link", name="Settings")
    basic_config_link = page.get_by_role(
        "link", name="Basic Configuration"
    )

    # Checkboxes
    dhcpv6_capture_checkbox = page.get_by_label(
        "Enable DHCPv6 packet capturing"
    )
    dhcpv6_sniffing_checkbox = page.get_by_label(
        "Enable DHCPv6 sniffing over external port"
    )

    # Save button
    save_changes_button = page.get_by_role("button", name="Save Changes")

    # Potential status/log links (best-effort, may need adjustment)
    status_menu = page.get_by_role("link", name="Status")
    profiler_status_link = page.get_by_role(
        "link", name="Profiler Status"
    )
    logs_link = page.get_by_role("link", name="Logs")

    # Potential status indicators (text-based, since we do not know exact DOM)
    dhcpv6_status_text = page.get_by_text(
        "DHCPv6 collector", exact=False
    )

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # -------------------------------------------------------------------------
    try:
        await profiler_menu.click()
        await profiler_config_menu.click()
        await settings_menu.click()
        await basic_config_link.click()
    except PlaywrightError as exc:
        logger.error("Navigation to Basic Configuration failed: %s", exc)
        pytest.fail("Failed to navigate to Basic Configuration page")

    # Wait for Basic Configuration content to be visible
    with suppress(PlaywrightError):
        await page.wait_for_load_state("networkidle")
    await asyncio.sleep(1)

    # Basic sanity check: ensure we are on the expected page
    with suppress(PlaywrightError):
        assert "Basic Configuration" in (await page.title())

    # -------------------------------------------------------------------------
    # Step 3: Check both DHCPv6-related checkboxes
    # -------------------------------------------------------------------------
    try:
        await dhcpv6_capture_checkbox.wait_for(state="visible", timeout=5000)
        await dhcpv6_sniffing_checkbox.wait_for(state="visible", timeout=5000)
    except PlaywrightError as exc:
        logger.error("DHCPv6 configuration options not found: %s", exc)
        pytest.fail("DHCPv6 configuration options are not present on the page")

    # Ensure both checkboxes are checked
    async def ensure_checked(checkbox, name: str) -> None:
        try:
            is_checked = await checkbox.is_checked()
            if not is_checked:
                await checkbox.check()
            assert await checkbox.is_checked(), (
                f"{name} checkbox could not be checked"
            )
        except PlaywrightError as exc:
            logger.error("Error interacting with %s checkbox: %s", name, exc)
            pytest.fail(f"Failed to set '{name}' checkbox")

    await ensure_checked(
        dhcpv6_capture_checkbox, "Enable DHCPv6 packet capturing"
    )
    await ensure_checked(
        dhcpv6_sniffing_checkbox,
        "Enable DHCPv6 sniffing over external port",
    )

    # -------------------------------------------------------------------------
    # Step 4: Click "Save Changes"
    # -------------------------------------------------------------------------
    try:
        await save_changes_button.click()
    except PlaywrightError as exc:
        logger.error("Failed to click 'Save Changes': %s", exc)
        pytest.fail("Could not click 'Save Changes' button")

    # Wait for potential success notification or page reload
    with suppress(PlaywrightError):
        # Adjust selector if the app uses a specific success message element
        await page.wait_for_timeout(2000)

    # Basic assertion: no generic error message is visible
    # (Adjust text/selectors to match the real application)
    error_indicators = [
        page.get_by_text("Error", exact=False),
        page.get_by_text("failed", exact=False),
    ]
    for error_indicator in error_indicators:
        with suppress(PlaywrightError):
            assert not await error_indicator.is_visible(), (
                "An error message appeared after saving configuration"
            )

    # -------------------------------------------------------------------------
    # Step 5–6: Reload and verify that settings persisted
    # -------------------------------------------------------------------------
    try:
        await page.reload()
        await dhcpv6_capture_checkbox.wait_for(state="visible", timeout=5000)
        await dhcpv6_sniffing_checkbox.wait_for(state="visible", timeout=5000)
    except PlaywrightError as exc:
        logger.error("Failed to reload or locate DHCPv6 checkboxes: %s", exc)
        pytest.fail("Page reload or checkbox lookup failed")

    assert await dhcpv6_capture_checkbox.is_checked(), (
        "DHCPv6 packet capturing checkbox is not checked after saving/reload"
    )
    assert await dhcpv6_sniffing_checkbox.is_checked(), (
        "DHCPv6 sniffing over external port checkbox is not checked "
        "after saving/reload"
    )

    # -------------------------------------------------------------------------
    # Step 5–6 (extended): Navigate to status/logs and verify collector state
    # This is best-effort, as we do not know the exact UI. The assertions are
    # written to be soft/optional where necessary.
    # -------------------------------------------------------------------------
    status_verification_performed = False
    try:
        # Attempt to reach a status or logs page where DHCPv6 collector state
        # might be visible.
        await profiler_menu.click()
        with suppress(PlaywrightError):
            await status_menu.click()
        with suppress(PlaywrightError):
            await profiler_status_link.click()
        with suppress(PlaywrightError):
            await logs_link.click()

        with suppress(PlaywrightError):
            await page.wait_for_load_state("networkidle")

        # Check for any text that indicates DHCPv6 collector is active
        # Adjust these substrings to match actual system messages.
        candidate_texts = [
            "DHCPv6 collector: running",
            "DHCPv6 collector running",
            "DHCPv6: active",
            "DHCPv6 collector active",
            "DHCPv6 sniffing over external port: enabled",
        ]

        status_text_found = False
        for text in candidate_texts:
            locator = page.get_by_text(text, exact=False)
            with suppress(PlaywrightError):
                if await locator.is_visible():
                    status_text_found = True
                    break

        # If we could inspect status, assert that some indication exists
        status_verification_performed = True
        assert status_text_found, (
            "Could not find any indication in status/logs that DHCPv6 "
            "collector and external port sniffing are active. "
            "Verify or adjust status page selectors/text."
        )
    except PlaywrightError as exc:
        # Do not fail hard if status/logs view is not implemented; log instead.
        logger.warning(
            "Status/logs verification for DHCPv6 collector could not be "
            "completed: %s",
            exc,
        )

    # If we did not manage to verify via status/logs, at least log that fact
    if not status_verification_performed:
        logger.info(
            "DHCPv6 collector status/log verification was not performed; "
            "only configuration persistence was validated."
        )