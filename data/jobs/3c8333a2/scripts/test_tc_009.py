import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
async def test_tc_009_dhcpv6_collector_requires_license(authenticated_page: Page, browser) -> None:
    """
    TC_009: Attempt to enable DHCPv6 collector without appropriate license

    Title:
        Attempt to enable DHCPv6 collector without appropriate license

    Category:
        Negative

    Priority:
        Critical

    Description:
        Validate behavior when attempting to enable “Enable DHCPv6 packet capturing”
        without having the required Profiler license that supports this feature.

    Preconditions (provided by fixtures / environment):
        - System installed without the DHCPv6-capable Profiler license.
        - Admin is already logged in (authenticated_page fixture).

    Expected Results:
        - Either the checkboxes are disabled/greyed out with tooltip
          “Requires DHCPv6 license”, OR
        - Save fails with an error message indicating missing license for
          DHCPv6 functionality.
        - Feature is not enabled in backend.
        - DHCPv6 collector remains disabled. License status unchanged.
    """
    page: Page = authenticated_page

    # Locators (update selectors as needed for the real UI)
    profiler_menu = page.locator("text=Profiler")
    profiler_config_menu = page.locator("text=Profiler Configuration")
    settings_menu = page.locator("text=Settings")
    basic_config_menu = page.locator("text=Basic Configuration")

    dhcpv6_capture_checkbox = page.locator(
        'input[type="checkbox"][name="enable_dhcpv6_capture"]'
    )
    dhcpv6_sniffing_checkbox = page.locator(
        'input[type="checkbox"][name="enable_dhcpv6_sniffing_external"]'
    )
    save_changes_button = page.locator('button:has-text("Save Changes"), input[type="submit"][value="Save Changes"]')

    # Possible error message locators (try multiple patterns)
    error_message_locator = page.locator(
        "text=/missing.*dhcpv6.*license/i, "
        "text=/requires.*dhcpv6.*license/i, "
        "text=/license.*not.*available.*dhcpv6/i"
    )

    # Generic status / toast area (if applicable)
    notification_area = page.locator(
        ".alert-danger, .alert-error, .toast-error, .message-error"
    )

    async def get_tooltip_text(element_locator) -> Optional[str]:
        """Try to read a tooltip text from title attribute or aria-label."""
        try:
            title_attr = await element_locator.get_attribute("title")
            if title_attr:
                return title_attr.strip()
            aria_label = await element_locator.get_attribute("aria-label")
            if aria_label:
                return aria_label.strip()
        except PlaywrightError:
            # If the element goes stale or is not attached, ignore and return None
            return None
        return None

    # -------------------------------------------------------------------------
    # Step 1: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # -------------------------------------------------------------------------
    try:
        await profiler_menu.click()
        await profiler_config_menu.click()
        await settings_menu.click()
        await basic_config_menu.click()
    except PlaywrightError as exc:
        pytest.fail(f"Navigation to Basic Configuration failed: {exc}")

    # Wait for the basic configuration page to be fully loaded
    # This selector should be adjusted to something unique on the Basic Configuration page.
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(500)  # small stabilization delay

    # -------------------------------------------------------------------------
    # Step 2 & 3: Attempt to check DHCPv6-related checkboxes
    # -------------------------------------------------------------------------
    # We must handle both UX possibilities:
    #   A) Checkboxes are disabled/greyed out with tooltip
    #   B) Checkboxes are enabled but saving fails due to license restriction

    # Ensure checkboxes exist
    try:
        await dhcpv6_capture_checkbox.wait_for(state="attached", timeout=5000)
        await dhcpv6_sniffing_checkbox.wait_for(state="attached", timeout=5000)
    except PlaywrightTimeoutError:
        pytest.fail("DHCPv6 checkbox elements were not found on Basic Configuration page.")

    # Determine if the checkboxes are disabled
    capture_disabled = await dhcpv6_capture_checkbox.is_disabled()
    sniffing_disabled = await dhcpv6_sniffing_checkbox.is_disabled()

    tooltip_capture = await get_tooltip_text(dhcpv6_capture_checkbox)
    tooltip_sniffing = await get_tooltip_text(dhcpv6_sniffing_checkbox)

    # Flag to know which path we are in
    license_enforced_by_disabled_ui = False
    license_enforced_by_save_error = False

    # Case A: Checkboxes disabled with tooltip
    if capture_disabled and sniffing_disabled:
        license_enforced_by_disabled_ui = True

        # Assert tooltip text if available
        if tooltip_capture:
            assert "requires dhcpv6 license" in tooltip_capture.lower(), (
                "Unexpected tooltip on DHCPv6 capture checkbox: "
                f"'{tooltip_capture}'. Expected indication of license requirement."
            )
        if tooltip_sniffing:
            assert "requires dhcpv6 license" in tooltip_sniffing.lower(), (
                "Unexpected tooltip on DHCPv6 sniffing checkbox: "
                f"'{tooltip_sniffing}'. Expected indication of license requirement."
            )

        # Since checkboxes are disabled, we should verify they are not checked
        assert not await dhcpv6_capture_checkbox.is_checked(), (
            "DHCPv6 packet capturing checkbox should not be checked when disabled."
        )
        assert not await dhcpv6_sniffing_checkbox.is_checked(), (
            "DHCPv6 sniffing external port checkbox should not be checked when disabled."
        )

        # Attempting to click should not change their state
        try:
            await dhcpv6_capture_checkbox.click()
            await dhcpv6_sniffing_checkbox.click()
        except PlaywrightError:
            # Some UIs may prevent clicking disabled elements; this is acceptable.
            pass

        assert not await dhcpv6_capture_checkbox.is_checked(), (
            "DHCPv6 packet capturing checkbox should remain unchecked after click attempt."
        )
        assert not await dhcpv6_sniffing_checkbox.is_checked(), (
            "DHCPv6 sniffing external port checkbox should remain unchecked after click attempt."
        )

    else:
        # Case B: Checkboxes appear enabled; attempt to enable them and rely on Save failure
        # Step 2: Attempt to check “Enable DHCPv6 packet capturing”.
        try:
            if not await dhcpv6_capture_checkbox.is_checked():
                await dhcpv6_capture_checkbox.check()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to interact with DHCPv6 packet capturing checkbox: {exc}")

        # Step 3: Attempt to check “Enable DHCPv6 sniffing over external port”.
        try:
            if not await dhcpv6_sniffing_checkbox.is_checked():
                await dhcpv6_sniffing_checkbox.check()
        except PlaywrightError as exc:
            pytest.fail(f"Failed to interact with DHCPv6 sniffing checkbox: {exc}")

        # Basic sanity: both boxes should show as checked in UI now
        assert await dhcpv6_capture_checkbox.is_checked(), (
            "DHCPv6 packet capturing checkbox should be checked after user action."
        )
        assert await dhcpv6_sniffing_checkbox.is_checked(), (
            "DHCPv6 sniffing external port checkbox should be checked after user action."
        )

    # -------------------------------------------------------------------------
    # Step 4: Click "Save Changes"
    # -------------------------------------------------------------------------
    try:
        await save_changes_button.wait_for(state="visible", timeout=5000)
    except PlaywrightTimeoutError:
        pytest.fail('"Save Changes" button not found on Basic Configuration page.')

    try:
        await save_changes_button.click()
    except PlaywrightError as exc:
        pytest.fail(f'Failed to click "Save Changes" button: {exc}')

    # Wait for any network operations / UI updates
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(1000)

    # -------------------------------------------------------------------------
    # Expected behavior assertions
    # -------------------------------------------------------------------------

    # If the UI already enforced license via disabled checkboxes, we still must
    # ensure that saving did not silently enable anything in the backend.
    # If checkboxes were enabled, we expect a license-related error message.

    # Try to detect a visible error message about missing license
    license_error_detected = False

    try:
        await error_message_locator.first.wait_for(state="visible", timeout=3000)
        license_error_text = await error_message_locator.first.inner_text()
        if "license" in license_error_text.lower() and "dhcpv6" in license_error_text.lower():
            license_error_detected = True
    except PlaywrightTimeoutError:
        # No specific error in the dedicated error locator; try notification area
        try:
            await notification_area.first.wait_for(state="visible", timeout=2000)
            notification_text = await notification_area.first.inner_text()
            if "license" in notification_text.lower() and "dhcpv6" in notification_text.lower():
                license_error_detected = True
        except PlaywrightTimeoutError:
            # No visible notification either; this is acceptable only if the UI
            # enforced license via disabled checkboxes.
            pass

    # At least one enforcement mechanism must be present
    assert license_enforced_by_disabled_ui or license_error_detected, (
        "Neither disabled UI nor a clear license-related error message was detected "
        "when attempting to enable DHCPv6 features without the appropriate license."
    )

    # -------------------------------------------------------------------------
    # Postconditions: DHCPv6 collector remains disabled
    # -------------------------------------------------------------------------
    # Reload the page to ensure backend state is reflected
    try:
        await page.reload()
        await page.wait_for_load_state("networkidle")
        await page.wait_for_timeout(500)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reload page for postcondition verification: {exc}")

    # Re-locate checkboxes after reload (DOM may have changed)
    dhcpv6_capture_checkbox_reloaded = page.locator(
        'input[type="checkbox"][name="enable_dhcpv6_capture"]'
    )
    dhcpv6_sniffing_checkbox_reloaded = page.locator(
        'input[type="checkbox"][name="enable_dhcpv6_sniffing_external"]'
    )

    try:
        await dhcpv6_capture_checkbox_reloaded.wait_for(state="attached", timeout=5000)
        await dhcpv6_sniffing_checkbox_reloaded.wait_for(state="attached", timeout=5000)
    except PlaywrightTimeoutError:
        pytest.fail(
            "DHCPv6 checkbox elements not found after reload; "
            "cannot verify that the feature remains disabled."
        )

    # Assert that backend did not enable the feature
    assert not await dhcpv6_capture_checkbox_reloaded.is_checked(), (
        "DHCPv6 packet capturing appears enabled after save, "
        "but it should remain disabled without the appropriate license."
    )
    assert not await dhcpv6_sniffing_checkbox_reloaded.is_checked(), (
        "DHCPv6 sniffing over external port appears enabled after save, "
        "but it should remain disabled without the appropriate license."
    )

    # Optional: verify that checkboxes are still disabled (if that is the chosen UX)
    # This is not strictly required by the test, but is a useful sanity check.
    capture_disabled_after = await dhcpv6_capture_checkbox_reloaded.is_disabled()
    sniffing_disabled_after = await dhcpv6_sniffing_checkbox_reloaded.is_disabled()
    if capture_disabled_after and sniffing_disabled_after:
        tooltip_capture_after = await get_tooltip_text(dhcpv6_capture_checkbox_reloaded)
        tooltip_sniffing_after = await get_tooltip_text(dhcpv6_sniffing_checkbox_reloaded)

        if tooltip_capture_after:
            assert "requires dhcpv6 license" in tooltip_capture_after.lower(), (
                "After reload, DHCPv6 capture tooltip no longer indicates license requirement."
            )
        if tooltip_sniffing_after:
            assert "requires dhcpv6 license" in tooltip_sniffing_after.lower(), (
                "After reload, DHCPv6 sniffing tooltip no longer indicates license requirement."
            )