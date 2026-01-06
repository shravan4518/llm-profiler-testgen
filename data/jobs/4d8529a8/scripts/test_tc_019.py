import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_019_integration_wlc_forwarding_http_ua_and_dhcp_fingerprinting(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_019: Integration – WLC forwarding HTTP User Agent and DHCP fingerprinting together

    Purpose:
        Ensure DHCP fingerprinting works alongside WLC configuration that forwards
        HTTP User Agent to PPS, resulting in more precise classification.

    Scope:
        - Verifies WLC configuration shows PPS IP in "Forward HTTP User Agent to IPs"
        - Verifies device with MAC AA:BB:CC:DD:EE:15 is initially classified via DHCP
        - Verifies HTTP User-Agent data refines classification without conflict
        - Verifies device record persists with combined DHCP and HTTP UA attributes

    Notes:
        - This test assumes:
          * WLC configuration and DHCP/User-Agent traffic generation have been
            performed outside the UI (e.g., via network/infra automation).
          * The UI under test is the PPS Profiler UI at the target system URL.
        - Where direct UI access to WLC is not available, this test validates
          the *effects* in PPS Profiler (classification and attributes) and
          treats WLC configuration verification as a best-effort UI check or
          a soft assertion if applicable.
    """

    page: Page = authenticated_page

    # ----------------------------------------------------------------------
    # Helper functions
    # ----------------------------------------------------------------------

    async def safe_click(locator_str: str, description: str, timeout: int = 15000) -> None:
        """Click an element safely with error handling."""
        try:
            await page.locator(locator_str).click(timeout=timeout)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click {description} using locator '{locator_str}': {exc}")

    async def safe_fill(locator_str: str, value: str, description: str, timeout: int = 15000) -> None:
        """Fill an input safely with error handling."""
        try:
            await page.locator(locator_str).fill(value, timeout=timeout)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to fill {description} using locator '{locator_str}': {exc}")

    async def wait_for_text(
        locator_str: str,
        expected_substring: str,
        description: str,
        timeout: int = 20000,
    ) -> None:
        """Wait until the given locator contains the expected text."""
        try:
            await page.locator(locator_str).filter(has_text=expected_substring).first.wait_for(
                state="visible",
                timeout=timeout,
            )
        except PlaywrightError as exc:
            pytest.fail(
                f"Timed out waiting for {description} to contain '{expected_substring}' "
                f"using locator '{locator_str}': {exc}"
            )

    async def get_text_or_none(locator_str: str, description: str) -> Optional[str]:
        """Get inner text from a locator, returning None if not found."""
        locator = page.locator(locator_str).first
        try:
            if await locator.count() == 0:
                return None
            return (await locator.inner_text()).strip()
        except PlaywrightError as exc:
            pytest.fail(f"Error retrieving text for {description} using '{locator_str}': {exc}")
        return None

    # ----------------------------------------------------------------------
    # Step 1: Verify WLC configuration for “Forward HTTP User Agent to IPs”
    #         includes PPS IP.
    #
    # Assumption:
    #   - The system exposes WLC-related configuration within the same UI.
    #   - If it does not, treat this as a soft check and focus on PPS behavior.
    # ----------------------------------------------------------------------

    # Navigate to a hypothetical WLC configuration section in PPS UI
    # Adjust selectors and navigation to match the real application.
    try:
        await page.goto(
            "https://npre-miiqa2mp-eastus2.openai.azure.com/wlc/config",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Unable to navigate to WLC configuration page: {exc}")

    # Example locator for the "Forward HTTP User Agent to IPs" field
    forward_ua_ips_locator = "textarea#wlc-forward-ua-ips"

    # Verify the PPS IP is present in the list of IPs.
    # NOTE: Replace '10.10.10.10' with the actual PPS IP used in your environment.
    pps_ip = "10.10.10.10"
    forward_ua_ips_text = await get_text_or_none(
        forward_ua_ips_locator,
        "Forward HTTP User Agent to IPs field",
    )

    assert (
        forward_ua_ips_text is not None
    ), "Forward HTTP User Agent to IPs field is not present on the WLC configuration page."

    assert (
        pps_ip in forward_ua_ips_text
    ), f"PPS IP {pps_ip} is not configured in 'Forward HTTP User Agent to IPs'."

    # ----------------------------------------------------------------------
    # Steps 2–4:
    # Connect Android phone, trigger DHCP, and generate HTTP/HTTPS traffic.
    #
    # These are physical/network actions not directly controllable via Playwright.
    # The UI test can only wait for and validate their effects in PPS Profiler.
    #
    # Implementation:
    #   - Wait/poll until the device with MAC AA:BB:CC:DD:EE:15 appears in the
    #     Profiler UI with an initial DHCP-based classification.
    #   - Then wait/poll until HTTP UA attributes are present and classification
    #     is refined.
    # ----------------------------------------------------------------------

    device_mac = "AA:BB:CC:DD:EE:15"

    # Navigate to Profiler device list/search page
    try:
        await page.goto(
            "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/devices",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Unable to navigate to Profiler devices page: {exc}")

    # ----------------------------------------------------------------------
    # Helper: Poll for device record to appear with initial DHCP classification
    # ----------------------------------------------------------------------

    async def wait_for_initial_dhcp_classification(
        mac: str,
        timeout_seconds: int = 120,
        poll_interval_seconds: int = 5,
    ) -> str:
        """
        Polls the Profiler UI for a device record with the given MAC and
        returns the initial classification string once found.

        Expected to reflect DHCP-based classification, such as "Generic Android".
        """
        end_time = asyncio.get_event_loop().time() + timeout_seconds
        initial_classification_locator = "span.device-classification"

        while asyncio.get_event_loop().time() < end_time:
            # Search by MAC
            await safe_fill("input#device-search", mac, "device search input")
            await safe_click("button#device-search-submit", "device search submit button")

            # Wait for results to load
            try:
                await page.wait_for_timeout(2000)
            except PlaywrightError:
                # Non-critical; continue polling
                pass

            # Check if a row containing the MAC is present
            device_row = page.locator("tr.device-row", has_text=mac).first
            if await device_row.count() > 0:
                # Get classification text from the device row
                classification_text = await device_row.locator(
                    initial_classification_locator
                ).inner_text()
                classification_text = classification_text.strip()

                return classification_text

            # Not yet found – wait and retry
            await asyncio.sleep(poll_interval_seconds)

        pytest.fail(
            f"Device with MAC {mac} did not appear in Profiler within "
            f"{timeout_seconds} seconds. Ensure DHCP traffic was generated."
        )

    # ----------------------------------------------------------------------
    # Helper: Poll for refined HTTP UA-based classification and combined attributes
    # ----------------------------------------------------------------------

    async def wait_for_refined_http_ua_classification(
        mac: str,
        initial_classification: str,
        timeout_seconds: int = 180,
        poll_interval_seconds: int = 10,
    ) -> str:
        """
        Polls the device details page for the given MAC until:
            - Classification changes from the initial DHCP-based value, and
            - HTTP User-Agent attribute is present.
        Returns the refined classification string.
        """
        end_time = asyncio.get_event_loop().time() + timeout_seconds

        while asyncio.get_event_loop().time() < end_time:
            # Open device details page (hypothetical URL pattern)
            try:
                await page.goto(
                    f"https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/devices/{mac}",
                    wait_until="networkidle",
                )
            except PlaywrightError as exc:
                pytest.fail(f"Unable to navigate to device details page for MAC {mac}: {exc}")

            # Read current classification
            current_classification = await get_text_or_none(
                "span#device-classification",
                "device classification on details page",
            )
            assert current_classification is not None, (
                "Device classification field is missing on the device details page."
            )

            # Read DHCP fingerprint and HTTP UA attributes
            dhcp_fingerprint = await get_text_or_none(
                "div#attribute-dhcp-fingerprint",
                "DHCP fingerprint attribute",
            )
            http_user_agent = await get_text_or_none(
                "div#attribute-http-user-agent",
                "HTTP User-Agent attribute",
            )

            # Check that DHCP fingerprint is present (should remain)
            assert dhcp_fingerprint, (
                "DHCP fingerprint attribute is missing; DHCP-based profiling "
                "must remain available."
            )

            # Check for HTTP UA attribute; if present and classification refined, return
            if http_user_agent:
                # Classification should be refined (different from initial)
                if current_classification != initial_classification:
                    return current_classification

            # Not yet refined – wait and retry
            await asyncio.sleep(poll_interval_seconds)

        pytest.fail(
            f"HTTP UA-based refined classification for MAC {mac} did not appear "
            f"within {timeout_seconds} seconds. Ensure HTTP/HTTPS traffic was generated."
        )

    # ----------------------------------------------------------------------
    # Step 5: In Profiler UI, locate device record for MAC AA:BB:CC:DD:EE:15.
    # Step 6 (part 1): Verify device is initially classified via DHCP fingerprint.
    # ----------------------------------------------------------------------

    initial_classification = await wait_for_initial_dhcp_classification(device_mac)

    # Assert initial classification looks DHCP-based (e.g., Generic Android)
    # This is a flexible assertion: we expect "Android" and "Generic" or similar.
    assert (
        "android" in initial_classification.lower()
    ), (
        f"Initial classification '{initial_classification}' does not appear to be "
        "an Android DHCP-based classification."
    )

    # ----------------------------------------------------------------------
    # Step 6 (part 2): After HTTP UA data is received, classification is refined
    #                  and DHCP + HTTP UA attributes are combined.
    # ----------------------------------------------------------------------

    refined_classification = await wait_for_refined_http_ua_classification(
        device_mac,
        initial_classification=initial_classification,
    )

    # Expected: refined classification is more specific than the initial one
    assert refined_classification != initial_classification, (
        "Refined classification is identical to initial DHCP-based classification; "
        "HTTP UA data did not refine the device classification."
    )

    # Basic heuristic: refined classification should still indicate Android but
    # be more specific (e.g., contain version or model info).
    assert "android" in refined_classification.lower(), (
        f"Refined classification '{refined_classification}' no longer indicates "
        "Android; profiling data may be conflicting."
    )

    # ----------------------------------------------------------------------
    # Step 6 (part 3): No conflict between HTTP and DHCP-based profiling; final
    #                  classification is consistent and precise.
    # ----------------------------------------------------------------------

    # Re-open device details to assert combined attributes and consistency
    try:
        await page.goto(
            f"https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/devices/{device_mac}",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Unable to re-open device details page for MAC {device_mac}: {exc}")

    final_classification = await get_text_or_none(
        "span#device-classification",
        "final device classification",
    )
    dhcp_fingerprint_final = await get_text_or_none(
        "div#attribute-dhcp-fingerprint",
        "final DHCP fingerprint attribute",
    )
    http_user_agent_final = await get_text_or_none(
        "div#attribute-http-user-agent",
        "final HTTP User-Agent attribute",
    )

    assert final_classification is not None, "Final classification field is missing."
    assert dhcp_fingerprint_final, "Final DHCP fingerprint attribute is missing."
    assert http_user_agent_final, "Final HTTP User-Agent attribute is missing."

    # Final classification should match the refined one we observed
    assert final_classification == refined_classification, (
        "Final classification on device details page does not match the refined "
        "classification observed earlier; profiling result is inconsistent."
    )

    # Ensure there is no explicit conflict indicator in the UI (example check)
    conflict_banner = page.locator("div.profiling-conflict-banner")
    if await conflict_banner.count() > 0:
        conflict_text = await conflict_banner.first.inner_text()
        pytest.fail(
            f"Profiler UI indicates a conflict between HTTP and DHCP profiling: "
            f"{conflict_text}"
        )

    # ----------------------------------------------------------------------
    # Postconditions:
    #   - Device record persists with combined DHCP and HTTP UA attributes.
    #
    # Validation:
    #   - Reload the device details page and ensure attributes are still present.
    # ----------------------------------------------------------------------

    try:
        await page.reload(wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reload device details page for MAC {device_mac}: {exc}")

    persisted_dhcp_fingerprint = await get_text_or_none(
        "div#attribute-dhcp-fingerprint",
        "persisted DHCP fingerprint attribute",
    )
    persisted_http_user_agent = await get_text_or_none(
        "div#attribute-http-user-agent",
        "persisted HTTP User-Agent attribute",
    )

    assert persisted_dhcp_fingerprint, (
        "DHCP fingerprint attribute did not persist after reload."
    )
    assert persisted_http_user_agent, (
        "HTTP User-Agent attribute did not persist after reload."
    )