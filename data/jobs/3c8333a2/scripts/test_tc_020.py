import asyncio
import re
from contextlib import asynccontextmanager

import pytest
from playwright.async_api import Page, Browser, Dialog, Error


@pytest.mark.asyncio
async def test_tc_020_hostname_script_injection_validation(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_020: Security – input validation against script injection in hostname fields.

    This test verifies that hostname/server name fields do not introduce a stored XSS
    vulnerability when malicious script input is provided. It validates that:
      - The system either rejects the input with a validation error, OR
      - The input is safely sanitized/escaped when displayed in the UI.
      - No JavaScript alert or script execution occurs at any time.

    Prerequisites:
      - Admin user is already logged in via `authenticated_page` fixture.
      - User has permission to add/edit Device Attribute Server / Additional collector servers.
    """

    page = authenticated_page

    # Malicious payload to test for script injection
    malicious_hostname = "<script>alert('XSS')</script>"

    # A valid dummy value for other required fields (placeholders, to be adjusted to real app)
    valid_ip = "192.0.2.10"
    valid_port = "8080"
    valid_description = "XSS test server"

    # Helper context manager to detect any unexpected dialogs (alerts/confirm/prompt)
    @asynccontextmanager
    async def no_unexpected_dialogs(expected: bool = False):
        dialog_triggered = False

        async def dialog_handler(dialog: Dialog) -> None:
            nonlocal dialog_triggered
            dialog_triggered = True
            # Always dismiss any dialog to avoid blocking the test
            try:
                await dialog.dismiss()
            except Error:
                # Even if dismiss fails, we record that a dialog occurred
                pass

        page.on("dialog", dialog_handler)
        try:
            yield
        finally:
            page.off("dialog", dialog_handler)
            if not expected:
                # Assert that no dialog was triggered if none was expected
                assert (
                    dialog_triggered is False
                ), "Unexpected JavaScript dialog was triggered, possible XSS."

    # STEP 1: Navigate to page for adding a new Device Attribute Server.
    # NOTE: The actual navigation selectors/URLs are placeholders and should be
    #       adapted to the real application structure.
    with pytest.raises(AssertionError):
        # Ensure we start with no unexpected dialogs
        async with no_unexpected_dialogs():
            # Example: Navigate via menu to Device Attribute Servers page
            # Replace selectors with real ones from AUT.
            await page.goto(
                "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
                wait_until="networkidle",
            )

    # The above context is used only to enforce dialog protection during navigation.
    # Re-enter a clean no_unexpected_dialogs context for the rest of the test.
    async with no_unexpected_dialogs():
        # Example navigation: open configuration / device attribute servers
        # These selectors are placeholders and must be replaced with actual ones.
        try:
            # Wait for main admin landing page to load
            await page.wait_for_load_state("networkidle")

            # STEP 1 (continued): Navigate to Device Attribute Server listing page
            # Example: click on "Configuration" menu
            # await page.click("text=Configuration")
            # Example: click on "Device Attribute Servers"
            # await page.click("text=Device Attribute Servers")

            # TODO: Replace the below with real navigation steps.
            # For now, we assume we are already on the Device Attribute Server listing page.
            pass
        except Error as e:
            pytest.fail(f"Failed to navigate to Device Attribute Server page: {e}")

        # STEP 2: Click `Add Server`.
        try:
            # Replace with actual selector for Add Server button/link
            # Example: await page.click("button:has-text('Add Server')")
            await page.click("text=Add Server")
        except Error as e:
            pytest.fail(f"Failed to click 'Add Server' button: {e}")

        # STEP 3: In the hostname field, enter `<script>alert('XSS')</script>`.
        try:
            # Replace with actual selector for hostname/server name field
            # Example: hostname_input = page.locator('input[name="hostname"]')
            hostname_input = page.locator('input[name="hostname"]')
            await hostname_input.fill(malicious_hostname)
        except Error as e:
            pytest.fail(f"Failed to fill hostname field with malicious payload: {e}")

        # STEP 4: Fill other required fields with valid dummy data.
        try:
            # Replace with actual selectors for other required fields
            # Example IP field
            ip_input = page.locator('input[name="ipAddress"]')
            await ip_input.fill(valid_ip)

            # Example port field
            port_input = page.locator('input[name="port"]')
            await port_input.fill(valid_port)

            # Example description field
            description_input = page.locator('textarea[name="description"]')
            await description_input.fill(valid_description)
        except Error as e:
            pytest.fail(f"Failed to fill required fields with valid data: {e}")

        # STEP 5: Click `Save`.
        try:
            # Replace with actual selector for Save button
            # Example: await page.click("button:has-text('Save')")
            await page.click("text=Save")
        except Error as e:
            pytest.fail(f"Failed to click 'Save' button: {e}")

        # After clicking Save, one of two behaviors is expected:
        #   1) Input is rejected with a validation error; OR
        #   2) Input is accepted but sanitized/escaped on display.
        # We check for both cases.

        # Small wait for validation or navigation to complete
        await page.wait_for_timeout(1000)

        validation_error_locator = page.locator(
            "text=invalid characters"
        )  # Placeholder text
        has_validation_error = await validation_error_locator.is_visible()

        if has_validation_error:
            # CASE 1: System rejects the input with validation error
            error_text = await validation_error_locator.inner_text()
            assert re.search(
                r"invalid|not allowed|forbidden", error_text, re.IGNORECASE
            ), (
                "Validation error does not clearly indicate invalid/forbidden characters "
                f"in hostname. Actual message: '{error_text}'"
            )
        else:
            # CASE 2: System accepts entry but must sanitize/escape it.

            # STEP 6: Navigate back to listing page and verify how this entry is displayed.
            try:
                # Example navigation back to listing page if needed:
                # await page.click("text=Back to list")
                # For now, assume Save redirects automatically to listing.
                await page.wait_for_load_state("networkidle")
            except Error as e:
                pytest.fail(f"Failed to return to Device Attribute Server listing: {e}")

            # Locate the newly created entry in the list.
            # We expect that the raw `<script>` tags are NOT rendered as HTML.
            try:
                # This locator is a placeholder; adapt to actual table/list structure.
                # We look for a row containing either the raw text or a sanitized version.
                # The key point: the UI must not execute the script.
                new_row = page.locator("table >> text=alert('XSS')")
                is_row_visible = await new_row.first().is_visible()
                assert is_row_visible, (
                    "Newly created server with malicious hostname not found in listing. "
                    "Either the entry was not saved or the locator is incorrect."
                )

                # Fetch the text content to ensure it is not interpreted as HTML.
                row_text = await new_row.first().inner_text()

                # The raw `<script>` tag should appear as text, not execute.
                assert "<script>" in row_text or "&lt;script&gt;" in row_text, (
                    "Hostname with script tags is not visible as literal/sanitized text. "
                    "Potential silent stripping or unexpected behavior."
                )

                # Ensure there is no indication that HTML was executed.
                assert (
                    "</script>" in row_text or "&lt;/script&gt;" in row_text
                ), "Closing script tag not visible as text; verify sanitization behavior."

            except Error as e:
                pytest.fail(f"Failed to verify newly created server entry in listing: {e}")

        # Final assertion: Throughout the test, no JavaScript alert or dialog should occur.
        # This is enforced by the no_unexpected_dialogs context manager above.
        # If any dialog was triggered, the context manager would have raised an assertion.
        # No additional code needed here; reaching this point means no dialog occurred.