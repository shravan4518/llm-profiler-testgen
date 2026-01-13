import asyncio
from typing import Dict, Any

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_021_csrf_protection_on_profiler_config(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_021: Security – prevent configuration via CSRF without user action

    Validate that Profiler Configuration endpoints are protected against CSRF
    by attempting to change configuration via an auto-submitting HTML form
    (simulating a CSRF attack) and verifying that the configuration is not
    changed without explicit user interaction.

    Prerequisites:
    - Valid admin session in Browser A (provided by `authenticated_page`).
    - Ability to craft a malicious HTML form posting to the configuration
      endpoint.

    Expected results:
    - CSRF protections prevent unauthorized config change; either the request
      is rejected due to missing/invalid CSRF token or requires explicit UI
      action.
    - Profiler configuration values remain unchanged after the attempted attack.
    """

    # -------------------------------------------------------------------------
    # Test configuration / helpers (adapt these selectors/URLs to your AUT)
    # -------------------------------------------------------------------------
    profiler_config_url = (
        "https://10.34.50.201/dana-na/auth/url_admin/profiler_config.cgi"
    )
    profiler_config_save_url = (
        "https://10.34.50.201/dana-na/auth/url_admin/profiler_config_save.cgi"
    )

    # Example field name and value to try to change via CSRF
    # NOTE: Update these to match the real Profiler configuration form fields.
    target_field_name = "profiler_enabled"
    original_expected_type = "checkbox"  # for sanity checks, optional

    # We will use these values to detect whether the configuration was changed.
    original_config: Dict[str, Any] = {}
    post_attack_config: Dict[str, Any] = {}

    # -------------------------------------------------------------------------
    # Helper: Safely read profiler configuration values from the UI
    # -------------------------------------------------------------------------
    async def read_profiler_config(page: Page) -> Dict[str, Any]:
        """
        Read relevant profiler configuration values from the configuration page.

        Returns:
            dict: key/value pairs representing relevant profiler config state.
        """
        config: Dict[str, Any] = {}

        try:
            # Navigate to Profiler configuration page
            await page.goto(profiler_config_url, wait_until="networkidle")

            # Example: read a checkbox value.
            # Update selectors to match the real application.
            checkbox_locator = page.locator(f"input[name='{target_field_name}']")
            if await checkbox_locator.count() == 0:
                raise AssertionError(
                    f"Expected profiler field '{target_field_name}' not found."
                )

            input_type = await checkbox_locator.get_attribute("type")
            if original_expected_type and input_type != original_expected_type:
                raise AssertionError(
                    f"Expected input type '{original_expected_type}' for "
                    f"'{target_field_name}', got '{input_type}'."
                )

            checked = await checkbox_locator.is_checked()
            config[target_field_name] = checked

            # Add more fields here as needed

        except PlaywrightError as exc:
            raise AssertionError(
                f"Failed to read profiler configuration: {exc}"
            ) from exc

        return config

    # -------------------------------------------------------------------------
    # Helper: Create a malicious HTML page with an auto-submitting POST form
    # -------------------------------------------------------------------------
    def build_malicious_html(target_url: str) -> str:
        """
        Build an auto-submitting HTML form that attempts to POST to the
        configuration save endpoint without a CSRF token.
        """
        # The form fields below must match actual server-side field names.
        # The idea is to set a value opposite to the original to detect change.
        malicious_html = f"""
        <!doctype html>
        <html>
        <head>
            <title>CSRF Test Page</title>
        </head>
        <body>
            <form id="csrfForm" action="{target_url}" method="POST">
                <!-- Attempt to change profiler configuration without CSRF token -->
                <input type="hidden" name="{target_field_name}" value="on" />
                <!-- Add any other fields that might be required by the endpoint -->
            </form>
            <script>
                // Auto-submit the form immediately on load
                document.getElementById('csrfForm').submit();
            </script>
        </body>
        </html>
        """
        return malicious_html

    # -------------------------------------------------------------------------
    # STEP 1: Log in as TPSAdmin in Browser A (already done via fixture)
    # -------------------------------------------------------------------------
    # `authenticated_page` is assumed to be a logged-in admin session (Browser A).
    page_a: Page = authenticated_page

    # Sanity check: ensure we are logged in by verifying some admin UI element.
    # Update selector as appropriate.
    try:
        await page_a.goto(
            profiler_config_url,
            wait_until="networkidle",
        )
        await page_a.wait_for_timeout(1000)
    except PlaywrightError as exc:
        raise AssertionError(
            f"Admin session is not valid or profiler config page not reachable: {exc}"
        ) from exc

    # -------------------------------------------------------------------------
    # STEP 2: Capture original Profiler configuration (baseline)
    # -------------------------------------------------------------------------
    original_config = await read_profiler_config(page_a)

    # -------------------------------------------------------------------------
    # STEP 3: In Browser B, prepare a malicious HTML page
    #         (simulated here by opening a new context/page and setting content)
    # -------------------------------------------------------------------------
    malicious_html_content = build_malicious_html(profiler_config_save_url)

    # Create a separate context to simulate Browser B (no auth, just hosting)
    context_b = await browser.new_context()
    page_b = await context_b.new_page()

    try:
        # Host the malicious HTML by directly setting its content.
        # In a real scenario, this could be served from another domain.
        await page_b.set_content(malicious_html_content)
    except PlaywrightError as exc:
        await context_b.close()
        raise AssertionError(
            f"Failed to load malicious HTML content in Browser B: {exc}"
        ) from exc

    # NOTE: We do not need to keep Browser B open after content is set,
    # but we keep it alive in case any async scripts run (e.g., auto-submit).

    # -------------------------------------------------------------------------
    # STEP 4: While logged in, open the malicious HTML page in Browser A
    #         (same session) and let it attempt the CSRF attack
    # -------------------------------------------------------------------------
    # Instead of hosting externally, we inject the same malicious HTML into
    # Browser A to simulate the admin visiting a malicious site while logged in.
    try:
        await page_a.set_content(malicious_html_content)
        # Wait a bit to allow auto-submit and the resulting request to complete.
        await page_a.wait_for_timeout(3000)
    except PlaywrightError as exc:
        await context_b.close()
        raise AssertionError(
            f"Failed to load malicious HTML in admin session (Browser A): {exc}"
        ) from exc

    # -------------------------------------------------------------------------
    # STEP 5: Re-open the Profiler configuration page and read config again
    # -------------------------------------------------------------------------
    post_attack_config = await read_profiler_config(page_a)

    # -------------------------------------------------------------------------
    # STEP 6: Assertions – verify that config did NOT change
    # -------------------------------------------------------------------------
    # 1) The specific field we attempted to change must remain unchanged.
    assert (
        post_attack_config.get(target_field_name)
        == original_config.get(target_field_name)
    ), (
        "Profiler configuration appears to have changed via CSRF-like request. "
        f"Field '{target_field_name}' before: {original_config.get(target_field_name)}, "
        f"after: {post_attack_config.get(target_field_name)}"
    )

    # 2) Optionally assert that all tracked fields are identical.
    assert post_attack_config == original_config, (
        "Profiler configuration differs after CSRF attempt. "
        f"Original: {original_config}, After: {post_attack_config}"
    )

    # -------------------------------------------------------------------------
    # STEP 7: Optionally verify that the CSRF request itself failed
    # -------------------------------------------------------------------------
    # If the application surfaces error messages or status indicators, they can
    # be asserted here. Example (update selector/message as needed):
    #
    # error_banner = page_a.locator(".error-banner")
    # if await error_banner.count() > 0:
    #     error_text = (await error_banner.text_content()) or ""
    #     assert "CSRF" in error_text or "invalid token" in error_text.lower()

    # -------------------------------------------------------------------------
    # Cleanup
    # -------------------------------------------------------------------------
    await context_b.close()

    # Small delay to ensure any pending network activities are done
    await asyncio.sleep(0.5)