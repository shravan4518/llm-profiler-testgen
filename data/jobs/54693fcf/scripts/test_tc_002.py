import asyncio
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError


@pytest.mark.asyncio
async def test_tc_002_snmp_linkdown_marks_endpoint_disconnected(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_002: Verify Profiler processes SNMP linkDown trap to mark endpoint as disconnected.

    Preconditions:
        - Endpoint 00:11:22:33:44:55 is currently connected and visible in Profiler
          on switch port Gi1/0/10.
        - User is already authenticated via authenticated_page fixture.

    Steps:
        1. Confirm in Profiler UI that endpoint 00:11:22:33:44:55 is displayed as
           connected on Gi1/0/10.
        2. On the switch, shut down interface Gi1/0/10 (manual / external step).
        3. Using tcpdump or similar, confirm an SNMP linkDown trap is sent from
           10.10.20.10 to 10.10.10.50 (manual / external step).
        4. Wait for Profiler processing interval (if any) plus 30 seconds.
        5. Refresh the endpoint details page in Profiler.

    Expected:
        - Profiler receives and parses the linkDown trap.
        - Endpoint 00:11:22:33:44:55 remains in the inventory.
        - Endpoint status changes to “Disconnected” or equivalent.
        - The last-seen timestamp is updated to match the linkDown time.
        - The associated switch and port remain recorded for historical purposes.
    """
    page = authenticated_page
    endpoint_mac = "00:11:22:33:44:55"
    expected_switch_port = "Gi1/0/10"

    # NOTE: These selectors are examples/placeholders and must be adapted
    #       to the actual Profiler UI DOM structure.
    endpoint_search_input_selector = "input[data-testid='endpoint-search']"
    endpoint_row_selector = f"tr[data-testid='endpoint-row'][data-mac='{endpoint_mac}']"
    endpoint_status_cell_selector = f"{endpoint_row_selector} td[data-testid='endpoint-status']"
    endpoint_port_cell_selector = f"{endpoint_row_selector} td[data-testid='endpoint-port']"
    endpoint_details_link_selector = f"{endpoint_row_selector} a[data-testid='endpoint-details-link']"
    endpoint_last_seen_selector = "span[data-testid='endpoint-last-seen']"
    endpoint_status_details_selector = "span[data-testid='endpoint-status']"
    endpoint_switch_details_selector = "span[data-testid='endpoint-switch']"
    endpoint_port_details_selector = "span[data-testid='endpoint-port']"

    # ---------------------------------------------------------------------
    # Step 1: Confirm in Profiler UI that endpoint is displayed as connected
    #         on Gi1/0/10.
    # ---------------------------------------------------------------------
    try:
        # Navigate to endpoint inventory page (adjust URL/path as needed)
        await page.goto("https://10.34.50.201/dana-na/auth/url_admin/endpoints", wait_until="networkidle")

        # Search for the endpoint by MAC address
        await page.fill(endpoint_search_input_selector, endpoint_mac)
        await page.press(endpoint_search_input_selector, "Enter")

        # Wait for the row to appear
        await page.wait_for_selector(endpoint_row_selector, timeout=15_000)
    except PlaywrightError as exc:
        pytest.fail(f"Failed to load or search endpoint inventory page: {exc}")

    # Validate endpoint is present in the inventory and currently connected
    try:
        endpoint_row = await page.query_selector(endpoint_row_selector)
        assert endpoint_row is not None, f"Endpoint {endpoint_mac} not found in inventory."

        status_text = (await page.text_content(endpoint_status_cell_selector) or "").strip()
        port_text = (await page.text_content(endpoint_port_cell_selector) or "").strip()

        assert status_text.lower() in {"connected", "online"}, (
            f"Expected endpoint {endpoint_mac} to be connected, "
            f"but found status '{status_text}'."
        )
        assert expected_switch_port in port_text, (
            f"Expected endpoint {endpoint_mac} to be on port {expected_switch_port}, "
            f"but found '{port_text}'."
        )
    except PlaywrightError as exc:
        pytest.fail(f"Error while validating initial endpoint state: {exc}")

    # Capture the original "last seen" timestamp for later comparison
    try:
        await page.click(endpoint_details_link_selector)
        await page.wait_for_selector(endpoint_last_seen_selector, timeout=10_000)
        original_last_seen_text = (
            await page.text_content(endpoint_last_seen_selector) or ""
        ).strip()
    except PlaywrightError as exc:
        pytest.fail(f"Error while opening endpoint details or reading last-seen time: {exc}")

    # ---------------------------------------------------------------------
    # Step 2: On the switch, shut down interface Gi1/0/10 (external step).
    # Step 3: Confirm SNMP linkDown trap is sent (external step).
    #
    # These are performed outside of Playwright. To keep the test robust,
    # we assume they are done before this test proceeds. If you have an
    # automation hook (e.g., API/SSH), integrate it here.
    # ---------------------------------------------------------------------
    # For traceability, log the time at which we expect the linkDown to occur.
    linkdown_initiated_at = datetime.utcnow()

    # ---------------------------------------------------------------------
    # Step 4: Wait for Profiler processing interval plus 30 seconds.
    #         The actual processing interval should be taken from config;
    #         here we use a conservative wait with polling.
    # ---------------------------------------------------------------------
    # Total wait window (e.g., 5 minutes) with periodic refreshes and checks.
    max_wait_seconds = 300
    poll_interval_seconds = 15

    # ---------------------------------------------------------------------
    # Step 5: Refresh endpoint details page and validate expected results.
    # ---------------------------------------------------------------------
    endpoint_found_disconnected = False
    last_seen_updated_correctly = False

    for _ in range(max_wait_seconds // poll_interval_seconds):
        try:
            # Refresh the page to get latest state
            await page.reload(wait_until="networkidle")
        except PlaywrightError:
            # If reload fails sporadically, wait and retry on next loop
            await asyncio.sleep(poll_interval_seconds)
            continue

        try:
            # Re-ensure we are on the details view; if not, navigate again
            if not await page.query_selector(endpoint_last_seen_selector):
                await page.goto(
                    "https://10.34.50.201/dana-na/auth/url_admin/endpoints",
                    wait_until="networkidle",
                )
                await page.fill(endpoint_search_input_selector, endpoint_mac)
                await page.press(endpoint_search_input_selector, "Enter")
                await page.wait_for_selector(endpoint_row_selector, timeout=15_000)
                await page.click(endpoint_details_link_selector)
                await page.wait_for_selector(endpoint_last_seen_selector, timeout=10_000)

            # Read current values
            current_status_text = (
                await page.text_content(endpoint_status_details_selector) or ""
            ).strip()
            current_last_seen_text = (
                await page.text_content(endpoint_last_seen_selector) or ""
            ).strip()
            current_switch_text = (
                await page.text_content(endpoint_switch_details_selector) or ""
            ).strip()
            current_port_text = (
                await page.text_content(endpoint_port_details_selector) or ""
            ).strip()

            # Check if status is now disconnected
            if current_status_text.lower() in {
                "disconnected",
                "offline",
                "down",
            }:
                endpoint_found_disconnected = True

                # Validate endpoint still in inventory by checking details page
                assert endpoint_mac.replace(":", "").lower() in (
                    await page.content()
                ).lower(), (
                    "Endpoint details page content does not contain the MAC address; "
                    "endpoint may have been removed from inventory."
                )

                # Validate that switch and port remain recorded
                assert current_switch_text, (
                    "Expected associated switch to remain recorded, but field is empty."
                )
                assert expected_switch_port in current_port_text, (
                    f"Expected port {expected_switch_port} to remain recorded for "
                    f"historical purposes, but found '{current_port_text}'."
                )

                # Validate last-seen timestamp is updated (later than original)
                if current_last_seen_text and current_last_seen_text != original_last_seen_text:
                    # Parsing format is environment-specific; adjust as needed.
                    # Example assumes ISO-like format: '2025-01-06 12:34:56'
                    try:
                        current_last_seen_dt = datetime.strptime(
                            current_last_seen_text, "%Y-%m-%d %H:%M:%S"
                        )
                        # Allow some tolerance before linkdown_initiated_at
                        tolerance = timedelta(minutes=2)
                        assert current_last_seen_dt >= linkdown_initiated_at - tolerance, (
                            "Last-seen timestamp does not appear to match the time of "
                            "the linkDown event (too early)."
                        )
                        last_seen_updated_correctly = True
                    except ValueError:
                        # If parsing fails, at least assert it changed
                        last_seen_updated_correctly = (
                            current_last_seen_text != original_last_seen_text
                        )

                # If we reached here, we have all conditions we can check in this loop
                break

        except PlaywrightError:
            # Non-fatal error in this iteration; wait and retry
            await asyncio.sleep(poll_interval_seconds)
            continue

        await asyncio.sleep(poll_interval_seconds)

    # ---------------------------------------------------------------------
    # Final assertions after polling loop
    # ---------------------------------------------------------------------
    assert endpoint_found_disconnected, (
        "Endpoint status did not change to 'Disconnected' (or equivalent) "
        f"for {endpoint_mac} within the expected time window."
    )

    assert last_seen_updated_correctly, (
        "Endpoint last-seen timestamp was not updated to reflect the linkDown event "
        f"for {endpoint_mac}."
    )