import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.medium
async def test_forward_and_sync_endpoint_data_to_remote_profiler(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_013: Integration – Forward and sync endpoint data to remote Profiler/PPS

    Validate that DHCP-based profiling results from a local Profiler are
    forwarded/synchronized correctly to a remote Profiler/PPS instance.

    Preconditions (assumed satisfied by environment/configuration):
        - Local PPS with Profiler enabled and DHCP sniffing configured.
        - Remote PPS/PCS/profiler server configured and reachable.
        - Forward & Sync Endpoint Data feature available on both systems.

    This test:
        1. Verifies local Profiler is capturing DHCP for local VLANs.
        2. Configures local Profiler to forward/sync endpoint data to remote PPS.
        3. Configures remote PPS to accept endpoint data.
        4. Simulates/assumes an endpoint with MAC AA:BB:CC:DD:EE:12 appears via DHCP.
        5. Confirms local Profiler discovery and classification.
        6. Confirms endpoint appears on remote PPS with synchronized attributes
           within the expected sync interval.
    """

    # ----------------------------------------------------------------------
    # Test configuration / constants
    # ----------------------------------------------------------------------
    base_url = "https://npre-miiqa2mp-eastus2.openai.azure.com/"
    local_profiler_url = f"{base_url}local-profiler"
    remote_profiler_url = f"{base_url}remote-profiler"

    # MAC address to verify
    target_mac = "AA:BB:CC:DD:EE:12"

    # Expected sync interval (seconds) + small buffer
    sync_interval_seconds = 60
    max_wait_seconds = sync_interval_seconds + 30

    # ----------------------------------------------------------------------
    # Helper functions
    # ----------------------------------------------------------------------
    async def safe_click(page: Page, selector: str, description: str) -> None:
        """Click an element with error handling and descriptive failures."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            await page.click(selector)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(f"Timed out waiting to click {description} ({selector})") from exc
        except Exception as exc:
            raise AssertionError(f"Failed to click {description} ({selector}): {exc}") from exc

    async def safe_fill(page: Page, selector: str, value: str, description: str) -> None:
        """Fill an input field with error handling and descriptive failures."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            await page.fill(selector, value)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(f"Timed out waiting to fill {description} ({selector})") from exc
        except Exception as exc:
            raise AssertionError(f"Failed to fill {description} ({selector}): {exc}") from exc

    async def assert_text_present(page: Page, text: str, description: str) -> None:
        """Assert that specific text is present on the page."""
        try:
            await page.wait_for_timeout(500)  # small delay for UI rendering
            locator = page.get_by_text(text, exact=False)
            await locator.wait_for(state="visible", timeout=10000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(f"Expected text not found for {description}: '{text}'") from exc

    async def wait_for_condition(condition_fn, timeout_seconds: int, poll_interval: float = 2.0):
        """
        Poll condition_fn until it returns True or timeout expires.

        condition_fn must be an async function returning bool.
        """
        end_time = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        last_error = None

        while datetime.utcnow() < end_time:
            try:
                if await condition_fn():
                    return True
            except AssertionError as exc:
                # Capture assertion errors but keep retrying until timeout
                last_error = exc
            await asyncio.sleep(poll_interval)

        if last_error:
            raise AssertionError(
                f"Condition not met within {timeout_seconds} seconds: {last_error}"
            )
        raise AssertionError(f"Condition not met within {timeout_seconds} seconds")

    # ----------------------------------------------------------------------
    # STEP 1: On local PPS, ensure Profiler is capturing DHCP for local VLANs.
    # ----------------------------------------------------------------------
    page = authenticated_page

    await page.goto(local_profiler_url, wait_until="networkidle")

    # Navigate to Profiler / DHCP capture configuration page
    # NOTE: Selectors are placeholders and should be updated to match real UI.
    await safe_click(
        page,
        "nav >> text=Profiler",
        "Profiler navigation tab",
    )
    await safe_click(
        page,
        "nav >> text=DHCP Sniffing",
        "DHCP Sniffing configuration tab",
    )

    # Assert that DHCP sniffing is enabled for local VLANs
    dhcp_sniffing_toggle = page.locator("input[data-testid='dhcp-sniffing-toggle']")
    try:
        await dhcp_sniffing_toggle.wait_for(state="attached", timeout=10000)
        is_checked = await dhcp_sniffing_toggle.is_checked()
    except PlaywrightTimeoutError as exc:
        raise AssertionError("DHCP sniffing toggle not found on local Profiler page") from exc

    assert is_checked, "DHCP sniffing must be enabled on local Profiler for local VLANs"

    # Optional: verify VLAN list is non-empty (indicating local VLANs monitored)
    vlan_rows = page.locator("table[data-testid='dhcp-vlan-table'] tbody tr")
    vlan_count = await vlan_rows.count()
    assert vlan_count > 0, "Expected at least one VLAN configured for DHCP sniffing"

    # ----------------------------------------------------------------------
    # STEP 2: Configure Forward and Sync Endpoint Data on local PPS.
    # ----------------------------------------------------------------------
    await safe_click(
        page,
        "nav >> text=Forward and Sync Endpoint Data",
        "Forward and Sync Endpoint Data tab",
    )

    # Enable forwarding to remote PPS and set remote endpoint details.
    forward_toggle = page.locator("input[data-testid='forward-sync-toggle']")
    if not await forward_toggle.is_checked():
        await forward_toggle.check()

    # Configure remote PPS address / profile (placeholder selectors)
    await safe_fill(
        page,
        "input[data-testid='remote-pps-host']",
        "remote-pps.example.com",
        "Remote PPS host field",
    )
    await safe_fill(
        page,
        "input[data-testid='remote-pps-port']",
        "443",
        "Remote PPS port field",
    )

    # Save configuration
    await safe_click(
        page,
        "button[data-testid='forward-sync-save']",
        "Forward and Sync configuration save button",
    )

    # Assert that configuration saved successfully
    await assert_text_present(
        page,
        "Forward and Sync configuration saved",
        "Forward & Sync save confirmation",
    )

    # ----------------------------------------------------------------------
    # STEP 3: On remote PPS, configure to accept and store endpoint data.
    # ----------------------------------------------------------------------
    remote_context = await browser.new_context()
    remote_page = await remote_context.new_page()

    try:
        await remote_page.goto(remote_profiler_url, wait_until="networkidle")

        # If separate authentication is required for remote PPS, it should be done here.
        # For this example, we assume SSO or pre-authenticated context.

        await safe_click(
            remote_page,
            "nav >> text=Profiler",
            "Remote Profiler navigation tab",
        )
        await safe_click(
            remote_page,
            "nav >> text=Endpoint Data Sync",
            "Remote Endpoint Data Sync tab",
        )

        # Ensure remote PPS is configured to accept endpoint data
        accept_toggle = remote_page.locator("input[data-testid='accept-endpoint-data-toggle']")
        if not await accept_toggle.is_checked():
            await accept_toggle.check()

        await safe_click(
            remote_page,
            "button[data-testid='endpoint-sync-save']",
            "Remote endpoint sync save button",
        )

        await assert_text_present(
            remote_page,
            "Endpoint data synchronization settings saved",
            "Remote endpoint sync save confirmation",
        )

        # ------------------------------------------------------------------
        # STEP 4: Connect endpoint MAC AA:BB:CC:DD:EE:12 and trigger DHCP.
        # ------------------------------------------------------------------
        # NOTE: This step typically involves physical/virtual network actions.
        # Here we assume an external test harness triggers the DHCP event,
        # or that the environment is pre-seeded. We simply wait a short
        # period to allow the local Profiler to capture DHCP.
        await page.bring_to_front()
        await page.wait_for_timeout(5000)  # small buffer for DHCP capture

        # ------------------------------------------------------------------
        # STEP 5: Confirm that local Profiler discovers and classifies the device.
        # ------------------------------------------------------------------
        await safe_click(
            page,
            "nav >> text=Endpoints",
            "Local endpoints listing tab",
        )

        # Search for the target MAC in local Profiler
        await safe_fill(
            page,
            "input[data-testid='endpoint-search']",
            target_mac,
            "Local endpoint search field",
        )
        await safe_click(
            page,
            "button[data-testid='endpoint-search-button']",
            "Local endpoint search button",
        )

        # Assert that local endpoint row appears with classification
        local_endpoint_row = page.locator(
            "table[data-testid='endpoint-table'] tbody tr",
        ).filter(has_text=target_mac)

        try:
            await local_endpoint_row.wait_for(state="visible", timeout=30000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(
                f"Local Profiler did not discover endpoint with MAC {target_mac} "
                "within 30 seconds after DHCP trigger."
            ) from exc

        # Verify DHCP and classification columns are populated
        dhcp_details_cell = local_endpoint_row.locator("td[data-testid='dhcp-details']")
        classification_cell = local_endpoint_row.locator("td[data-testid='classification']")

        dhcp_text = (await dhcp_details_cell.text_content() or "").strip()
        classification_text = (await classification_cell.text_content() or "").strip()

        assert dhcp_text, "Local Profiler should record DHCP details for the endpoint"
        assert classification_text, "Local Profiler should classify the endpoint device"

        # ------------------------------------------------------------------
        # STEP 6: On remote PPS, navigate to endpoint/device listing.
        # STEP 7: Search for MAC AA:BB:CC:DD:EE:12 and verify sync.
        # ------------------------------------------------------------------
        await remote_page.bring_to_front()
        await safe_click(
            remote_page,
            "nav >> text=Endpoints",
            "Remote endpoints listing tab",
        )

        async def remote_endpoint_synced() -> bool:
            """Condition function to verify endpoint appears on remote PPS."""
            # Clear and re-search each poll to ensure latest data
            await safe_fill(
                remote_page,
                "input[data-testid='endpoint-search']",
                target_mac,
                "Remote endpoint search field",
            )
            await safe_click(
                remote_page,
                "button[data-testid='endpoint-search-button']",
                "Remote endpoint search button",
            )

            remote_row = remote_page.locator(
                "table[data-testid='endpoint-table'] tbody tr",
            ).filter(has_text=target_mac)

            try:
                await remote_row.wait_for(state="visible", timeout=10000)
            except PlaywrightTimeoutError:
                # Not found yet, let caller retry
                return False

            # Validate core synchronized attributes (placeholders)
            remote_mac_cell = remote_row.locator("td[data-testid='mac-address']")
            remote_classification_cell = remote_row.locator("td[data-testid='classification']")

            remote_mac_text = (await remote_mac_cell.text_content() or "").strip()
            remote_classification_text = (
                await remote_classification_cell.text_content() or ""
            ).strip()

            if remote_mac_text.lower() != target_mac.lower():
                raise AssertionError(
                    f"Remote endpoint MAC mismatch: expected {target_mac}, got {remote_mac_text}"
                )

            if not remote_classification_text:
                raise AssertionError(
                    "Remote endpoint is missing classification; expected synchronized classification."
                )

            # Additional attribute checks (e.g., IP, VLAN, profile) can be added here.

            return True

        # Wait up to max_wait_seconds for the endpoint to appear on remote PPS
        start_time = datetime.utcnow()
        await wait_for_condition(remote_endpoint_synced, timeout_seconds=max_wait_seconds)
        elapsed = (datetime.utcnow() - start_time).total_seconds()

        # Assert that sync delay is within the expected interval
        assert (
            elapsed <= max_wait_seconds
        ), f"Endpoint sync took too long: {elapsed:.1f}s (limit {max_wait_seconds}s)"

    finally:
        # ------------------------------------------------------------------
        # Postconditions / Cleanup:
        # Forward & sync remains active for future endpoints.
        # We do NOT disable the feature, but we ensure contexts are closed.
        # ------------------------------------------------------------------
        await remote_context.close()