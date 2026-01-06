import asyncio
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_snmp_trap_payload_is_sanitized(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_017: Verify security – SNMP trap payload is sanitized and not executed as code.

    This test verifies that a malicious SNMP trap containing a script tag in a
    string field is treated as data only and cannot trigger script execution (XSS)
    in the Profiler UI.

    Preconditions:
        - Profiler UI is reachable.
        - `authenticated_page` fixture logs in as admin.
        - An external mechanism can send a crafted SNMP trap to the Profiler.

    Steps:
        1. Use SNMP tool to craft and send a trap with string field:
           "<script>alert('XSS')</script>" from IP 10.10.60.60.
        2. Wait for trap processing.
        3. Navigate to pages showing device/trap details for 10.10.60.60.
        4. Verify that the script is not executed and is rendered as escaped text.

    Expected:
        - String is displayed as plain text, properly escaped.
        - No JavaScript execution (no alert dialogs).
        - HTML source contains escaped characters (e.g., &lt;script&gt;).
    """

    # -------------------------------------------------------------------------
    # Helper: send SNMP trap (placeholder)
    # -------------------------------------------------------------------------
    async def send_snmp_trap_with_payload(
        source_ip: str,
        payload: str,
    ) -> None:
        """
        Placeholder for sending an SNMP trap with a controllable string varbind.

        In a real environment, implement this using:
        - pysnmp
        - snmptrap CLI
        - or an internal test utility / API

        This function is async to fit into the async test flow.
        """
        # NOTE: Implement actual SNMP trap sending here, for example:
        #   await asyncio.create_subprocess_exec(
        #       "snmptrap", "-v2c", "-c", "public", PROFILER_TRAP_IP, "...",
        #       stdout=asyncio.subprocess.DEVNULL,
        #       stderr=asyncio.subprocess.DEVNULL,
        #   )
        # For now, this is a no-op placeholder.
        await asyncio.sleep(0.1)

    # -------------------------------------------------------------------------
    # Test data
    # -------------------------------------------------------------------------
    malicious_source_ip = "10.10.60.60"
    malicious_payload = "<script>alert('XSS')</script>"
    escaped_payload_fragment = "&lt;script&gt;alert('XSS')&lt;/script&gt;"

    page: Page = authenticated_page

    # -------------------------------------------------------------------------
    # Step 1–2: Send malicious SNMP trap and wait for processing
    # -------------------------------------------------------------------------
    try:
        await send_snmp_trap_with_payload(
            source_ip=malicious_source_ip,
            payload=malicious_payload,
        )
    except Exception as exc:
        pytest.fail(f"Failed to send SNMP trap with malicious payload: {exc}")

    # Allow time for the Profiler to receive and process the trap.
    # Adjust this delay or replace with a polling mechanism as needed.
    await asyncio.sleep(10)

    # -------------------------------------------------------------------------
    # Step 3: Navigate to page(s) showing device/trap details for 10.10.60.60
    # -------------------------------------------------------------------------
    # NOTE: The actual navigation depends on the Profiler UI.
    # Replace selectors and navigation steps with real ones for your system.

    try:
        # Example: navigate to a device search or trap list page
        # This is a placeholder path; adjust to your application.
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open Profiler admin page: {exc}")

    # Example: filter by IP address (replace selectors with real ones)
    # The following is intentionally generic and must be adapted:
    try:
        # Locate a search input, type the source IP, and submit
        search_box_selector = "input[name='deviceSearch']"
        search_button_selector = "button#deviceSearchButton"

        if await page.locator(search_box_selector).count() == 0:
            pytest.skip(
                "Device search input not found; adjust selectors for the real UI."
            )

        await page.fill(search_box_selector, malicious_source_ip)
        await page.click(search_button_selector)

        # Wait for results to load
        await page.wait_for_timeout(3000)

        # Click on the device / trap entry for 10.10.60.60
        # This is a generic example; update the selector accordingly.
        device_link = page.locator(f"text={malicious_source_ip}").first
        await device_link.click()
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to device/trap details page: {exc}")

    # -------------------------------------------------------------------------
    # Step 4: Observe page rendering and console – ensure script is not executed
    # -------------------------------------------------------------------------

    # 4a. Assert that no alert dialog is triggered.
    # We set up a handler that would fail the test if an alert appears.
    alert_triggered = False

    async def dialog_handler(dialog) -> None:
        nonlocal alert_triggered
        alert_triggered = True
        await dialog.dismiss()

    page.on("dialog", dialog_handler)

    # Wait a short period to see if any dialogs are triggered automatically.
    await page.wait_for_timeout(3000)

    assert (
        alert_triggered is False
    ), "Unexpected JavaScript alert dialog detected; possible XSS execution."

    # 4b. Verify that the payload is rendered as text, not executed HTML.
    # We check that the raw script tag is not present in the DOM as HTML.
    page_content = await page.content()

    # The raw script tag should not appear as-is in the HTML.
    assert (
        malicious_payload not in page_content
    ), "Malicious script tag is present in the HTML source; expected it to be escaped."

    # 4c. Verify that escaped characters are present somewhere in the HTML.
    # This indicates proper sanitization / escaping.
    assert (
        escaped_payload_fragment in page_content
    ), "Escaped script payload not found in HTML; expected &lt;script&gt; style escaping."

    # 4d. Optionally, verify that the text is visible as plain text on screen.
    # This uses a generic locator; adjust to match where the trap description is shown.
    # We search for the escaped text in the rendered page (inner text).
    visible_text_locator = page.get_by_text("alert('XSS')", exact=False)

    try:
        await visible_text_locator.wait_for(timeout=5000)
    except PlaywrightError:
        pytest.fail(
            "Trap description containing the malicious payload was not found "
            "in the UI; cannot verify that it is displayed as plain text."
        )

    # Confirm that the element's innerHTML is escaped (no <script> tag).
    element_html: Optional[str] = await visible_text_locator.first.evaluate(
        "el => el.innerHTML"
    )

    assert element_html is not None, "Failed to retrieve innerHTML of payload element."

    assert (
        "<script>" not in element_html
    ), "Payload element innerHTML contains a <script> tag; expected escaped text."

    assert (
        "&lt;script&gt;" in element_html
    ), "Payload element innerHTML does not contain escaped script tag; expected &lt;script&gt;."

    # -------------------------------------------------------------------------
    # Postconditions: system continues operating normally
    # -------------------------------------------------------------------------
    # Basic sanity check: ensure page is still responsive and no JS errors blocked it.
    # We can perform a simple interaction, such as clicking a known navigation element.
    # This is generic and may need adjustment.
    try:
        await page.wait_for_timeout(1000)
        # Example: check that some common navigation or header is still present.
        header_locator = page.locator("header").first
        if await header_locator.count() > 0:
            assert await header_locator.is_visible(), (
                "Header not visible after XSS test; UI may be in a broken state."
            )
    except PlaywrightError as exc:
        pytest.fail(f"UI appears unresponsive after XSS test: {exc}")