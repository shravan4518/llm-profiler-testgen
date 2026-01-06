import asyncio
import random
import time
from datetime import datetime, timedelta

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError


@pytest.mark.asyncio
@pytest.mark.performance
async def test_tc_017_dual_stack_dhcp_performance(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_017: Performance – Sustained dual-stack (DHCPv4 + DHCPv6) traffic.

    Objective:
        Evaluate Profiler’s performance when simultaneously handling sustained
        DHCPv4 and DHCPv6 traffic in a dual-stack network.

    Notes:
        - This implementation assumes the UI provides:
          * A way to confirm DHCPv4/DHCPv6 capture is enabled.
          * A way to start/monitor a dual-stack load or to verify that an
            external load generator is already running.
          * A dashboard or metrics page for CPU, memory, and processing delay.
          * An endpoint inventory/search page that shows IPv4, IPv6, and
            classification per endpoint.

        - Where concrete selectors or API endpoints are not known, placeholder
          selectors are used and clearly marked with TODO comments. Replace
          these with real selectors/logic for your application.

    Prerequisites:
        - DHCPv4 and DHCPv6 capturing enabled.
        - Dual-stack network with load generation tools for both protocols.

    Expected Results:
        - Profiler sustains the load without crashes or significant backlog.
        - Both DHCPv4 and DHCPv6 data are correctly reflected for endpoints.
        - No severe increase in processing delays over time (no memory leak or
          degradation).
        - System remains stable and usable after the test.
    """
    page = authenticated_page

    # Configuration constants (adjust as needed for your environment)
    test_duration_minutes = 60  # Total duration of the performance run
    monitoring_interval_seconds = 300  # 5 minutes between metric samples
    max_allowed_cpu_percent = 85  # Example threshold
    max_allowed_memory_percent = 85  # Example threshold
    max_allowed_delay_growth_ms = 500  # Allowed increase in processing delay
    sample_endpoint_count = 20

    # Use this to store metrics over time for later comparison
    cpu_samples: list[float] = []
    memory_samples: list[float] = []
    processing_delay_samples_ms: list[float] = []

    # Helper: safe click with error handling
    async def safe_click(selector: str, description: str) -> None:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=30_000)
            await page.click(selector)
        except PlaywrightError as exc:
            pytest.fail(f"Failed to click {description} ({selector}): {exc}")

    # Helper: safe text extraction with error handling
    async def safe_text(selector: str, description: str) -> str:
        try:
            await page.wait_for_selector(selector, state="visible", timeout=30_000)
            element = await page.query_selector(selector)
            if not element:
                pytest.fail(f"Element for {description} not found: {selector}")
            text = await element.text_content()
            return text.strip() if text else ""
        except PlaywrightError as exc:
            pytest.fail(f"Failed to get text for {description} ({selector}): {exc}")

    # Helper: parse percentage text like "72%" -> 72.0
    def parse_percent(value: str, description: str) -> float:
        try:
            return float(value.strip().rstrip("%"))
        except (ValueError, AttributeError) as exc:
            pytest.fail(f"Unable to parse {description} percentage from '{value}': {exc}")

    # Helper: parse milliseconds text like "120 ms" -> 120.0
    def parse_ms(value: str, description: str) -> float:
        try:
            cleaned = value.lower().replace("ms", "").strip()
            return float(cleaned)
        except (ValueError, AttributeError) as exc:
            pytest.fail(f"Unable to parse {description} ms from '{value}': {exc}")

    # -------------------------------------------------------------------------
    # STEP 1: Configure test tools/VMs for 500 dual-stack endpoints
    # -------------------------------------------------------------------------
    # In many setups this is handled externally (e.g., traffic generator).
    # Here we:
    #   - Navigate to traffic/config page (if present)
    #   - Verify that a dual-stack profile with 500 endpoints is configured
    #   - Start the traffic if the UI controls it
    # -------------------------------------------------------------------------

    # TODO: Replace selectors/URLs with real ones for your environment
    traffic_config_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/ui/traffic/config"
    )

    await page.goto(traffic_config_url, wait_until="networkidle")

    # Example: verify dual-stack profile and endpoint count
    dual_stack_profile_selector = "text='Dual-stack DHCP Profile'"
    endpoint_count_selector = "[data-test-id='endpoint-count']"

    # Ensure the dual-stack profile is visible
    await page.wait_for_selector(dual_stack_profile_selector, timeout=30_000)

    # Validate that configured endpoint count is at least 500
    endpoint_count_text = await safe_text(
        endpoint_count_selector, "configured endpoint count"
    )
    try:
        endpoint_count = int(endpoint_count_text)
    except ValueError:
        pytest.fail(
            f"Endpoint count is not a valid integer: '{endpoint_count_text}'"
        )

    assert (
        endpoint_count >= 500
    ), f"Expected at least 500 dual-stack endpoints, found {endpoint_count}"

    # Start traffic if there is a UI control for it
    # (If traffic is started externally, this step can be a no-op or a check.)
    start_traffic_button = "[data-test-id='start-dual-stack-traffic']"
    try:
        if await page.query_selector(start_traffic_button):
            await safe_click(start_traffic_button, "Start dual-stack traffic")
    except PlaywrightError:
        # If this control does not exist, assume external traffic generator
        pass

    # -------------------------------------------------------------------------
    # STEP 2: Ensure PPS is capturing both DHCPv4 and DHCPv6
    # -------------------------------------------------------------------------

    # TODO: Replace with actual capture status page/controls
    capture_status_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/ui/capture/status"
    )
    await page.goto(capture_status_url, wait_until="networkidle")

    dhcpv4_status_selector = "[data-test-id='capture-dhcpv4-status']"
    dhcpv6_status_selector = "[data-test-id='capture-dhcpv6-status']"

    dhcpv4_status_text = await safe_text(
        dhcpv4_status_selector, "DHCPv4 capture status"
    )
    dhcpv6_status_text = await safe_text(
        dhcpv6_status_selector, "DHCPv6 capture status"
    )

    assert dhcpv4_status_text.lower() in {
        "enabled",
        "on",
    }, f"DHCPv4 capture not enabled: '{dhcpv4_status_text}'"
    assert dhcpv6_status_text.lower() in {
        "enabled",
        "on",
    }, f"DHCPv6 capture not enabled: '{dhcpv6_status_text}'"

    # -------------------------------------------------------------------------
    # STEP 3: Monitor profiler CPU, memory, and logs during the 1-hour test
    # -------------------------------------------------------------------------

    # TODO: Replace with actual performance dashboard selectors
    performance_dashboard_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/ui/performance/profiler"
    )
    await page.goto(performance_dashboard_url, wait_until="networkidle")

    cpu_selector = "[data-test-id='profiler-cpu-percent']"
    memory_selector = "[data-test-id='profiler-memory-percent']"
    delay_selector = "[data-test-id='profiler-processing-delay-ms']"
    log_panel_selector = "[data-test-id='profiler-log-panel']"
    severe_log_entry_selector = "[data-test-severity='error'], [data-test-severity='critical']"

    test_start_time = datetime.utcnow()
    test_end_time = test_start_time + timedelta(minutes=test_duration_minutes)

    # Take periodic samples for CPU, memory, and delay
    while datetime.utcnow() < test_end_time:
        # Refresh or ensure metrics are up to date
        await page.reload(wait_until="networkidle")

        cpu_text = await safe_text(cpu_selector, "Profiler CPU usage")
        memory_text = await safe_text(memory_selector, "Profiler memory usage")
        delay_text = await safe_text(
            delay_selector, "Profiler processing delay (ms)"
        )

        cpu_value = parse_percent(cpu_text, "CPU")
        memory_value = parse_percent(memory_text, "Memory")
        delay_value_ms = parse_ms(delay_text, "Processing delay")

        cpu_samples.append(cpu_value)
        memory_samples.append(memory_value)
        processing_delay_samples_ms.append(delay_value_ms)

        # Assert CPU and memory are within reasonable limits at each sample
        assert (
            cpu_value <= max_allowed_cpu_percent
        ), f"CPU usage too high: {cpu_value}% (threshold {max_allowed_cpu_percent}%)"
        assert (
            memory_value <= max_allowed_memory_percent
        ), (
            f"Memory usage too high: {memory_value}% "
            f"(threshold {max_allowed_memory_percent}%)"
        )

        # Check logs for severe errors
        await page.wait_for_selector(log_panel_selector, timeout=30_000)
        severe_logs = await page.query_selector_all(severe_log_entry_selector)
        assert (
            len(severe_logs) == 0
        ), "Severe error/critical log entries detected during performance run"

        # Wait until next monitoring interval
        await asyncio.sleep(monitoring_interval_seconds)

    # After the monitoring loop, verify no severe increase in processing delays
    if processing_delay_samples_ms:
        initial_delay = processing_delay_samples_ms[0]
        max_delay = max(processing_delay_samples_ms)
        delay_growth = max_delay - initial_delay

        assert (
            delay_growth <= max_allowed_delay_growth_ms
        ), (
            "Processing delay increased too much over time: "
            f"initial={initial_delay} ms, max={max_delay} ms, "
            f"growth={delay_growth} ms (threshold {max_allowed_delay_growth_ms} ms)"
        )

    # -------------------------------------------------------------------------
    # STEP 4: After the run, verify random sample of 20 endpoints show both
    #         IPv4 and IPv6 addresses and correct classification.
    # -------------------------------------------------------------------------

    # TODO: Replace with actual endpoint inventory/search page
    endpoints_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/ui/endpoints"
    )
    await page.goto(endpoints_url, wait_until="networkidle")

    # Example selectors for endpoint table
    endpoint_row_selector = "[data-test-id='endpoint-row']"
    ipv4_cell_selector = "[data-test-id='endpoint-ipv4']"
    ipv6_cell_selector = "[data-test-id='endpoint-ipv6']"
    classification_cell_selector = "[data-test-id='endpoint-classification']"

    # Wait for endpoint table to load
    await page.wait_for_selector(endpoint_row_selector, timeout=60_000)
    endpoint_rows = await page.query_selector_all(endpoint_row_selector)

    assert endpoint_rows, "No endpoints found after 1-hour dual-stack test"

    # Determine how many endpoints we can sample
    total_endpoints = len(endpoint_rows)
    sample_size = min(sample_endpoint_count, total_endpoints)

    # Randomly choose indices for sampling
    sampled_indices = random.sample(range(total_endpoints), sample_size)

    for index in sampled_indices:
        row = endpoint_rows[index]

        ipv4_element = await row.query_selector(ipv4_cell_selector)
        ipv6_element = await row.query_selector(ipv6_cell_selector)
        classification_element = await row.query_selector(
            classification_cell_selector
        )

        assert ipv4_element is not None, "Missing IPv4 cell for endpoint row"
        assert ipv6_element is not None, "Missing IPv6 cell for endpoint row"
        assert (
            classification_element is not None
        ), "Missing classification cell for endpoint row"

        ipv4_text = (await ipv4_element.text_content() or "").strip()
        ipv6_text = (await ipv6_element.text_content() or "").strip()
        classification_text = (
            await classification_element.text_content() or ""
        ).strip()

        assert ipv4_text, "Endpoint missing IPv4 address in Profiler"
        assert ipv6_text, "Endpoint missing IPv6 address in Profiler"

        # Classification criteria will depend on your product.
        # This is a generic check that classification is not empty or "unknown".
        assert classification_text, "Endpoint classification is empty"
        assert classification_text.lower() not in {
            "unknown",
            "unclassified",
        }, f"Endpoint classification is not valid: '{classification_text}'"

    # -------------------------------------------------------------------------
    # Postconditions: System remains stable and usable after the test
    # -------------------------------------------------------------------------

    # As a basic stability check, ensure we can still navigate and load
    # a core page (e.g., dashboard) without errors.
    dashboard_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/ui/dashboard"
    )
    try:
        await page.goto(dashboard_url, wait_until="networkidle", timeout=60_000)
    except PlaywrightError as exc:
        pytest.fail(f"System not stable after test; dashboard failed to load: {exc}")

    # Basic sanity: ensure some key dashboard element is visible
    dashboard_key_widget_selector = "[data-test-id='dashboard-summary-widget']"
    try:
        await page.wait_for_selector(
            dashboard_key_widget_selector, state="visible", timeout=30_000
        )
    except PlaywrightError as exc:
        pytest.fail(
            "System not fully usable after test; "
            f"dashboard summary widget not visible: {exc}"
        )

    # If we reach this point, the test passes all assertions.