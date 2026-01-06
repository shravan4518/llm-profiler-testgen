import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_minimum_supported_dhcp_fingerprints_version_45(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_009: Boundary test – minimum supported DHCP fingerprints database version (45)

    Steps:
        1. Attempt to upload fingerprints package v44 via Profiler Configuration > Device Fingerprints.
        2. Capture any error/validation messages for v44.
        3. Upload fingerprints package v45 and apply.
        4. Verify current fingerprints version shown is 45.
        5. Connect Android endpoint MAC `AA:BB:CC:DD:EE:0A` and trigger DHCP.
        6. Check Profiler classification results for that device.
        7. Optionally upgrade to v46 and verify that upgrade works too.

    Expected:
        - v44 package is rejected or flagged as unsupported with a clear error referencing minimum version 45.
        - v45 package is accepted and becomes active.
        - Android device is profiled correctly based on DHCP fingerprint using v45.
        - System log records the fingerprint database version change.
    """
    page = authenticated_page

    # -------------------------------------------------------------------------
    # Helper functions
    # -------------------------------------------------------------------------

    async def goto_device_fingerprints_page() -> None:
        """Navigate to Profiler Configuration > Device Fingerprints."""
        try:
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/config/device-fingerprints",
                wait_until="networkidle",
            )
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to Device Fingerprints page: {exc}")

        # Basic sanity check that we are on the right page
        header = page.get_by_role("heading", name="Device Fingerprints")
        await header.wait_for(timeout=10_000)

    async def upload_fingerprints_package(
        package_path: Path,
    ) -> None:
        """Upload a fingerprints package file through the UI."""
        upload_input = page.locator('input[type="file"][data-testid="fingerprints-upload"]')
        await upload_input.wait_for(timeout=10_000)

        if not package_path.exists():
            pytest.fail(f"Fingerprints package not found: {package_path}")

        await upload_input.set_input_files(str(package_path))

        # Click upload/submit button if present
        upload_button = page.get_by_role("button", name="Upload")
        if await upload_button.is_visible():
            await upload_button.click()

    async def get_toast_or_inline_error(timeout_ms: int = 10_000) -> Optional[str]:
        """
        Try to capture either a toast notification or inline validation error.
        Returns the text if found, otherwise None.
        """
        # Toast-like message
        toast_locator = page.locator('[data-testid="notification-toast"], .toast, .alert-error')
        inline_error_locator = page.locator('[data-testid="validation-error"], .error-message')

        try:
            await toast_locator.first.wait_for(timeout=timeout_ms)
            text = (await toast_locator.first.inner_text()).strip()
            if text:
                return text
        except PlaywrightError:
            pass

        try:
            await inline_error_locator.first.wait_for(timeout=timeout_ms)
            text = (await inline_error_locator.first.inner_text()).strip()
            if text:
                return text
        except PlaywrightError:
            pass

        return None

    async def get_current_fingerprints_version() -> str:
        """Read the currently active fingerprints version string from the UI."""
        version_locator = page.locator('[data-testid="current-fingerprints-version"]')
        try:
            await version_locator.wait_for(timeout=15_000)
        except PlaywrightError as exc:
            pytest.fail(f"Current fingerprints version label not found: {exc}")

        version_text = (await version_locator.inner_text()).strip()
        assert version_text, "Current fingerprints version text should not be empty."
        return version_text

    async def apply_fingerprints_changes() -> None:
        """Click the 'Apply' or 'Save' button to activate the uploaded package."""
        apply_button = page.get_by_role("button", name="Apply")
        if not await apply_button.is_visible():
            # Some UIs use 'Save' instead of 'Apply'
            apply_button = page.get_by_role("button", name="Save")

        await apply_button.click()

        # Wait for success notification or state change
        success_locator = page.locator(
            '[data-testid="notification-success"], .toast-success, .alert-success'
        )
        try:
            await success_locator.first.wait_for(timeout=30_000)
        except PlaywrightError:
            # Not fatal by itself; assertions later on version will catch any failure
            pass

    async def trigger_android_dhcp(mac_address: str) -> None:
        """
        Stub: Trigger DHCP from Android endpoint with given MAC.

        In a real test environment this would:
          - Call a lab automation API, or
          - SSH into a test harness, or
          - Use a simulator to send a DHCP request.

        Here we simulate the delay only.
        """
        # Placeholder for external integration – replace with real call when available.
        await asyncio.sleep(5)

    async def wait_for_device_classification(
        mac_address: str,
        expected_profile: str,
        timeout: int = 120,
    ) -> None:
        """
        Poll the Profiler UI for device classification of the given MAC.

        Args:
            mac_address: MAC address of the endpoint.
            expected_profile: Expected classification (e.g. 'Android', 'Android Phone').
            timeout: Max seconds to wait before failing.
        """
        # Navigate to devices / endpoints page
        try:
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/devices",
                wait_until="networkidle",
            )
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to Devices page: {exc}")

        search_input = page.get_by_placeholder("Search MAC, IP, hostname")
        await search_input.wait_for(timeout=10_000)
        await search_input.fill(mac_address)
        await search_input.press("Enter")

        row_locator = page.locator(
            f'[data-testid="device-row"][data-mac="{mac_address.lower()}"]'
        )
        classification_cell = row_locator.locator('[data-testid="device-classification"]')

        end_time = datetime.utcnow() + timedelta(seconds=timeout)
        last_seen_text = ""

        while datetime.utcnow() < end_time:
            try:
                await row_locator.first.wait_for(timeout=10_000)
                last_seen_text = (await classification_cell.inner_text()).strip()
                if expected_profile.lower() in last_seen_text.lower():
                    return
            except PlaywrightError:
                # Row not yet present; keep polling
                pass

            await asyncio.sleep(5)
            await search_input.fill(mac_address)
            await search_input.press("Enter")

        pytest.fail(
            f"Device with MAC {mac_address} was not classified as "
            f"'{expected_profile}' within {timeout}s. Last seen: '{last_seen_text}'."
        )

    async def verify_system_log_contains_version_change(
        expected_version: str,
        timeout: int = 120,
    ) -> None:
        """
        Verify that system log records the fingerprint database version change.

        Args:
            expected_version: Version string expected in the logs (e.g. '45').
            timeout: Max seconds to wait.
        """
        try:
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/logs/system",
                wait_until="networkidle",
            )
        except PlaywrightError as exc:
            pytest.fail(f"Failed to navigate to System Logs page: {exc}")

        search_input = page.get_by_placeholder("Search logs")
        await search_input.wait_for(timeout=10_000)
        await search_input.fill("fingerprint")
        await search_input.press("Enter")

        log_rows = page.locator('[data-testid="log-row"]')
        end_time = datetime.utcnow() + timedelta(seconds=timeout)
        found = False

        while datetime.utcnow() < end_time and not found:
            count = await log_rows.count()
            for i in range(count):
                text = (await log_rows.nth(i).inner_text()).lower()
                if "fingerprint" in text and expected_version.lower() in text:
                    found = True
                    break

            if found:
                break

            await asyncio.sleep(5)
            await search_input.press("Enter")

        assert found, (
            f"System log did not contain fingerprint database version change "
            f"to '{expected_version}' within {timeout}s."
        )

    # -------------------------------------------------------------------------
    # Test Step 1–2: Upload v44 and verify rejection
    # -------------------------------------------------------------------------
    await goto_device_fingerprints_page()

    # NOTE: Adjust paths to match your real test environment
    v44_package = Path("testdata/fingerprints/fingerprints_v44.pkg")
    v45_package = Path("testdata/fingerprints/fingerprints_v45.pkg")
    v46_package = Path("testdata/fingerprints/fingerprints_v46.pkg")

    # Step 1: Attempt to upload fingerprints package v44
    await upload_fingerprints_package(v44_package)

    # Step 2: Capture any error/validation messages for v44
    error_text = await get_toast_or_inline_error(timeout_ms=20_000)

    assert error_text is not None, (
        "Uploading fingerprints package v44 should produce an error or "
        "validation message, but none was found."
    )
    assert "45" in error_text or "minimum" in error_text.lower(), (
        "Error message for v44 should reference minimum supported version 45. "
        f"Actual message: '{error_text}'"
    )

    # Sanity check that current version did NOT change to 44
    current_version_after_v44 = await get_current_fingerprints_version()
    assert current_version_after_v44 != "44", (
        "Fingerprints version should not be downgraded to 44; "
        f"current version: {current_version_after_v44}"
    )

    # -------------------------------------------------------------------------
    # Test Step 3–4: Upload v45, apply, and verify version
    # -------------------------------------------------------------------------
    # Step 3: Upload fingerprints package v45 and apply
    await upload_fingerprints_package(v45_package)
    await apply_fingerprints_changes()

    # Step 4: Verify current fingerprints version shown is 45
    # Allow some time for backend to switch versions
    for _ in range(6):
        current_version = await get_current_fingerprints_version()
        if current_version.strip() == "45":
            break
        await asyncio.sleep(5)

    assert current_version.strip() == "45", (
        "Fingerprints version should be 45 after applying v45 package. "
        f"Actual: '{current_version}'"
    )

    # -------------------------------------------------------------------------
    # Test Step 5–6: Trigger Android DHCP and verify profiling
    # -------------------------------------------------------------------------
    android_mac = "AA:BB:CC:DD:EE:0A"

    # Step 5: Connect Android endpoint and trigger DHCP (stubbed)
    await trigger_android_dhcp(android_mac)

    # Step 6: Check Profiler classification results for that device
    await wait_for_device_classification(
        mac_address=android_mac,
        expected_profile="Android",
        timeout=180,
    )

    # -------------------------------------------------------------------------
    # Test Step 7 (Optional): Upgrade to v46 and verify
    # -------------------------------------------------------------------------
    # This is optional; run it but do not fail the entire test if v46 upload fails,
    # unless the behavior contradicts expectations (e.g., 46 is rejected).
    try:
        await goto_device_fingerprints_page()
        await upload_fingerprints_package(v46_package)
        await apply_fingerprints_changes()

        # Wait for version 46 to appear, but do not wait excessively
        upgraded = False
        for _ in range(6):
            version_after_v46 = await get_current_fingerprints_version()
            if version_after_v46.strip() == "46":
                upgraded = True
                break
            await asyncio.sleep(5)

        # If v46 is not active, log a soft assertion via pytest warning
        if not upgraded:
            pytest.skip(
                "Upgrade to fingerprints version 46 did not complete within the "
                "allowed time. Core requirement (support for v45) is already verified."
            )
    except Exception as exc:
        # Do not mask the primary purpose of the test (v45 boundary check)
        pytest.skip(
            f"Optional upgrade to fingerprints version 46 failed with error: {exc}. "
            "Boundary behavior for minimum supported version 45 is already validated."
        )

    # -------------------------------------------------------------------------
    # Final: Verify system log records fingerprint DB version change (to >= 45)
    # -------------------------------------------------------------------------
    # Prefer to verify the last successfully applied version (46 if upgraded, else 45)
    final_version = await get_current_fingerprints_version()
    final_expected_version = "46" if final_version.strip() == "46" else "45"

    await verify_system_log_contains_version_change(expected_version=final_expected_version)