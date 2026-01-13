import asyncio
import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_forward_and_sync_endpoint_data_page_loads_and_options_available(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_007: Forward and Sync Endpoint Data page loads and options are available.

    Test Steps:
    1. Log in as `ppsadmin` (handled by authenticated_page fixture).
    2. Navigate to Profiler > Profiler Configuration > Forward and Sync Endpoint Data.
    3. Verify breadcrumb shows: "Profiler Configuration > Forward and Sync Endpoint Data".
    4. Inspect page elements for options like enabling forwarding, selecting target
       PPS/PCS systems, scheduling sync, etc.

    Expected Results:
    - Page loads without error.
    - Breadcrumb displays correct path.
    - UI presents clear options related to forwarding and synchronizing endpoint data.
    """

    page: Page = authenticated_page

    # STEP 1: Login is handled by the authenticated_page fixture.
    # Assert that we are on an authenticated/authorized page.
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightError as exc:
        pytest.fail(f"Initial authenticated page did not reach network idle state: {exc}")

    # Optional sanity check: ensure we are not on the login page anymore
    login_indicator = page.locator("text=Sign In").first
    if await login_indicator.is_visible():
        pytest.fail("User appears to still be on the login page; authentication may have failed.")

    # STEP 2: Navigate using breadcrumb or navigation to:
    # Profiler > Profiler Configuration > Forward and Sync Endpoint Data

    # Note: The actual selectors will depend on the real UI.
    # These are written in a robust, descriptive way and should be adapted as needed.

    try:
        # Open Profiler main menu
        profiler_menu = page.get_by_role("link", name="Profiler").first
        await profiler_menu.wait_for(state="visible", timeout=10000)
        await profiler_menu.click()

        # Navigate to Profiler Configuration
        profiler_config_link = page.get_by_role(
            "link", name="Profiler Configuration"
        ).first
        await profiler_config_link.wait_for(state="visible", timeout=10000)
        await profiler_config_link.click()

        # Navigate to Forward and Sync Endpoint Data
        forward_sync_link = page.get_by_role(
            "link", name="Forward and Sync Endpoint Data"
        ).first
        await forward_sync_link.wait_for(state="visible", timeout=10000)
        await forward_sync_link.click()

        # Wait for the target page to fully load
        await page.wait_for_load_state("networkidle", timeout=20000)

    except PlaywrightError as exc:
        pytest.fail(f"Navigation to 'Forward and Sync Endpoint Data' failed: {exc}")

    # STEP 3: Verify breadcrumb shows:
    # "Profiler Configuration > Forward and Sync Endpoint Data"

    # Try a few resilient breadcrumb locator strategies
    breadcrumb_text_expected = "Profiler Configuration > Forward and Sync Endpoint Data"

    breadcrumb_locators = [
        page.locator("nav.breadcrumb >> text=Profiler Configuration"),
        page.locator("nav[aria-label='Breadcrumb']"),
        page.get_by_text("Profiler Configuration > Forward and Sync Endpoint Data"),
    ]

    breadcrumb_text_actual = None
    found_breadcrumb = False

    for breadcrumb_locator in breadcrumb_locators:
        try:
            if await breadcrumb_locator.first.is_visible():
                breadcrumb_text_actual = await breadcrumb_locator.inner_text()
                found_breadcrumb = True
                break
        except PlaywrightError:
            # Try next locator if this one fails
            continue

    if not found_breadcrumb:
        pytest.fail(
            "Breadcrumb for 'Forward and Sync Endpoint Data' page not found using known locators."
        )

    # Normalize whitespace for comparison
    normalized_actual = " ".join(breadcrumb_text_actual.split())
    normalized_expected = " ".join(breadcrumb_text_expected.split())

    assert normalized_expected in normalized_actual, (
        f"Breadcrumb text mismatch. Expected to contain: "
        f"'{breadcrumb_text_expected}', but got: '{breadcrumb_text_actual}'"
    )

    # STEP 4: Inspect page elements for options related to forwarding
    # and synchronizing endpoint data.

    # These selectors are intentionally generic and should be adapted to real UI controls.
    # We look for:
    # - A control to enable forwarding
    # - A control to select target PPS/PCS systems
    # - A control to schedule synchronization

    # 4a. Option: enabling forwarding (checkbox, toggle, or similar)
    forwarding_option_locators = [
        page.get_by_label("Enable forwarding"),
        page.get_by_text("Enable forwarding", exact=False),
        page.locator("input[type='checkbox'][name*='forward']"),
    ]

    forwarding_option_found = False
    for locator in forwarding_option_locators:
        try:
            if await locator.first.is_visible():
                forwarding_option_found = True
                break
        except PlaywrightError:
            continue

    assert forwarding_option_found, (
        "Forwarding enable option not found on 'Forward and Sync Endpoint Data' page."
    )

    # 4b. Option: selecting target PPS/PCS systems (dropdown or list)
    target_system_option_locators = [
        page.get_by_label("Target PPS/PCS system"),
        page.get_by_role("combobox", name="Target PPS/PCS system"),
        page.get_by_text("Target PPS", exact=False),
        page.get_by_text("Target PCS", exact=False),
    ]

    target_system_option_found = False
    for locator in target_system_option_locators:
        try:
            if await locator.first.is_visible():
                target_system_option_found = True
                break
        except PlaywrightError:
            continue

    assert target_system_option_found, (
        "Target PPS/PCS system selection control not found on 'Forward and Sync Endpoint Data' page."
    )

    # 4c. Option: scheduling synchronization (date/time or schedule control)
    schedule_option_locators = [
        page.get_by_label("Schedule sync"),
        page.get_by_role("combobox", name="Schedule"),
        page.get_by_text("Schedule sync", exact=False),
        page.get_by_text("Synchronization schedule", exact=False),
    ]

    schedule_option_found = False
    for locator in schedule_option_locators:
        try:
            if await locator.first.is_visible():
                schedule_option_found = True
                break
        except PlaywrightError:
            continue

    assert schedule_option_found, (
        "Synchronization scheduling option not found on 'Forward and Sync Endpoint Data' page."
    )

    # FINAL ASSERTION: Page is loaded and main content is visible.
    # This is a generic check that some primary heading or content is present.
    try:
        main_heading = page.get_by_role(
            "heading", name="Forward and Sync Endpoint Data"
        ).first
        await main_heading.wait_for(state="visible", timeout=10000)
    except PlaywrightError as exc:
        pytest.fail(
            "Main heading 'Forward and Sync Endpoint Data' not visible; "
            f"page may not have loaded correctly: {exc}"
        )

    # Postconditions: none (we do not modify any configuration in this test).
    # Optionally wait a short moment to ensure no unexpected errors appear.
    await asyncio.sleep(1)