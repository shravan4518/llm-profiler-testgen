import asyncio
import re
from typing import Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
async def test_TC_021_profiler_name_xss_sanitization(
    authenticated_page: Page, browser: Browser
) -> None:
    """
    TC_021: Input sanitization on Profiler Name to prevent XSS.

    Steps:
        1. Log in as `ppsadmin`.  (handled by authenticated_page fixture)
        2. Navigate to Basic Configuration page.
        3. Set Profiler Name to `<script>alert('xss')</script>`.
        4. Click `Save Changes`.
        5. Reload the page and observe how Profiler Name is rendered.
        6. Navigate to any page where Profiler Name may be displayed
           (breadcrumbs, headers, etc.).

    Expected:
        - System either rejects the value or encodes it; script tags are not executed.
        - No alert pop-ups or script execution occurs.
        - Stored/displayed value is escaped or sanitized (e.g.,
          `&lt;script&gt;alert('xss')&lt;/script&gt;`).
    """

    page: Page = authenticated_page

    # -----------------------------
    # Test data
    # -----------------------------
    malicious_value: str = "<script>alert('xss')</script>"
    expected_encoded_pattern = re.compile(
        r"&lt;script&gt;.*alert\('xss'\).*&lt;/script&gt;", re.IGNORECASE
    )

    # -----------------------------
    # Helper: wait for unexpected alert (XSS symptom)
    # -----------------------------
    alert_triggered = False
    alert_message: Optional[str] = None

    async def dialog_handler(dialog) -> None:
        nonlocal alert_triggered, alert_message
        alert_triggered = True
        alert_message = dialog.message
        # Dismiss any unexpected alert to keep test running
        await dialog.dismiss()

    page.on("dialog", dialog_handler)

    # -----------------------------
    # Step 2: Navigate to Basic Configuration page
    # -----------------------------
    # NOTE: Selectors are placeholders and should be updated
    #       to match the real application under test.
    try:
        # Example: navigate via menu or direct URL if known
        # await page.goto("https://10.34.50.201/dana-na/admin/basic_config.cgi")
        await page.click("text=Configuration")
        await page.click("text=Basic Configuration")
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to Basic Configuration page: {exc}")

    # -----------------------------
    # Step 3: Set Profiler Name to malicious XSS value
    # -----------------------------
    profiler_name_selector = "input[name='profilerName']"  # Placeholder selector

    try:
        await page.wait_for_selector(profiler_name_selector, state="visible", timeout=10_000)
        await page.fill(profiler_name_selector, malicious_value)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to locate or fill Profiler Name field: {exc}")

    # -----------------------------
    # Step 4: Click "Save Changes"
    # -----------------------------
    save_button_selector = "button:has-text('Save Changes')"  # Placeholder selector

    try:
        async with page.expect_navigation(wait_until="networkidle", timeout=20_000):
            await page.click(save_button_selector)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to save changes on Basic Configuration page: {exc}")

    # -----------------------------
    # Step 5: Reload page and inspect Profiler Name rendering
    # -----------------------------
    try:
        await page.reload(wait_until="networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to reload Basic Configuration page: {exc}")

    # Get the stored value from the input field after reload
    try:
        await page.wait_for_selector(profiler_name_selector, state="visible", timeout=10_000)
        stored_value = await page.get_attribute(profiler_name_selector, "value")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to read Profiler Name after reload: {exc}")

    # Assert that no raw script tag is stored directly
    assert stored_value is not None, "Profiler Name value should not be None after reload."

    # It is acceptable if the system rejects the value (e.g., empty or sanitized),
    # but it must not store the raw script tags.
    assert "<script" not in stored_value.lower(), (
        "Profiler Name field stored raw <script> tag, which is unsafe and indicates XSS risk."
    )

    # If the value is encoded, it should not execute as HTML/JS.
    # Optional: check for encoded representation if the system supports it.
    if "&lt;script&gt;" in stored_value.lower():
        assert expected_encoded_pattern.search(stored_value) is not None, (
            "Profiler Name appears encoded but does not match expected sanitized pattern."
        )

    # -----------------------------
    # Step 6: Navigate to a page where Profiler Name is displayed
    # -----------------------------
    # Example: assume Profiler Name appears in header or breadcrumb
    try:
        # Navigate to a representative page where the Profiler Name is rendered
        await page.click("text=Dashboard")  # Placeholder selector
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to navigate to page where Profiler Name is displayed: {exc}")

    # Locator where Profiler Name is displayed (e.g., header, breadcrumb)
    profiler_display_selector = "header .profiler-name, .breadcrumb .profiler-name"
    try:
        profiler_display_element = await page.wait_for_selector(
            profiler_display_selector, state="visible", timeout=10_000
        )
        rendered_text = await profiler_display_element.inner_text()
        rendered_html = await profiler_display_element.inner_html()
    except PlaywrightError as exc:
        pytest.fail(f"Failed to locate rendered Profiler Name on display page: {exc}")

    # -----------------------------
    # Assertions: No script execution / proper sanitization
    # -----------------------------

    # 1) Assert no alert dialog (XSS) was triggered
    # Wait a short period to ensure any automatic script execution would have occurred
    await asyncio.sleep(2)
    assert not alert_triggered, (
        f"Unexpected JavaScript alert was triggered, indicating possible XSS. "
        f"Alert message: {alert_message!r}"
    )

    # 2) Assert that raw script tags are not rendered as HTML
    assert "<script" not in rendered_html.lower(), (
        "Profiler Name is rendered as raw <script> HTML, which is unsafe."
    )

    # 3) Assert that user-facing text is safe (no script tags in text)
    assert "<script" not in rendered_text.lower(), (
        "Profiler Name text contains '<script', indicating unsafe rendering."
    )

    # 4) If encoded script is shown, ensure it is escaped (visible as text, not executed)
    if "&lt;script&gt;" in rendered_html.lower():
        assert expected_encoded_pattern.search(rendered_html) is not None, (
            "Profiler Name appears encoded but does not match expected sanitized pattern "
            "in the rendered HTML."
        )

    # -----------------------------
    # Postcondition: System remains secure
    # -----------------------------
    # Additional safety check: attempt to trigger any remaining dialogs
    await asyncio.sleep(1)
    assert not alert_triggered, (
        "System shows evidence of XSS after navigation; security must be reviewed."
    )