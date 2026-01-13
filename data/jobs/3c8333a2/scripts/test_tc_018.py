import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.integration
@pytest.mark.asyncio
async def test_tc_018_ldap_additional_collector_enriches_endpoint_attributes(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_018: Integration – Additional LDAP collector populates endpoint attributes.

    Validates that an additional LDAP data collector successfully queries LDAP and
    enriches endpoint records with owner and department attributes for endpoint
    `Client1`.

    Prerequisites:
    - LDAP server `ldap.acme.com` configured as additional data collector.
    - Endpoint MAC or hostname present in LDAP directory with metadata.

    Expected:
    - Profiler maps LDAP directory attributes onto endpoint record.
    - Owner and department fields for `Client1` are populated with
      `USER001` and `Finance`.
    """
    page: Page = authenticated_page

    # Helper: wait for a locator to contain non-empty text with timeout
    async def wait_for_non_empty_text(
        locator_str: str,
        timeout_ms: int = 15000,
    ) -> str:
        locator = page.locator(locator_str)
        await locator.wait_for(state="visible", timeout=timeout_ms)
        end_time = page.context._impl_obj._loop.time() + timeout_ms / 1000.0  # type: ignore[attr-defined]

        last_text: Optional[str] = None
        while page.context._impl_obj._loop.time() < end_time:  # type: ignore[attr-defined]
            try:
                text = (await locator.inner_text()).strip()
                last_text = text
                if text:
                    return text
            except PlaywrightError:
                # Retry until timeout
                pass
            await asyncio.sleep(0.5)

        pytest.fail(
            f"Timeout waiting for non-empty text in locator '{locator_str}'. "
            f"Last observed text: {last_text!r}"
        )

    # -------------------------------------------------------------------------
    # Step 1: Ensure LDAP collector is configured and enabled (as in TC_006).
    # -------------------------------------------------------------------------
    try:
        # Navigate to configuration / collectors page.
        # NOTE: Selectors are assumptions and should be updated to match the UI.
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )

        # Open "Settings" or "Configuration" menu.
        await page.click("text=Settings", timeout=10000)

        # Open "Data Collectors" or similar section.
        await page.click("text=Data Collectors", timeout=10000)

        # Locate LDAP collector row for ldap.acme.com
        ldap_row = page.locator("tr:has-text('ldap.acme.com')")

        await ldap_row.wait_for(state="visible", timeout=15000)

        # Assert that LDAP collector exists
        assert await ldap_row.count() > 0, (
            "LDAP collector for 'ldap.acme.com' is not configured. "
            "Prerequisite not met."
        )

        # Assert that LDAP collector is enabled (e.g., checkbox or status text)
        # Example: a toggle or status cell with text 'Enabled'
        ldap_status_cell = ldap_row.locator("td:has-text('Enabled')")
        assert await ldap_status_cell.count() > 0, (
            "LDAP collector for 'ldap.acme.com' is not enabled."
        )

    except PlaywrightError as exc:
        pytest.fail(f"Failed to verify LDAP collector configuration: {exc!r}")

    # -------------------------------------------------------------------------
    # Step 2: Trigger a sync (if manual option exists) or wait for next cycle.
    # -------------------------------------------------------------------------
    try:
        # Check if a manual "Sync Now" button is available for the LDAP collector.
        sync_button = ldap_row.locator("button:has-text('Sync Now'), a:has-text('Sync Now')")

        if await sync_button.count() > 0:
            # Trigger manual sync
            await sync_button.first.click()

            # Optionally wait for a success toast/message
            # e.g., "Sync completed" notification
            await page.locator("text=Sync completed").wait_for(
                state="visible",
                timeout=60000,
            )
        else:
            # No manual sync option; wait for scheduled collection cycle.
            # Adjust wait time as appropriate for the environment.
            await asyncio.sleep(60)

    except PlaywrightError as exc:
        pytest.fail(f"Failed to trigger or wait for LDAP sync: {exc!r}")

    # -------------------------------------------------------------------------
    # Step 3: In Profiler, open endpoint details for `Client1`.
    # -------------------------------------------------------------------------
    try:
        # Navigate to the "Profiler" or "Endpoints" section
        await page.click("text=Profiler", timeout=15000)

        # Wait for endpoints table / search bar
        await page.wait_for_selector("input[placeholder*='Search']", timeout=15000)

        # Search for endpoint `Client1`
        search_box = page.locator("input[placeholder*='Search']")
        await search_box.fill("Client1")
        await search_box.press("Enter")

        # Wait for table row containing `Client1`
        client_row = page.locator("tr:has-text('Client1')")
        await client_row.wait_for(state="visible", timeout=20000)

        # Open endpoint details - usually by clicking the row or a details icon.
        # Here we click the row itself.
        await client_row.first.click()

        # Wait for details panel/page to load
        await page.wait_for_selector("text=Endpoint Details", timeout=15000)

    except PlaywrightError as exc:
        pytest.fail(f"Failed to open endpoint details for 'Client1': {exc!r}")

    # -------------------------------------------------------------------------
    # Step 4: Inspect attributes for owner and department.
    # -------------------------------------------------------------------------
    try:
        # Locators for owner and department fields in endpoint details.
        # Adjust selectors to match actual DOM (labels, data-testid, etc.).
        owner_value_locator = page.locator(
            "xpath=//label[normalize-space()='Owner']/following-sibling::*[1]"
        )
        department_value_locator = page.locator(
            "xpath=//label[normalize-space()='Department']/following-sibling::*[1]"
        )

        # Wait for the fields to be visible and non-empty
        owner_text = await wait_for_non_empty_text(
            "xpath=//label[normalize-space()='Owner']/following-sibling::*[1]",
            timeout_ms=30000,
        )
        department_text = await wait_for_non_empty_text(
            "xpath=//label[normalize-space()='Department']/following-sibling::*[1]",
            timeout_ms=30000,
        )

        # ---------------------------------------------------------------------
        # Assertions: LDAP attributes are populated as expected.
        # ---------------------------------------------------------------------
        assert owner_text == "USER001", (
            "Owner field is not populated with expected LDAP value. "
            f"Expected: 'USER001', Actual: {owner_text!r}"
        )
        assert department_text == "Finance", (
            "Department field is not populated with expected LDAP value. "
            f"Expected: 'Finance', Actual: {department_text!r}"
        )

    except PlaywrightError as exc:
        pytest.fail(
            f"Failed while inspecting owner/department attributes for 'Client1': {exc!r}"
        )

    # -------------------------------------------------------------------------
    # Postcondition: Endpoint data is enriched with LDAP-derived attributes.
    # This is implicitly validated by the assertions above.
    # -------------------------------------------------------------------------