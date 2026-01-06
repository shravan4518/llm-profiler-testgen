import asyncio
import json
from typing import Any, Dict, List

import pytest
from playwright.async_api import Page, Response, Error


@pytest.mark.asyncio
async def test_tc_015_readonly_cannot_modify_snmp_traps(
    authenticated_page: Page, browser
) -> None:
    """
    TC_015: Verify security - unauthorized (ReadOnly) user cannot modify SNMP trap configuration.

    Preconditions:
        - Profiler RBAC configured with Admin and ReadOnly roles.
        - ReadOnly user: viewer_user / Viewer#123 (handled by authenticated_page fixture).

    Steps:
        1. Log into Profiler UI as viewer_user (handled by fixture).
        2. Navigate to SNMP device configuration page.
        3. Attempt to add a new SNMP device (if "Add" visible).
        4. Attempt to edit an existing SNMP device trap settings (if edit option visible).
        5. Attempt to save configuration changes.
        6. Attempt a direct POST/PUT via UI actions and assert backend authorization error.

    Expected Results:
        - ReadOnly user can view SNMP/trap configuration but cannot edit or add entries.
        - Add/Save controls are disabled or hidden.
        - Any attempted change results in authorization error from backend
          and configuration remains unchanged.
    """

    page: Page = authenticated_page

    # ----------------------------------------------------------------------
    # Step 2: Navigate to Profiler Configuration → SNMP device configuration
    # ----------------------------------------------------------------------
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi",
            wait_until="networkidle",
        )
    except Error as exc:
        pytest.fail(f"Failed to load Profiler welcome page: {exc}")

    # The exact navigation selectors will depend on the real UI.
    # These are example locators that should be adapted to the AUT.
    try:
        # Open configuration menu
        await page.click("text=Profiler Configuration")
        # Navigate to Network Infrastructure Device Collector
        await page.click("text=Network Infrastructure Device Collector")
        # Navigate to SNMP device configuration page
        await page.click("text=SNMP Device Configuration")
    except Error as exc:
        pytest.fail(f"Failed to navigate to SNMP device configuration page: {exc}")

    # Wait for SNMP configuration table/grid to be visible
    snmp_table_locator = page.locator("table#snmpDevicesTable")
    await snmp_table_locator.wait_for(state="visible", timeout=15000)

    # Helper: capture current device list (for later comparison)
    async def get_current_snmp_devices() -> List[Dict[str, Any]]:
        """
        Extracts SNMP device rows from the table as a list of dictionaries.
        This is a UI-based snapshot to verify no changes occur.
        """
        devices = []
        rows = snmp_table_locator.locator("tbody tr")
        row_count = await rows.count()

        for i in range(row_count):
            row = rows.nth(i)
            # Adjust selectors/columns as appropriate for AUT
            device_name = await row.locator("td:nth-child(1)").inner_text()
            ip_address = await row.locator("td:nth-child(2)").inner_text()
            trap_enabled = await row.locator("td:nth-child(3)").inner_text()
            devices.append(
                {
                    "name": device_name.strip(),
                    "ip": ip_address.strip(),
                    "trap_enabled": trap_enabled.strip(),
                }
            )
        return devices

    baseline_devices = await get_current_snmp_devices()

    # ----------------------------------------------------------------------
    # Step 3: Attempt to add a new SNMP device (UI controls)
    # ----------------------------------------------------------------------
    add_button = page.locator("button#addSnmpDevice, text=Add SNMP Device, text=Add")

    add_visible = await add_button.is_visible()
    add_enabled = False
    if add_visible:
        add_enabled = await add_button.is_enabled()

    # Assert that readonly user cannot effectively use "Add" button
    # It may be hidden OR disabled.
    assert not (add_visible and add_enabled), (
        "ReadOnly user should not have an enabled 'Add' button for SNMP devices. "
        f"Visible={add_visible}, Enabled={add_enabled}"
    )

    # If the button is visible but disabled, attempt a click and ensure it does not open a form
    if add_visible and not add_enabled:
        try:
            await add_button.click(force=True)
        except Error:
            # Expected: click may be blocked; ensure no modal/form appears
            pass

        add_modal = page.locator("#snmpDeviceAddModal, .snmp-add-dialog")
        assert not await add_modal.is_visible(), (
            "Add SNMP device modal should not be visible for ReadOnly user."
        )

    # ----------------------------------------------------------------------
    # Step 4: Attempt to edit an existing SNMP device’s trap settings
    # ----------------------------------------------------------------------
    # We assume there is at least one device; if not, this part is skipped.
    row_count = await snmp_table_locator.locator("tbody tr").count()
    if row_count > 0:
        first_row = snmp_table_locator.locator("tbody tr").nth(0)
        edit_button = first_row.locator(
            "button[title='Edit'], a[title='Edit'], text=Edit"
        )

        edit_visible = await edit_button.is_visible()
        edit_enabled = False
        if edit_visible:
            edit_enabled = await edit_button.is_enabled()

        # ReadOnly user should not be able to perform edit
        assert not (edit_visible and edit_enabled), (
            "ReadOnly user should not have an enabled 'Edit' control for SNMP devices. "
            f"Visible={edit_visible}, Enabled={edit_enabled}"
        )

        if edit_visible and not edit_enabled:
            try:
                await edit_button.click(force=True)
            except Error:
                # Expected: click may be blocked; ensure no edit form appears
                pass

            edit_modal = page.locator("#snmpDeviceEditModal, .snmp-edit-dialog")
            assert not await edit_modal.is_visible(), (
                "Edit SNMP device modal should not be visible for ReadOnly user."
            )

    # ----------------------------------------------------------------------
    # Step 5: Attempt to save any configuration changes (if possible)
    # ----------------------------------------------------------------------
    # Some UIs may always show a global "Save" button; ensure it is disabled or hidden.
    save_button = page.locator("button#saveSnmpConfig, text=Save, text=Apply")
    save_visible = await save_button.is_visible()
    save_enabled = False
    if save_visible:
        save_enabled = await save_button.is_enabled()

    assert not (save_visible and save_enabled), (
        "ReadOnly user should not have an enabled 'Save' button for SNMP configuration. "
        f"Visible={save_visible}, Enabled={save_enabled}"
    )

    if save_visible and not save_enabled:
        try:
            await save_button.click(force=True)
        except Error:
            # Expected: click may be blocked; ensure no success notification appears
            pass

        success_toast = page.locator(".toast-success, .notification-success")
        # Expect no success notification about configuration being saved
        assert not await success_toast.is_visible(), (
            "ReadOnly user should not see a success message for saving SNMP configuration."
        )

    # ----------------------------------------------------------------------
    # Step 6: Attempt to POST changes via network request interception
    # ----------------------------------------------------------------------
    # We cannot directly craft HTTP calls with Playwright's Page,
    # but we can listen for any save/update request triggered by UI actions
    # and assert that backend returns an authorization error if such a request occurs.

    # This section is defensive: if the UI allows any save attempt,
    # we capture the response and verify it is unauthorized.

    snmp_update_responses: List[Response] = []

    def _capture_snmp_responses(response: Response) -> None:
        try:
            url = response.url.lower()
            if any(
                endpoint in url
                for endpoint in [
                    "/api/snmp",
                    "/snmp/update",
                    "/snmp/save",
                    "/snmp/devices",
                ]
            ):
                snmp_update_responses.append(response)
        except Exception:
            # Do not break the test if logging fails
            pass

    page.on("response", _capture_snmp_responses)

    # Try to trigger any possible save/update from UI, if controls exist
    # (This is a best-effort attempt; readonly should prevent this anyway.)
    if save_visible:
        try:
            await save_button.click(force=True)
            # Give some time for any network calls to complete
            await asyncio.sleep(2)
        except Error:
            # Expected: click may fail or do nothing
            pass

    # Validate captured responses (if any) are unauthorized
    for resp in snmp_update_responses:
        status = resp.status
        body_text = ""
        try:
            body_text = await resp.text()
        except Error:
            body_text = ""

        # Typical unauthorized/forbidden codes: 401 or 403
        assert status in (401, 403), (
            "Backend should return authorization error for ReadOnly user attempting "
            f"SNMP configuration change. Got status {status} for URL {resp.url}."
        )

        # Optionally inspect response body for auth error message
        if body_text:
            try:
                body_json = json.loads(body_text)
                message = str(body_json.get("message", "")).lower()
            except (ValueError, TypeError):
                message = body_text.lower()

            assert any(
                keyword in message
                for keyword in [
                    "unauthorized",
                    "forbidden",
                    "not allowed",
                    "insufficient privileges",
                    "permission",
                ]
            ), (
                "Authorization error message should be present in backend response "
                f"for URL {resp.url}. Response body: {body_text}"
            )

    # ----------------------------------------------------------------------
    # Postcondition: Verify SNMP configuration remains unchanged
    # ----------------------------------------------------------------------
    final_devices = await get_current_snmp_devices()
    assert final_devices == baseline_devices, (
        "SNMP device and trap configuration should remain unchanged for "
        "ReadOnly user after attempted modifications."
    )

    # Note: Verification of audit logs (if implemented) would require
    # access to log UI or backend; that is outside the scope of this UI test.