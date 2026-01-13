import asyncio
import logging
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.high
async def test_profiler_polls_device_attribute_server_and_updates_endpoint_attributes(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_017: Integration – Profiler polling Device Attribute Server via HTTP

    Verify that Profiler:
    - Regularly polls the configured Device Attribute Server (HTTP Attribute Server)
      at the configured interval.
    - Updates endpoint attributes based on data from the Device Attribute Server.

    Preconditions:
    - Device Attribute Server ("Controller-01") is configured and reachable.
    - Polling interval can be set (e.g., to 5 minutes).
    - Endpoint EP-12345 already exists (discovered via passive collectors).
    """
    page = authenticated_page

    # --- Test configuration (adjust selectors and URLs to your actual UI) ---
    device_attribute_server_name = "Controller-01"
    endpoint_id = "EP-12345"
    new_device_type = "Smartphone"
    polling_interval_minutes = 5

    # Safety margin: wait slightly longer than the configured interval
    polling_wait_seconds = polling_interval_minutes * 60 + 60

    # Helper for safe click with logging
    async def safe_click(locator_str: str, description: str) -> None:
        try:
            locator = page.locator(locator_str)
            await locator.wait_for(state="visible", timeout=15000)
            await locator.click()
            logger.info("Clicked: %s (%s)", locator_str, description)
        except PlaywrightError as exc:
            logger.error("Failed to click %s: %s", description, exc)
            pytest.fail(f"Unable to click {description}: {exc}")

    # Helper for safe fill with logging
    async def safe_fill(locator_str: str, value: str, description: str) -> None:
        try:
            locator = page.locator(locator_str)
            await locator.wait_for(state="visible", timeout=15000)
            await locator.fill(value)
            logger.info("Filled %s with '%s' (%s)", locator_str, value, description)
        except PlaywrightError as exc:
            logger.error("Failed to fill %s: %s", description, exc)
            pytest.fail(f"Unable to fill {description}: {exc}")

    # Helper to assert text content
    async def assert_text_contains(
        locator_str: str,
        expected_substring: str,
        description: str,
        timeout_ms: int = 30000,
    ) -> None:
        try:
            locator = page.locator(locator_str)
            await locator.wait_for(state="visible", timeout=timeout_ms)
            text = await locator.text_content()
            assert text is not None, f"No text found for {description}"
            assert expected_substring in text, (
                f"Expected '{expected_substring}' in {description}, "
                f"but got: '{text.strip()}'"
            )
            logger.info(
                "Verified '%s' is present in %s (text: '%s')",
                expected_substring,
                description,
                text.strip(),
            )
        except PlaywrightError as exc:
            logger.error("Playwright error while asserting %s: %s", description, exc)
            pytest.fail(f"Playwright error while asserting {description}: {exc}")

    # ----------------------------------------------------------------------
    # Step 1: Configure Device Attribute Server with Controller-01
    #         and polling interval = 5
    # ----------------------------------------------------------------------
    try:
        # NOTE: Replace navigation and selectors with actual application paths.
        # Example: Navigate to Profiler configuration > Device Attribute Servers
        await safe_click(
            "text=Configuration",
            "Configuration main menu",
        )
        await safe_click(
            "text=Device Attribute Servers",
            "Device Attribute Servers submenu",
        )

        # Select "Controller-01" in Selected Servers (or add/configure it)
        await safe_click(
            f"text={device_attribute_server_name}",
            f"Device Attribute Server '{device_attribute_server_name}' entry",
        )

        # Set polling interval to 5 minutes
        await safe_fill(
            "input[name='pollingIntervalMinutes']",
            str(polling_interval_minutes),
            "Polling interval input (minutes)",
        )

        # Save configuration
        await safe_click("button:has-text('Save')", "Save Device Attribute Server config")

        # Optional: verify success notification
        await assert_text_contains(
            ".notification-success, .alert-success",
            "success",
            "configuration success message",
            timeout_ms=15000,
        )
    except AssertionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during Step 1 configuration: %s", exc)
        pytest.fail(f"Step 1 failed: Unable to configure Device Attribute Server: {exc}")

    # ----------------------------------------------------------------------
    # Step 2: On Controller-01, update attribute data for EP-12345
    #         (e.g., device type from 'Unknown' to 'Smartphone').
    #
    # NOTE:
    # In an ideal integration test, this step would call the real Controller-01
    # API or UI. Here we assume either:
    #  - There is a UI in Profiler to trigger a sync/update, or
    #  - An external fixture/test setup has already updated Controller-01.
    #
    # Below is a placeholder block that you should replace with the actual
    # update mechanism (REST call, UI steps, etc.).
    # ----------------------------------------------------------------------
    try:
        # Placeholder log; replace with real interaction if available.
        logger.info(
            "Assuming Controller-01 has updated attributes for %s to device type '%s'. "
            "If not, integrate API/UI calls here.",
            endpoint_id,
            new_device_type,
        )
    except Exception as exc:
        logger.exception("Unexpected error during Step 2 (Controller-01 update): %s", exc)
        pytest.fail(f"Step 2 failed: Unable to update attributes on Controller-01: {exc}")

    # ----------------------------------------------------------------------
    # Step 3: Wait >5 minutes for at least one polling cycle.
    #         Also verify that Profiler sends HTTP requests to Controller-01.
    #
    # We use Playwright's network interception to monitor HTTP calls that
    # match Controller-01. Adjust the URL pattern to your environment.
    # ----------------------------------------------------------------------
    controller_request_pattern = "Controller-01"  # e.g. "http://controller-01/api/*"
    controller_requests = []

    async def track_controller_requests(route_or_request):
        # This handler works for both page.on("request") and context.on("request")
        request = route_or_request
        if controller_request_pattern in request.url:
            logger.info("Observed polling request to Controller-01: %s", request.url)
            controller_requests.append(request)

    context = page.context
    context.on("request", track_controller_requests)

    start_time = datetime.utcnow()
    logger.info(
        "Waiting up to %s seconds for at least one polling request to Controller-01...",
        polling_wait_seconds,
    )

    try:
        # Use a periodic check instead of a single long sleep to allow early exit
        timeout_at = start_time + timedelta(seconds=polling_wait_seconds)
        while datetime.utcnow() < timeout_at:
            if controller_requests:
                break
            await asyncio.sleep(10)

        assert controller_requests, (
            "No HTTP polling requests to Controller-01 were observed within "
            f"{polling_wait_seconds} seconds. "
            "Verify that the URL pattern and polling configuration are correct."
        )
    except AssertionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error while waiting for polling requests: %s", exc)
        pytest.fail(f"Step 3 failed: Error while monitoring polling requests: {exc}")
    finally:
        # Clean up listener to avoid side effects on other tests
        context.off("request", track_controller_requests)

    # ----------------------------------------------------------------------
    # Step 4: In Profiler UI, open endpoint details for EP-12345.
    # ----------------------------------------------------------------------
    try:
        # Navigate to endpoints list
        await safe_click("text=Endpoints", "Endpoints main menu")

        # Search for EP-12345
        await safe_fill(
            "input[placeholder='Search endpoints'], input[name='endpointSearch']",
            endpoint_id,
            "Endpoint search box",
        )
        await safe_click("button:has-text('Search')", "Search button")

        # Open endpoint details row
        await safe_click(
            f"text={endpoint_id}",
            f"Endpoint row for {endpoint_id}",
        )

        # Wait for details panel/page to load
        await page.locator("text=Endpoint Details, text=Endpoint Information").wait_for(
            state="visible",
            timeout=30000,
        )
    except AssertionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during Step 4 (open endpoint details): %s", exc)
        pytest.fail(f"Step 4 failed: Unable to open endpoint details for {endpoint_id}: {exc}")

    # ----------------------------------------------------------------------
    # Step 5: Inspect attributes such as device type, OS, etc.
    #         Assert that device type reflects the new value from Controller-01.
    # ----------------------------------------------------------------------
    try:
        # Example selectors; replace with actual labels/ids from your UI.
        device_type_selector = "data-testid=device-type, span#deviceType, td:has-text('Device Type') + td"
        os_selector = "data-testid=device-os, span#deviceOS, td:has-text('OS') + td"

        # Verify device type updated to "Smartphone"
        await assert_text_contains(
            device_type_selector,
            new_device_type,
            "Endpoint device type field",
            timeout_ms=60000,
        )

        # Optionally verify OS or other attributes if Controller-01 updates them.
        # For now we only assert that OS field is present (non-empty).
        os_locator = page.locator(os_selector)
        await os_locator.wait_for(state="visible", timeout=30000)
        os_text = (await os_locator.text_content() or "").strip()
        assert os_text, "OS attribute should not be empty after polling update"
        logger.info("Verified OS attribute is present: '%s'", os_text)

    except AssertionError:
        raise
    except Exception as exc:
        logger.exception("Unexpected error during Step 5 (inspect attributes): %s", exc)
        pytest.fail(
            f"Step 5 failed: Unable to verify updated attributes for {endpoint_id}: {exc}"
        )

    # ----------------------------------------------------------------------
    # Final assertion: Profiler holds up-to-date endpoint attributes
    # synchronized with Device Attribute Server.
    #
    # This is effectively covered by:
    #  - Observed polling HTTP request(s) to Controller-01.
    #  - Verified endpoint device type updated to the new value.
    # ----------------------------------------------------------------------
    logger.info(
        "TC_017 passed: Profiler polled Controller-01 and updated attributes "
        "for endpoint %s to device type '%s'.",
        endpoint_id,
        new_device_type,
    )