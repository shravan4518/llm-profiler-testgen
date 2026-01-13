import asyncio
import re
from datetime import datetime, timedelta
from typing import List

import pytest
from playwright.async_api import Page, Browser, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
async def test_configure_min_polling_interval_das(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_013: Configure minimum allowed polling interval for Device Attribute Server.

    Title:
        Configure minimum allowed polling interval for Device Attribute Server

    Description:
        Validate behavior when setting polling interval to the minimum allowed
        value (1 minute) and ensure system accepts and functions correctly.

    Steps:
        1. Log in as `ppsadmin` (handled by authenticated_page fixture).
        2. Navigate to Device Attribute Server configuration.
        3. Set Polling interval to `1`.
        4. Ensure `das1` is in Selected Servers.
        5. Click `Save Changes`.
        6. Observe successful save.
        7. Monitor logs for at least 3 minutes to confirm polling occurs
           approximately every minute.

    Expected Results:
        - System accepts polling interval = 1.
        - Polling events occur at ~1-minute intervals (within reasonable tolerance).
        - No performance warnings/errors appear due to small interval.

    Notes:
        - This test assumes:
          * The authenticated_page fixture logs in as `ppsadmin`.
          * The UI has identifiable selectors for DAS configuration and logs.
          * Polling events are visible in a log view with timestamps.
        - Adjust selectors and log parsing logic to match the actual application.
    """
    page = authenticated_page

    # -------------------------------------------------------------------------
    # Test constants and helper functions
    # -------------------------------------------------------------------------
    MIN_POLLING_INTERVAL_MINUTES = 1
    POLLING_TOLERANCE_SECONDS = 20  # +/- 20 seconds around 60 seconds
    OBSERVATION_WINDOW_MINUTES = 3  # how long to watch logs
    EXPECTED_MIN_EVENTS = 2        # at least 2 polling events in 3 minutes

    async def safe_click(locator_str: str, description: str) -> None:
        """Click a locator with error handling and descriptive messages."""
        try:
            await page.locator(locator_str).click()
        except PlaywrightTimeoutError as exc:
            pytest.fail(f"Timeout while trying to click {description}: {exc}")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Unexpected error while trying to click {description}: {exc}")

    async def safe_fill(locator_str: str, value: str, description: str) -> None:
        """Fill an input with error handling and descriptive messages."""
        try:
            field = page.locator(locator_str)
            await field.fill("")
            await field.type(value)
        except PlaywrightTimeoutError as exc:
            pytest.fail(f"Timeout while trying to fill {description}: {exc}")
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Unexpected error while trying to fill {description}: {exc}")

    def parse_timestamp_from_log_line(log_line: str) -> datetime | None:
        """
        Parse a timestamp from a log line.

        This is a placeholder implementation and should be updated to match
        the actual log timestamp format, e.g.:
        - "2026-01-06 12:34:56 Polling DAS das1 ..."
        - "[12:34:56] Polling event for das1"

        Returns:
            datetime object if parsed successfully, otherwise None.
        """
        # Example pattern: 2026-01-06 12:34:56
        match = re.search(
            r"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})",
            log_line,
        )
        if match:
            try:
                return datetime.strptime(match.group(1), "%Y-%m-%d %H:%M:%S")
            except ValueError:
                return None
        return None

    def is_polling_log_line(log_line: str) -> bool:
        """
        Determine whether a log line corresponds to a DAS polling event.

        Update the keywords to match the real log messages.
        """
        normalized = log_line.lower()
        return (
            "poll" in normalized
            and "device attribute server" in normalized
            or "polling" in normalized
            and "das1" in normalized
        )

    # -------------------------------------------------------------------------
    # Step 1: Log in as `ppsadmin` (handled by authenticated_page fixture)
    # -------------------------------------------------------------------------
    # Sanity check that we are on an authenticated/admin page
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        pytest.fail("Page did not reach network idle state after login.")

    # -------------------------------------------------------------------------
    # Step 2: Navigate to Device Attribute Server configuration
    # -------------------------------------------------------------------------
    # NOTE: Replace selectors with actual ones from the application.
    # Example navigation via menu.
    try:
        # Open admin/configuration menu
        await safe_click("text=System Configuration", "System Configuration menu")
        await safe_click("text=Device Attribute Server", "Device Attribute Server menu")
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to navigate to Device Attribute Server configuration: {exc}")

    # Wait for the DAS configuration page to load
    try:
        await page.wait_for_selector(
            "text=Device Attribute Server Configuration",
            timeout=15000,
        )
    except PlaywrightTimeoutError:
        pytest.fail("Device Attribute Server configuration page did not load in time.")

    # -------------------------------------------------------------------------
    # Step 3: Set Polling interval to `1`
    # -------------------------------------------------------------------------
    # NOTE: Adjust selector to actual polling interval input.
    polling_interval_input = "input[name='pollingInterval']"

    await safe_fill(
        polling_interval_input,
        str(MIN_POLLING_INTERVAL_MINUTES),
        "Polling Interval field",
    )

    # Assertion: verify the field contains the expected value
    current_value = await page.locator(polling_interval_input).input_value()
    assert (
        current_value == str(MIN_POLLING_INTERVAL_MINUTES)
    ), f"Polling interval input value should be '{MIN_POLLING_INTERVAL_MINUTES}', got '{current_value}'."

    # -------------------------------------------------------------------------
    # Step 4: Ensure `das1` is in Selected Servers
    # -------------------------------------------------------------------------
    # Example UI:
    # - Available Servers list
    # - Selected Servers list
    # - 'Add' button to move from available to selected
    #
    # Adjust selectors to match the actual implementation.
    selected_servers_list = "select[name='selectedServers']"
    available_servers_list = "select[name='availableServers']"
    add_button = "button:has-text('Add')"

    try:
        # Ensure lists are visible
        await page.wait_for_selector(selected_servers_list, timeout=10000)
        await page.wait_for_selector(available_servers_list, timeout=10000)
    except PlaywrightTimeoutError:
        pytest.fail("Server selection lists did not appear in time.")

    selected_servers_text = await page.locator(selected_servers_list).inner_text()
    if "das1" not in selected_servers_text:
        # If not already selected, move from available to selected
        available_options = page.locator(f"{available_servers_list} option")
        available_count = await available_options.count()

        das1_found = False
        for i in range(available_count):
            option = available_options.nth(i)
            option_text = (await option.inner_text()).strip()
            if option_text.lower() == "das1":
                await option.click()
                await safe_click(add_button, "Add server to selected list")
                das1_found = True
                break

        assert das1_found, "Server 'das1' not found in Available Servers list."

    # Verify that das1 is now in the selected list
    selected_servers_text = await page.locator(selected_servers_list).inner_text()
    assert "das1" in selected_servers_text, "Server 'das1' is not in Selected Servers."

    # -------------------------------------------------------------------------
    # Step 5: Click `Save Changes`
    # -------------------------------------------------------------------------
    # NOTE: Adjust selector to actual Save button.
    save_button_selector = "button:has-text('Save Changes')"

    await safe_click(save_button_selector, "Save Changes button")

    # -------------------------------------------------------------------------
    # Step 6: Observe successful save
    # -------------------------------------------------------------------------
    # Example: success banner, toast, or message.
    # Adjust selectors and messages to match the real system.
    success_message_locator = page.locator(
        "text=Changes saved successfully, text=Configuration saved, "
        "text=Update successful",
    )

    try:
        await success_message_locator.first.wait_for(timeout=15000)
    except PlaywrightTimeoutError:
        # Collect any visible error message for debugging
        error_banner = page.locator(".error, .alert-error, .message-error")
        error_text = ""
        try:
            if await error_banner.is_visible():
                error_text = await error_banner.inner_text()
        except Exception:  # noqa: BLE001
            error_text = ""
        pytest.fail(
            "Save operation did not show a success message within timeout. "
            f"Possible error: {error_text}",
        )

    # Assertion: polling interval value persisted after save (sanity check)
    # Re-read the field value
    persisted_value = await page.locator(polling_interval_input).input_value()
    assert (
        persisted_value == str(MIN_POLLING_INTERVAL_MINUTES)
    ), "Polling interval value did not persist after save."

    # -------------------------------------------------------------------------
    # Step 7: Monitor logs for at least 3 minutes to confirm polling occurs
    #         approximately every minute.
    # -------------------------------------------------------------------------
    #
    # This section is highly application-specific. The example assumes there is
    # a log viewer in the UI that can be opened and auto-refreshes or can be
    # manually refreshed.
    #
    # If your system exposes logs differently (e.g. separate page, tab, or
    # embedded console), adjust navigation and selectors accordingly.

    # Navigate to logs / monitoring page
    try:
        await safe_click("text=Monitoring", "Monitoring menu")
        await safe_click("text=System Logs", "System Logs menu")
    except AssertionError:
        raise
    except Exception as exc:  # noqa: BLE001
        pytest.fail(f"Failed to navigate to System Logs: {exc}")

    # Wait for log area to appear
    log_container_selector = "#logContainer, pre.log-output, div.log-viewer"
    try:
        await page.wait_for_selector(log_container_selector, timeout=15000)
    except PlaywrightTimeoutError:
        pytest.fail("Log viewer did not appear in time.")

    log_container = page.locator(log_container_selector)

    polling_timestamps: List[datetime] = []
    start_time = datetime.now()
    end_time = start_time + timedelta(minutes=OBSERVATION_WINDOW_MINUTES)

    # Optional: refresh button if logs require manual refresh
    refresh_button_selector = "button:has-text('Refresh'), button:has-text('Update')"
    refresh_button = page.locator(refresh_button_selector)

    while datetime.now() < end_time:
        try:
            # Refresh logs if button exists and is visible
            if await refresh_button.count() > 0 and await refresh_button.first.is_visible():
                await refresh_button.first.click()

            # Give some time for logs to update
            await asyncio.sleep(5)

            # Read logs
            logs_text = await log_container.inner_text()
            log_lines = logs_text.splitlines()

            for line in log_lines:
                if not is_polling_log_line(line):
                    continue

                timestamp = parse_timestamp_from_log_line(line)
                if timestamp and timestamp not in polling_timestamps:
                    polling_timestamps.append(timestamp)

            # Small sleep to avoid tight loop; still sample frequently
            await asyncio.sleep(10)
        except Exception as exc:  # noqa: BLE001
            pytest.fail(f"Error while monitoring logs: {exc}")

    # -------------------------------------------------------------------------
    # Assertions on polling behavior
    # -------------------------------------------------------------------------
    # We expect at least a couple of polling events in a 3-minute window.
    assert (
        len(polling_timestamps) >= EXPECTED_MIN_EVENTS
    ), (
        f"Expected at least {EXPECTED_MIN_EVENTS} polling events in "
        f"{OBSERVATION_WINDOW_MINUTES} minutes, but found {len(polling_timestamps)}. "
        "Verify log parsing and polling behavior."
    )

    # Sort timestamps and compute intervals in seconds
    polling_timestamps.sort()
    intervals_seconds: List[float] = []
    for i in range(1, len(polling_timestamps)):
        delta = (polling_timestamps[i] - polling_timestamps[i - 1]).total_seconds()
        intervals_seconds.append(delta)

    # Validate each interval is around 60 seconds within tolerance
    for idx, interval in enumerate(intervals_seconds):
        assert (
            60 - POLLING_TOLERANCE_SECONDS
            <= interval
            <= 60 + POLLING_TOLERANCE_SECONDS
        ), (
            f"Polling interval #{idx + 1} is {interval:.1f} seconds, "
            "which is outside the acceptable tolerance around 60 seconds. "
            "This may indicate incorrect polling behavior."
        )

    # -------------------------------------------------------------------------
    # Check for performance warnings/errors related to small interval
    # -------------------------------------------------------------------------
    # Search logs for warnings/errors mentioning polling interval or performance.
    warning_keywords = [
        "performance",
        "high load",
        "too frequent",
        "polling interval too small",
        "excessive polling",
    ]

    logs_text_final = await log_container.inner_text()
    logs_lower = logs_text_final.lower()

    problematic_messages = [
        kw for kw in warning_keywords if kw in logs_lower
    ]

    assert (
        not problematic_messages
    ), (
        "Detected potential performance warnings/errors related to small polling "
        f"interval: {problematic_messages}"
    )

    # If we reach this point, the test passes and postconditions are met:
    # - Device Attribute Server polling interval set to minimum value and active.