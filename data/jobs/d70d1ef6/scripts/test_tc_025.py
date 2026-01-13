import asyncio
import statistics
import time
from typing import List, Dict, Any

import pytest
from playwright.async_api import Page, Browser, Error


@pytest.mark.asyncio
@pytest.mark.performance
async def test_profiler_polling_performance_min_vs_max_das(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_025: Profiler polling performance with minimal and maximal Device Attribute Servers.

    This test compares system behavior when polling:
      - Scenario A: a single Device Attribute Server (`das1`)
      - Scenario B: multiple Device Attribute Servers (`das1`–`das10`)

    It measures:
      - UI responsiveness (latency for key UI actions)
      - Presence/absence of polling errors
      - Relative resource usage (via browser performance metrics as proxy)

    NOTE:
      - Actual OS-level CPU/memory collection is out of scope for Playwright alone.
      - This test uses browser performance metrics and UI latency as an approximation.
      - The test is written to be robust and to fail clearly if performance degrades badly.
    """

    page = authenticated_page

    # -------------------------------
    # Helper functions
    # -------------------------------

    async def safe_click(page: Page, selector: str, description: str) -> None:
        """Click an element with error handling and a clear error message."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10_000)
            await page.click(selector)
        except Error as exc:
            pytest.fail(f"Failed to click '{description}' ({selector}): {exc}")

    async def safe_fill(page: Page, selector: str, text: str, description: str) -> None:
        """Fill an input field with error handling and a clear error message."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10_000)
            await page.fill(selector, text)
        except Error as exc:
            pytest.fail(f"Failed to fill '{description}' ({selector}) with '{text}': {exc}")

    async def safe_select_option(
        page: Page, selector: str, value: str, description: str
    ) -> None:
        """Select an option from a <select> element."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10_000)
            await page.select_option(selector, value=value)
        except Error as exc:
            pytest.fail(
                f"Failed to select option '{value}' for '{description}' ({selector}): {exc}"
            )

    async def measure_ui_action_latency(
        page: Page,
        action_coro,
        description: str,
        timeout_ms: int = 15_000,
    ) -> float:
        """
        Measure latency (in seconds) for a UI action.

        `action_coro` should be a coroutine that performs the action and awaits its completion.
        """
        start = time.perf_counter()
        try:
            await asyncio.wait_for(action_coro, timeout=timeout_ms / 1000)
        except asyncio.TimeoutError:
            pytest.fail(f"UI action '{description}' exceeded timeout of {timeout_ms} ms")
        except Error as exc:
            pytest.fail(f"UI action '{description}' failed: {exc}")
        end = time.perf_counter()
        return end - start

    async def collect_browser_metrics(page: Page) -> Dict[str, Any]:
        """
        Collect basic browser performance metrics as a proxy for system load.

        Returns a dict with:
          - 'dom_content_loaded'
          - 'load_event'
          - 'first_paint'
          - 'first_contentful_paint'
        """
        try:
            timing = await page.evaluate(
                """() => {
                    const perf = window.performance;
                    const nav = perf.getEntriesByType('navigation')[0];
                    const paint = perf.getEntriesByType('paint');
                    const fp = paint.find(e => e.name === 'first-paint');
                    const fcp = paint.find(e => e.name === 'first-contentful-paint');
                    return {
                        domContentLoaded: nav ? nav.domContentLoadedEventEnd : null,
                        loadEvent: nav ? nav.loadEventEnd : null,
                        firstPaint: fp ? fp.startTime : null,
                        firstContentfulPaint: fcp ? fcp.startTime : null
                    };
                }"""
            )
        except Error:
            timing = {}
        return timing

    async def verify_no_polling_errors(page: Page) -> None:
        """
        Verify that no polling-related errors are visible in the UI.

        This is a heuristic check; adjust selectors/texts to match the real UI.
        """
        error_indicators = [
            "Polling error",
            "Timeout while polling",
            "Device Attribute Server unreachable",
        ]

        page_text = (await page.content()).lower()
        for indicator in error_indicators:
            assert indicator.lower() not in page_text, (
                f"Found polling error indicator in UI: '{indicator}'"
            )

    async def configure_device_attribute_servers(
        page: Page,
        selected_servers: List[str],
        polling_interval_seconds: int,
    ) -> None:
        """
        Configure Device Attribute Servers in the Profiler UI.

        Adjust selectors according to the actual system under test.
        """
        # Navigate to Profiler / Device Attribute Server configuration page
        # (Selectors are placeholders and must be aligned with real UI)
        await safe_click(
            page,
            "a#menu-profiler",
            "Profiler main menu",
        )
        await safe_click(
            page,
            "a#menu-profiler-das-config",
            "Device Attribute Server configuration menu",
        )

        # Wait for configuration form to be visible
        await page.wait_for_selector("form#das-config-form", timeout=15_000)

        # Clear any existing selections and set the new list
        # Assume there are two multi-select boxes:
        # - Available servers: select#available-das
        # - Selected servers: select#selected-das
        # And buttons to move items between them.
        # These are placeholders and must be adapted to the real DOM.
        # First, clear existing selected servers:
        try:
            selected_options = await page.query_selector_all(
                "select#selected-das option"
            )
            if selected_options:
                await safe_click(
                    page,
                    "button#btn-das-remove-all",
                    "Remove all selected Device Attribute Servers",
                )
        except Error:
            # Non-fatal: if the control is not present, we continue.
            pass

        # Add each desired server from the available list
        for server in selected_servers:
            # Select server in available list
            await safe_select_option(
                page,
                "select#available-das",
                value=server,
                description=f"Available DAS '{server}'",
            )
            # Click add button
            await safe_click(
                page,
                "button#btn-das-add",
                f"Add DAS '{server}' to selected list",
            )

        # Set polling interval
        await safe_fill(
            page,
            "input#das-polling-interval",
            str(polling_interval_seconds),
            "Polling interval (seconds)",
        )

        # Save configuration
        await safe_click(
            page,
            "button#das-save",
            "Save Device Attribute Server configuration",
        )

        # Wait for confirmation / success message
        await page.wait_for_selector(
            "div.alert-success, div.flash-success",
            timeout=15_000,
        )

    async def simulate_polling_observation(
        page: Page,
        observation_seconds: int,
        sample_interval_seconds: int = 60,
    ) -> Dict[str, Any]:
        """
        Observe system behavior for a period to approximate load and responsiveness.

        During observation:
          - Periodically reload a key Profiler page to ensure it remains responsive.
          - Measure reload latency.
          - Collect browser metrics.

        Returns:
          {
            "latencies": [float, ...],
            "metrics": [dict, ...],
            "duration": float
          }
        """
        latencies: List[float] = []
        metrics: List[Dict[str, Any]] = []

        start_time = time.perf_counter()
        end_time = start_time + observation_seconds

        # Use a known Profiler page; adjust URL/selector as needed.
        profiler_status_selector = "div#profiler-status"

        while time.perf_counter() < end_time:
            # Measure latency for a "typical" UI operation (e.g., reload status page)
            async def reload_profiler_status():
                await page.reload(wait_until="networkidle")
                await page.wait_for_selector(profiler_status_selector, timeout=15_000)

            latency = await measure_ui_action_latency(
                page,
                reload_profiler_status(),
                description="Profiler status page reload",
            )
            latencies.append(latency)

            # Collect browser metrics
            metrics.append(await collect_browser_metrics(page))

            # Verify no polling errors in the UI snapshot
            await verify_no_polling_errors(page)

            # Sleep until next sample, unless we are near the end
            remaining = end_time - time.perf_counter()
            sleep_for = min(sample_interval_seconds, max(0, remaining))
            if sleep_for <= 0:
                break
            await asyncio.sleep(sleep_for)

        duration = time.perf_counter() - start_time
        return {
            "latencies": latencies,
            "metrics": metrics,
            "duration": duration,
        }

    # -------------------------------
    # Test logic
    # -------------------------------

    # Constants for the test
    polling_interval_seconds = 5
    scenario_a_servers = ["das1"]
    scenario_b_servers = [f"das{i}" for i in range(1, 11)]

    # Observation duration per scenario (in seconds).
    # The test case specifies 15 minutes; for automation practicality this
    # parameter can be tuned (e.g. 60–180 seconds). Here we keep the full 900.
    observation_duration_seconds = 900

    # -----------------------------------------
    # Step 1: Scenario A configuration (das1)
    # -----------------------------------------
    await configure_device_attribute_servers(
        page,
        selected_servers=scenario_a_servers,
        polling_interval_seconds=polling_interval_seconds,
    )

    # -----------------------------------------
    # Step 2: Monitor behavior for Scenario A
    # -----------------------------------------
    try:
        scenario_a_data = await simulate_polling_observation(
            page,
            observation_seconds=observation_duration_seconds,
            sample_interval_seconds=60,
        )
    except Exception as exc:
        pytest.fail(f"Error while monitoring Scenario A (single DAS): {exc}")

    # Basic sanity assertions for Scenario A
    assert scenario_a_data["latencies"], (
        "No latency samples collected for Scenario A; observation may have failed."
    )
    assert scenario_a_data["duration"] >= observation_duration_seconds * 0.8, (
        "Scenario A observation duration significantly shorter than expected; "
        "test may have terminated prematurely."
    )

    # -----------------------------------------
    # Step 3: Scenario B configuration (das1–das10)
    # -----------------------------------------
    await configure_device_attribute_servers(
        page,
        selected_servers=scenario_b_servers,
        polling_interval_seconds=polling_interval_seconds,
    )

    # -----------------------------------------
    # Step 4: Monitor behavior for Scenario B
    # -----------------------------------------
    try:
        scenario_b_data = await simulate_polling_observation(
            page,
            observation_seconds=observation_duration_seconds,
            sample_interval_seconds=60,
        )
    except Exception as exc:
        pytest.fail(f"Error while monitoring Scenario B (multiple DAS): {exc}")

    # Basic sanity assertions for Scenario B
    assert scenario_b_data["latencies"], (
        "No latency samples collected for Scenario B; observation may have failed."
    )
    assert scenario_b_data["duration"] >= observation_duration_seconds * 0.8, (
        "Scenario B observation duration significantly shorter than expected; "
        "test may have terminated prematurely."
    )

    # -----------------------------------------
    # Step 5: Compare UI latency and system load
    # -----------------------------------------

    # Compute median UI latency for both scenarios
    scenario_a_median_latency = statistics.median(scenario_a_data["latencies"])
    scenario_b_median_latency = statistics.median(scenario_b_data["latencies"])

    # We expect Scenario B to be heavier, but still acceptable.
    # Define an "acceptable" latency multiplier threshold (e.g., 3x).
    acceptable_multiplier = 3.0

    # Assertion: Scenario B latency must not be unreasonably higher
    assert scenario_b_median_latency <= scenario_a_median_latency * acceptable_multiplier, (
        "UI latency under high-load Device Attribute Server configuration is too high.\n"
        f"Scenario A median latency: {scenario_a_median_latency:.3f}s\n"
        f"Scenario B median latency: {scenario_b_median_latency:.3f}s\n"
        f"Allowed multiplier: {acceptable_multiplier:.2f}"
    )

    # Additional heuristic: ensure absolute latencies remain in a sane range
    max_acceptable_latency_seconds = 10.0
    assert scenario_b_median_latency <= max_acceptable_latency_seconds, (
        "UI latency under high-load configuration exceeds absolute acceptable threshold.\n"
        f"Scenario B median latency: {scenario_b_median_latency:.3f}s\n"
        f"Threshold: {max_acceptable_latency_seconds:.3f}s"
    )

    # Verify no polling errors were detected in either scenario
    await verify_no_polling_errors(page)

    # Optionally, compare basic browser metrics between scenarios
    # (we only assert that they do not explode to unreasonable values)
    def extract_load_events(metrics_list: List[Dict[str, Any]]) -> List[float]:
        values: List[float] = []
        for m in metrics_list:
            if m and isinstance(m.get("loadEvent"), (int, float)):
                values.append(float(m["loadEvent"]))
        return values

    a_load_events = extract_load_events(scenario_a_data["metrics"])
    b_load_events = extract_load_events(scenario_b_data["metrics"])

    if a_load_events and b_load_events:
        a_median_load = statistics.median(a_load_events)
        b_median_load = statistics.median(b_load_events)

        # Allow Scenario B to be heavier but not catastrophically so
        load_multiplier_threshold = 4.0
        assert b_median_load <= a_median_load * load_multiplier_threshold, (
            "Browser load events under high-load configuration are excessively slower.\n"
            f"Scenario A median loadEvent: {a_median_load:.1f} ms\n"
            f"Scenario B median loadEvent: {b_median_load:.1f} ms\n"
            f"Allowed multiplier: {load_multiplier_threshold:.1f}"
        )

    # Postcondition:
    # Per test case, configuration remains on high-load scenario (Scenario B).
    # No cleanup/reset is performed here; it must be handled manually or in a separate test.