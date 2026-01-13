import asyncio
import logging
from typing import List

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_012_delete_profiler_with_active_dhcpv6_collector(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_012: Delete Profiler with active DHCPv6 collector enabled (negative)

    Objective:
        Validate system behavior when trying to delete Profiler while DHCPv6
        packet capturing is currently enabled and possibly running.

    Pre-conditions:
        - User is logged in as `ppsadmin` via authenticated_page fixture.
        - DHCPv6 packet capturing is expected to be enabled and active
          (from TC_005 or equivalent setup).

    Steps:
        1. Navigate to Basic Configuration page.
        2. Confirm `Enable DHCPv6 packet capturing` is checked.
        3. Click `Delete Profiler`.
        4. Confirm delete in dialog.
        5. Validate system behavior and postconditions.

    Expected Results:
        - System either:
            - Cleanly stops DHCPv6 collector and deletes Profiler configuration; or
            - Warns that DHCPv6 collector is active and asks for additional confirmation.
        - No orphaned DHCPv6 processes continue running (approximated via UI/logs).
        - No residual references to deleted Profiler remain in logs/status.
        - Profiler deleted; DHCPv6 collection stopped.
    """

    page = authenticated_page

    # Helper selectors – these are examples and should be adapted to real DOM
    basic_config_nav_selector = "a[href*='basic_config'], text=Basic Configuration"
    dhcpv6_checkbox_selector = "input#enable_dhcpv6_capture"
    delete_profiler_button_selector = "button#delete_profiler, text=Delete Profiler"
    confirm_dialog_selector = "div[role='dialog']"
    confirm_delete_button_selector = (
        f"{confirm_dialog_selector} button:has-text('Delete'), "
        f"{confirm_dialog_selector} button:has-text('OK')"
    )
    dhcpv6_warning_text_locator = page.locator(
        "text=DHCPv6 collector is active, text=DHCPv6 capture is currently running"
    )
    profiler_status_locator = page.locator(
        "text=Profiler Status, text=Profiler Configuration"
    )
    profiler_deleted_message_locator = page.locator(
        "text=Profiler deleted successfully, text=Profiler configuration removed"
    )
    dhcpv6_status_locator = page.locator(
        "text=DHCPv6 capture: Disabled, text=DHCPv6 collector: Stopped"
    )
    log_viewer_nav_selector = "a[href*='logs'], text=Logs"
    log_search_input_selector = "input#log_search"
    log_search_button_selector = "button#log_search_btn"
    log_results_locator = page.locator("div.log-entry")

    # ----------------------------------------------------------------------
    # Step 1: Navigate to Basic Configuration page
    # ----------------------------------------------------------------------
    try:
        await page.wait_for_load_state("domcontentloaded")
        await page.click(basic_config_nav_selector, timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Basic Configuration page: {exc}")

    # Ensure Basic Configuration page is loaded
    await page.wait_for_timeout(1000)
    assert await page.is_visible("text=Basic Configuration"), (
        "Basic Configuration page did not load as expected."
    )

    # ----------------------------------------------------------------------
    # Step 2: Confirm `Enable DHCPv6 packet capturing` is checked
    # ----------------------------------------------------------------------
    try:
        dhcpv6_checkbox = page.locator(dhcpv6_checkbox_selector)
        await dhcpv6_checkbox.wait_for(state="visible", timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(f"DHCPv6 packet capturing checkbox not found: {exc}")

    is_checked = await dhcpv6_checkbox.is_checked()
    assert is_checked, (
        "Precondition failed: 'Enable DHCPv6 packet capturing' is not checked. "
        "This test requires an active DHCPv6 collector."
    )

    # ----------------------------------------------------------------------
    # Step 3: Click `Delete Profiler`
    # ----------------------------------------------------------------------
    try:
        await page.click(delete_profiler_button_selector, timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click 'Delete Profiler' button: {exc}")

    # ----------------------------------------------------------------------
    # Step 4: Confirm delete in dialog
    # ----------------------------------------------------------------------
    try:
        await page.locator(confirm_dialog_selector).wait_for(
            state="visible", timeout=10_000
        )
    except PlaywrightError as exc:
        pytest.fail(f"Confirmation dialog did not appear after delete click: {exc}")

    # Optional: If additional warning appears about active DHCPv6 collector,
    # assert its presence (one of the expected behaviors).
    warning_present = False
    try:
        warning_present = await dhcpv6_warning_text_locator.first.is_visible()
    except PlaywrightError:
        # If locator fails, treat as no warning; behavior is still acceptable
        warning_present = False

    # Confirmation dialog must be confirmed regardless of warning presence
    try:
        await page.click(confirm_delete_button_selector, timeout=10_000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to confirm Profiler deletion in dialog: {exc}")

    # Allow backend to process deletion
    await page.wait_for_load_state("networkidle")
    await page.wait_for_timeout(2000)

    # ----------------------------------------------------------------------
    # Expected Result 1:
    #   - Either warning about active collector was shown OR
    #   - Profiler is deleted cleanly without warning.
    # We already captured `warning_present`; now we assert that at least
    # one of the expected end states is true.
    # ----------------------------------------------------------------------
    logger.info("DHCPv6 active warning present: %s", warning_present)

    # We do not fail if warning was not shown; both flows are acceptable.
    # Instead, we assert the postconditions (Profiler deleted, collector stopped).

    # ----------------------------------------------------------------------
    # Expected Result 2: Profiler deleted; DHCPv6 collection stopped
    # ----------------------------------------------------------------------
    # Refresh the page to ensure latest state
    await page.reload(wait_until="networkidle")

    # Check for explicit success / deletion message if UI provides it
    profiler_deleted_message_visible = False
    try:
        profiler_deleted_message_visible = await profiler_deleted_message_locator.first.is_visible()
    except PlaywrightError:
        profiler_deleted_message_visible = False

    # Profiler status section should not show active/provisioned profiler
    profiler_status_visible = await profiler_status_locator.first.is_visible()
    if profiler_status_visible:
        # If the Profiler status block exists, it should indicate removed/disabled
        profiler_status_text = (await profiler_status_locator.first.inner_text()).lower()
        assert "deleted" in profiler_status_text or "not configured" in profiler_status_text, (
            "Profiler status still indicates an active or configured Profiler "
            "after deletion attempt."
        )

    # Assert that either we saw an explicit success message or that the
    # Profiler status no longer indicates an active profiler.
    assert profiler_deleted_message_visible or not profiler_status_visible, (
        "Profiler deletion was not confirmed by the UI and Profiler status "
        "still appears present."
    )

    # DHCPv6 collection should be stopped/disabled after Profiler deletion
    dhcpv6_status_visible = False
    try:
        dhcpv6_status_visible = await dhcpv6_status_locator.first.is_visible()
    except PlaywrightError:
        dhcpv6_status_visible = False

    assert dhcpv6_status_visible, (
        "DHCPv6 status indicator not visible; cannot verify that DHCPv6 "
        "collector has stopped."
    )
    dhcpv6_status_text = (await dhcpv6_status_locator.first.inner_text()).lower()
    assert "disabled" in dhcpv6_status_text or "stopped" in dhcpv6_status_text, (
        "DHCPv6 collector does not appear to be stopped after Profiler deletion. "
        f"Status text: {dhcpv6_status_text!r}"
    )

    # ----------------------------------------------------------------------
    # Expected Result 3: No orphaned DHCPv6 processes / residual references
    # ----------------------------------------------------------------------
    # NOTE: From a UI test we cannot inspect OS-level processes, but we can
    # approximate this by checking logs/status for residual references.
    # This section should be adapted to the actual log viewer implementation.
    # ----------------------------------------------------------------------
    try:
        # Navigate to logs / status page
        await page.click(log_viewer_nav_selector, timeout=10_000)
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        # If log viewer is not available, log and continue with a soft assertion.
        logger.warning("Could not navigate to log viewer to check for residual "
                       "references to Profiler: %s", exc)
        # We don't fail the test solely for missing log viewer.
        return

    # Search logs for references that would indicate an active Profiler/DHCPv6
    # process after deletion. Adjust search terms as appropriate.
    suspicious_terms: List[str] = [
        "DHCPv6 collector started",
        "DHCPv6 capture running",
        "Profiler active",
        "Profiler started",
    ]

    try:
        for term in suspicious_terms:
            if not await page.is_visible(log_search_input_selector):
                break

            await page.fill(log_search_input_selector, term)
            await page.click(log_search_button_selector, timeout=5_000)
            await page.wait_for_timeout(1500)

            # Collect a small set of log entries and inspect their timestamps/text
            log_entries = await log_results_locator.all_inner_texts()
            recent_entries = [e for e in log_entries if term in e]

            # We allow historical entries, but there should be no entries
            # AFTER the deletion timestamp indicating that the collector is still active.
            # Since we do not have timestamps here, we assert more weakly:
            # no *new* "started/running" entries should appear immediately
            # after deletion when searching.
            assert not recent_entries, (
                "Residual log entries suggest DHCPv6 collector or Profiler is "
                f"still active after deletion (term found: {term!r}). Entries: {recent_entries}"
            )

    except PlaywrightError as exc:
        logger.warning(
            "Error while inspecting logs for residual Profiler/DHCPv6 references: %s",
            exc,
        )
        # Do not fail the test purely on log viewer issues
        # because the primary functional behavior is already verified above.
        return

    # Final short wait to ensure no late UI errors appear
    await asyncio.sleep(1)