import asyncio
import ipaddress
import pytest
from playwright.async_api import Page, Error


@pytest.mark.asyncio
async def test_save_profiler_basic_config_with_invalid_ip(authenticated_page: Page, browser):
    """
    TC_008: Attempt to save basic Profiler configuration with invalid management IP address

    Title:
        Attempt to save basic Profiler configuration with invalid management IP address

    Description:
        Validate input validation and error handling when admin enters an invalid IPv4
        address for Profiler management IP.

    Preconditions:
        - User is logged in as `ppsadmin` (handled by authenticated_page fixture).
        - User has access to Basic Configuration page.

    Steps:
        1. Log in as `ppsadmin`.
        2. Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration.
        3. Enter `LocalProfilerInvalidIP` as Profiler Name.
        4. Enter `999.999.999.999` into IP address field.
        5. Click `Save Changes`.

    Expected Results:
        - System rejects the configuration.
        - A clear validation error appears near the IP field (e.g., “Invalid IP address”).
        - No configuration is saved with this invalid IP.
        - Existing valid configuration (if any) remains unchanged.
        - Profiler management IP remains at prior valid value or blank if none was set.
    """
    page: Page = authenticated_page

    # NOTE:
    # The actual selectors (text, IDs, names, etc.) are assumptions.
    # Adjust them to match the real application DOM.

    # -------------------------------------------------------------------------
    # Helper functions
    # -------------------------------------------------------------------------

    async def safe_get_text(locator, default: str = "") -> str:
        """Safely get text from a locator, returning default if not found or not visible."""
        try:
            if await locator.first.is_visible():
                return (await locator.first.text_content()) or default
        except Error:
            return default
        return default

    async def safe_get_input_value(locator, default: str = "") -> str:
        """Safely get value from an input locator, returning default on failure."""
        try:
            if await locator.first.is_visible():
                return await locator.first.input_value()
        except Error:
            return default
        return default

    # -------------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin`
    # -------------------------------------------------------------------------
    # This is handled by the authenticated_page fixture.
    # We only validate that we are on an authenticated/admin page.
    await page.wait_for_load_state("networkidle")

    # Basic sanity check that we're logged in and on the admin UI
    # (Adjust selector/text as appropriate for the real app)
    await page.wait_for_timeout(500)  # small wait to stabilize UI
    assert await page.get_by_text("Profiler", exact=False).first.is_visible(), (
        "Profiler menu not visible; login or navigation may have failed."
    )

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Profiler > Profiler Configuration > Settings > Basic Configuration
    # -------------------------------------------------------------------------
    # These are assumed selectors based on typical menu structures.
    # Replace with actual selectors for your application.

    # Open Profiler main menu
    await page.get_by_role("link", name="Profiler", exact=False).click()

    # Navigate to Profiler Configuration
    await page.get_by_role("link", name="Profiler Configuration", exact=False).click()

    # Navigate to Settings
    await page.get_by_role("link", name="Settings", exact=False).click()

    # Finally, open Basic Configuration
    await page.get_by_role("link", name="Basic Configuration", exact=False).click()

    # Wait for Basic Configuration form to be visible
    basic_config_header = page.get_by_role(
        "heading", name="Basic Configuration", exact=False
    )
    await basic_config_header.wait_for(state="visible", timeout=10000)

    # -------------------------------------------------------------------------
    # Capture existing configuration to validate "no change" behavior later
    # -------------------------------------------------------------------------
    # Assumed selectors:
    #   - Profiler Name input: input[name="profilerName"]
    #   - IP Address input: input[name="profilerIp"]
    profiler_name_input = page.locator('input[name="profilerName"]')
    profiler_ip_input = page.locator('input[name="profilerIp"]')

    original_profiler_name = await safe_get_input_value(profiler_name_input, "")
    original_profiler_ip = await safe_get_input_value(profiler_ip_input, "")

    # Keep a parsed version of original IP if valid, for stronger validation
    original_ip_is_valid = False
    try:
        if original_profiler_ip:
            ipaddress.ip_address(original_profiler_ip)
            original_ip_is_valid = True
    except ValueError:
        original_ip_is_valid = False

    # -------------------------------------------------------------------------
    # Step 3: Enter `LocalProfilerInvalidIP` as Profiler Name
    # -------------------------------------------------------------------------
    await profiler_name_input.fill("LocalProfilerInvalidIP")

    # -------------------------------------------------------------------------
    # Step 4: Enter `999.999.999.999` into IP address field
    # -------------------------------------------------------------------------
    invalid_ip = "999.999.999.999"
    await profiler_ip_input.fill(invalid_ip)

    # -------------------------------------------------------------------------
    # Step 5: Click `Save Changes`
    # -------------------------------------------------------------------------
    # Assumed selector for Save Changes button
    save_button = page.get_by_role("button", name="Save Changes", exact=False)

    # Ensure Save button is enabled before clicking
    assert await save_button.is_enabled(), "Save Changes button is disabled unexpectedly."

    await save_button.click()

    # Wait briefly for validation and possible error messages to appear
    await page.wait_for_timeout(1000)

    # -------------------------------------------------------------------------
    # Assertions for expected results
    # -------------------------------------------------------------------------

    # 1. System rejects the configuration: we expect a validation error near IP field.
    #    We look for typical error patterns near the IP input.
    #    Adjust selectors/text according to real application.

    # Possible error locators:
    ip_error_locators = [
        page.get_by_text("Invalid IP address", exact=False),
        page.locator("span.error", has_text="Invalid IP"),
        page.locator("div.validation-error", has_text="IP"),
        page.locator("span", has_text="Invalid IP"),
    ]

    error_visible = False
    error_text_collected = []

    for locator in ip_error_locators:
        try:
            if await locator.first.is_visible():
                error_visible = True
                error_text_collected.append(await safe_get_text(locator))
        except Error:
            # Ignore locator errors; we'll check the aggregated result
            continue

    assert error_visible, (
        "Expected a validation error near the IP field for invalid IP, "
        "but no error message was found."
    )

    # Optional: strengthen the assertion by checking that at least one error
    # message contains 'invalid' and 'IP' (case-insensitive).
    normalized_errors = " ".join(error_text_collected).lower()
    assert (
        "invalid" in normalized_errors and "ip" in normalized_errors
    ), f"Validation error did not clearly indicate invalid IP. Found: {error_text_collected}"

    # 2. No configuration is saved with this invalid IP.
    #    We validate that the IP field did not persist the invalid value after
    #    the validation error. Some UIs keep the invalid value in the field
    #    but do not commit it; others reset the field. We will treat both as
    #    acceptable as long as the backend value (after reload) is not the
    #    invalid IP.

    # First, check the immediate field value (UI-level check)
    current_ip_value = await safe_get_input_value(profiler_ip_input, "")
    # It may still show invalid value in the input; that's not a proof of save.
    # So we do not assert here; we rely on the post-reload check below.

    # 3. Existing valid configuration (if any) remains unchanged.
    #    To confirm the configuration was not saved, reload the page and re-open
    #    the Basic Configuration, then compare the stored values.

    # Reload current page to force data reload from backend
    await page.reload(wait_until="networkidle")

    # Re-navigate to Basic Configuration in case reload changes current view
    await page.get_by_role("link", name="Profiler", exact=False).click()
    await page.get_by_role("link", name="Profiler Configuration", exact=False).click()
    await page.get_by_role("link", name="Settings", exact=False).click()
    await page.get_by_role("link", name="Basic Configuration", exact=False).click()
    await basic_config_header.wait_for(state="visible", timeout=10000)

    # Re-locate inputs after navigation
    profiler_name_input = page.locator('input[name="profilerName"]')
    profiler_ip_input = page.locator('input[name="profilerIp"]')

    persisted_profiler_name = await safe_get_input_value(profiler_name_input, "")
    persisted_profiler_ip = await safe_get_input_value(profiler_ip_input, "")

    # Assert that invalid IP is not persisted
    assert persisted_profiler_ip != invalid_ip, (
        "Invalid IP address appears to have been saved; "
        f"persisted IP is {persisted_profiler_ip!r}, expected not {invalid_ip!r}."
    )

    # If there was a valid IP before, verify it did not change
    if original_profiler_ip:
        if original_ip_is_valid:
            assert persisted_profiler_ip == original_profiler_ip, (
                "Existing valid Profiler IP configuration changed after invalid save attempt. "
                f"Original: {original_profiler_ip!r}, Persisted: {persisted_profiler_ip!r}"
            )
        else:
            # Original was non-empty but invalid; we at least ensure it didn't
            # become the new invalid IP.
            assert persisted_profiler_ip != invalid_ip, (
                "Profiler IP changed to the new invalid IP despite prior invalid value."
            )
    else:
        # If no IP was set before, it should remain blank or unset.
        assert persisted_profiler_ip in ("", None), (
            "Profiler management IP should remain blank when invalid IP is rejected, "
            f"but found {persisted_profiler_ip!r}."
        )

    # Optional: ensure that the profiler name did not get saved with the invalid IP.
    # Depending on system behavior, the name may or may not be saved together with IP.
    # If the system treats the form as atomic, the name should also remain unchanged.
    # We implement a soft assertion-like check (no hard failure) but log discrepancy.

    try:
        if original_profiler_name and persisted_profiler_name != original_profiler_name:
            pytest.fail(
                "Profiler name changed despite invalid IP preventing configuration save. "
                f"Original name: {original_profiler_name!r}, "
                f"Persisted name: {persisted_profiler_name!r}"
            )
    except AssertionError:
        # Re-raise to ensure pytest reports the failure
        raise

    # Postconditions are implicitly verified by the assertions above:
    # - Profiler management IP remains at prior valid value or blank if none was set.