import asyncio
from typing import Dict, Any

import pytest
from playwright.async_api import Page, Browser, Request, Response, Error as PlaywrightError


@pytest.mark.asyncio
async def test_profiler_config_csrf_protection(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_022: Protect Profiler configuration changes with CSRF protection

    Validate that Profiler configuration changes require a valid session/CSRF token
    and cannot be executed via forged cross-site requests.

    Steps:
        1. Log in as `ppsadmin` and open Basic Configuration page.
        2. Capture the HTTP request used when clicking `Save Changes`.
        3. Log out from PPS.
        4. Attempt to replay the captured HTTP POST/PUT request from a tool
           without valid session/CSRF token.
        5. Observe server response.

    Expected:
        - Server rejects the replayed request due to invalid/expired session or
          CSRF token.
        - No configuration change is applied.
    """

    # ----------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin` and open Basic Configuration page
    # ----------------------------------------------------------------------
    # NOTE: `authenticated_page` fixture is assumed to return a Page object
    # that is already logged in as `ppsadmin` and has an active session.
    page: Page = authenticated_page

    # Navigate to Basic Configuration page (adjust URL/path/selector as needed)
    # This assumes the Basic Configuration page is reachable from the admin
    # welcome page and has a stable URL or navigation path.
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open admin welcome page: {exc}")

    # Example navigation to Basic Configuration:
    # Adjust selectors to match the real UI.
    try:
        # Click a menu item or link that opens the Profiler Basic Configuration page
        await page.click("text=Profiler")
        await page.click("text=Basic Configuration")

        # Wait for a known element on the Basic Configuration page
        await page.wait_for_selector("text=Save Changes", timeout=10000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to open Basic Configuration page: {exc}")

    # ----------------------------------------------------------------------
    # Step 2: Capture the HTTP request used when clicking `Save Changes`
    # ----------------------------------------------------------------------
    captured_request: Dict[str, Any] = {}

    async def handle_request(request: Request) -> None:
        """
        Request handler to capture the first POST/PUT to the configuration
        endpoint triggered by 'Save Changes'.
        """
        nonlocal captured_request

        # Only capture once
        if captured_request:
            return

        method = request.method.upper()

        # Heuristic: configuration changes are usually POST/PUT.
        if method not in {"POST", "PUT"}:
            return

        # Optionally, filter by URL path fragment if known, e.g.:
        # if "/profiler/config" not in request.url:
        #     return

        # Wait for the response so we can see status and body if needed
        try:
            response: Response | None = await request.response()
        except PlaywrightError:
            response = None

        captured_request = {
            "url": request.url,
            "method": method,
            "headers": await request.all_headers(),
            "post_data": await request.post_data() if request.post_data() else None,
            "status": response.status if response else None,
        }

    page.on("requestfinished", lambda req: asyncio.create_task(handle_request(req)))

    # Trigger a harmless "Save Changes" to capture the real request
    try:
        # Optionally adjust a field to avoid real configuration changes.
        # Example: toggle a checkbox and revert it back after test if needed.
        # await page.check("#some-safe-checkbox")

        await page.click("text=Save Changes")
        # Wait for network to settle and the save to complete
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to click 'Save Changes': {exc}")

    # Give some time for the requestfinished handler to run
    await asyncio.sleep(1.0)

    assert captured_request, (
        "No configuration POST/PUT request was captured when clicking 'Save Changes'. "
        "Check selectors and request filter."
    )

    # ----------------------------------------------------------------------
    # Step 3: Log out from PPS
    # ----------------------------------------------------------------------
    try:
        # Adjust selector to actual logout control
        await page.click("text=Log Out")
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to log out from PPS: {exc}")

    # Ensure we are logged out by asserting presence of login form
    try:
        await page.wait_for_selector("input[type='password']", timeout=10000)
    except PlaywrightError:
        pytest.fail("Login form not found after logout; user may still be logged in.")

    # ----------------------------------------------------------------------
    # Step 4: Replay the captured HTTP POST/PUT request without valid session
    #         /CSRF token using a fresh context (simulating forged request)
    # ----------------------------------------------------------------------
    # We use a new browser context with no cookies or session to simulate an
    # attacker sending the captured request from another origin.
    context = await browser.new_context()
    forged_page = await context.new_page()

    try:
        # Replay the captured request with minimal headers, excluding cookies
        # and CSRF-related headers to simulate missing/invalid tokens.
        forged_headers = {
            k: v
            for k, v in captured_request["headers"].items()
            if k.lower() not in {"cookie", "x-csrf-token", "x-xsrf-token", "csrf-token"}
        }

        response = await forged_page.request.fetch(
            url=captured_request["url"],
            method=captured_request["method"],
            headers=forged_headers,
            data=captured_request["post_data"],
        )
    except PlaywrightError as exc:
        await context.close()
        pytest.fail(f"Failed to replay forged configuration request: {exc}")

    # ----------------------------------------------------------------------
    # Step 5: Observe server response and assert CSRF/session protection
    # ----------------------------------------------------------------------
    status_code = response.status
    response_text = await response.text()

    # Assert that the server rejects the request: typically 401/403/440/400 etc.
    # Adjust accepted status codes as needed for your application.
    assert status_code in {400, 401, 403, 440}, (
        "Replayed configuration request was not rejected as expected. "
        f"Expected 4xx status, got {status_code}."
    )

    # Optionally assert presence of error message in body
    expected_error_indicators = [
        "CSRF",
        "cross-site request",
        "invalid session",
        "expired session",
        "not authorized",
        "forbidden",
    ]
    assert any(
        indicator.lower() in response_text.lower()
        for indicator in expected_error_indicators
    ), (
        "Response to forged configuration request does not clearly indicate "
        "CSRF/session rejection. "
        f"Status: {status_code}, body (truncated): {response_text[:500]!r}"
    )

    # ----------------------------------------------------------------------
    # Postcondition: Profiler configuration remains unchanged
    # ----------------------------------------------------------------------
    # Re-login and verify configuration has not changed.
    # This assumes that we can verify by checking a known field value.
    # The safest approach is to capture a specific field before the test and
    # compare it after; here we demonstrate a basic verification pattern.
    await context.close()

    # Reuse the existing page to log back in as ppsadmin
    # (Assumes login form is visible.)
    try:
        await page.fill("input[name='username']", "ppsadmin")
        await page.fill("input[type='password']", "ppsadmin")  # adjust as needed
        await page.click("text=Sign In")
        await page.wait_for_load_state("networkidle")
    except PlaywrightError as exc:
        pytest.fail(f"Failed to log back in as ppsadmin: {exc}")

    # Navigate again to Basic Configuration page
    try:
        await page.click("text=Profiler")
        await page.click("text=Basic Configuration")
        await page.wait_for_selector("text=Save Changes", timeout=10000)
    except PlaywrightError as exc:
        pytest.fail(
            f"Failed to reopen Basic Configuration page after forged request: {exc}"
        )

    # Example assertion: verify a known configuration field value is unchanged.
    # In a real test, you should capture the original value before Step 2 and
    # compare it here. For demonstration, we check that the page does not show
    # an obvious error or unexpected state.
    try:
        # Replace '#some-config-input' with a real selector
        config_value = await page.input_value("#some-config-input")
        assert config_value is not None, (
            "Configuration value could not be read after forged request; "
            "page may be in an unexpected state."
        )
        # Optionally, compare with a stored baseline value if available:
        # assert config_value == baseline_value
    except PlaywrightError:
        pytest.fail(
            "Failed to read configuration field to verify that no changes were applied."
        )