import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any

import pytest
from playwright.async_api import Page, Browser, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.performance
@pytest.mark.high
async def test_tc_016_high_volume_dhcp_burst(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_016: Performance – High volume DHCPv4 requests (burst load)

    This test assesses the Profiler’s ability to handle a large burst of DHCPv4
    requests without dropping packets or significantly degrading classification
    performance.

    High-level flow:
        1. Prepare DHCP traffic generator to simulate 2000 unique MACs.
        2. Start monitoring tools (CPU, memory, packet processing).
        3. Run burst load for 5 minutes.
        4. Verify number of newly discovered devices (~2000, >95%).
        5. Measure classification delay for a sample of endpoints.
        6. Verify resource usage remains within safe limits and returns to normal.

    Assumptions:
        - The Profiler UI exposes:
            * A way to start/stop or confirm external DHCP traffic generation
              (or at least a status indicator).
            * A device inventory page with filters and total count.
            * A per-device first-seen timestamp or similar.
            * A system health/performance page with CPU/memory metrics.
        - The DHCP generator is either:
            * Controlled via the UI; or
            * Controlled externally and only its timing is coordinated here.
        - Selectors used below are placeholders and should be adjusted to match
          the actual application under test.
    """
    page = authenticated_page

    # ----------------------------
    # Helper functions
    # ----------------------------

    async def navigate_with_retry(url: str, retries: int = 3) -> None:
        """Navigate to a URL with basic retry logic."""
        last_error: Exception | None = None
        for attempt in range(1, retries + 1):
            try:
                await page.goto(url, wait_until="networkidle", timeout=60_000)
                return
            except PlaywrightTimeoutError as exc:
                last_error = exc
                logger.warning(
                    "Navigation attempt %d to %s failed: %s",
                    attempt,
                    url,
                    str(exc),
                )
                await asyncio.sleep(3)
        raise AssertionError(f"Failed to navigate to {url!r} after {retries} attempts") from last_error

    async def get_system_metrics() -> Dict[str, Any]:
        """
        Read current CPU and memory usage from Profiler UI.

        NOTE: Replace selectors and parsing logic with your actual UI details.
        """
        try:
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/system/health",
                wait_until="networkidle",
                timeout=60_000,
            )

            cpu_text = await page.locator("data-test=cpu-usage").inner_text()
            mem_text = await page.locator("data-test=memory-usage").inner_text()

            def parse_percent(value: str) -> float:
                return float(value.strip().rstrip("%"))

            cpu_usage = parse_percent(cpu_text)
            mem_usage = parse_percent(mem_text)

            logger.info("Current metrics - CPU: %.2f%%, Memory: %.2f%%", cpu_usage, mem_usage)
            return {"cpu": cpu_usage, "memory": mem_usage}
        except Exception as exc:
            logger.error("Failed to read system metrics: %s", exc)
            # Fail the test explicitly; metrics are critical for this scenario
            raise AssertionError(f"Unable to read system metrics: {exc}") from exc

    async def start_dhcp_burst() -> None:
        """
        Start DHCP burst generation for 2000 unique MACs.

        NOTE: This is a placeholder implementation. Adapt to your actual
        DHCP generator UI or control mechanism.
        """
        try:
            await navigate_with_retry(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/tools/dhcp-generator"
            )

            # Step 1: Configure DHCP generator for 2000 MACs and VLAN
            await page.fill("data-test=mac-count-input", "2000")
            await page.fill("data-test=vlan-id-input", "10")  # Example VLAN; adjust as needed

            # Safety: ensure PPS/VLAN capture is enabled
            await page.check("data-test=pps-capture-toggle")

            # Step 2: Start Profiler-side logging/monitoring if needed
            await page.check("data-test=enable-profiler-logging-checkbox")

            # Step 3: Start the DHCP storm
            await page.click("data-test=start-dhcp-burst-button")

            # Optional: wait for a status indicator that the burst is active
            await page.locator("data-test=burst-status-running").wait_for(timeout=30_000)
        except PlaywrightTimeoutError as exc:
            raise AssertionError(f"Timed out starting DHCP burst: {exc}") from exc
        except Exception as exc:
            raise AssertionError(f"Failed to start DHCP burst: {exc}") from exc

    async def stop_dhcp_burst_if_running() -> None:
        """
        Stop DHCP burst generation if it is still running (best-effort cleanup).
        """
        try:
            await navigate_with_retry(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/tools/dhcp-generator"
            )
            if await page.locator("data-test=burst-status-running").is_visible():
                await page.click("data-test=stop-dhcp-burst-button")
                await page.locator("data-test=burst-status-stopped").wait_for(timeout=30_000)
        except Exception as exc:
            # Do not fail test in cleanup; just log
            logger.warning("Failed to stop DHCP burst during cleanup: %s", exc)

    async def get_device_inventory_snapshot() -> Dict[str, Any]:
        """
        Capture a snapshot of the device inventory: total count and a small sample.

        NOTE: Adjust selectors and parsed fields to match your UI.
        """
        try:
            await navigate_with_retry(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/devices/inventory"
            )

            # Example: filter for devices discovered "today" to reduce noise
            await page.click("data-test=discovered-filter-dropdown")
            await page.click("data-test=discovered-filter-today")

            await page.wait_for_timeout(2_000)  # allow table refresh

            total_text = await page.locator("data-test=device-total-count").inner_text()
            total_count = int(total_text.strip())

            # Sample first N devices for delay analysis
            sample_rows = page.locator("data-test=device-row")
            sample_size = min(await sample_rows.count(), 20)
            sample_devices: List[Dict[str, Any]] = []

            for index in range(sample_size):
                row = sample_rows.nth(index)
                mac = (await row.locator("data-test=device-mac").inner_text()).strip()
                first_seen_text = (
                    await row.locator("data-test=device-first-seen").inner_text()
                ).strip()
                # Assume ISO 8601 or similar parseable timestamp
                first_seen = datetime.fromisoformat(first_seen_text)
                sample_devices.append(
                    {
                        "mac": mac,
                        "first_seen": first_seen,
                    }
                )

            logger.info(
                "Inventory snapshot - total: %d, sampled devices: %d",
                total_count,
                len(sample_devices),
            )
            return {"total": total_count, "sample": sample_devices}
        except Exception as exc:
            raise AssertionError(f"Failed to read device inventory: {exc}") from exc

    async def wait_for_device_count_increase(
        baseline_count: int,
        expected_min_increase: int,
        timeout_seconds: int = 600,
        poll_interval: int = 15,
    ) -> int:
        """
        Poll the inventory until the total device count increases by at least
        expected_min_increase or timeout occurs.

        Returns the final total device count observed.
        """
        deadline = datetime.utcnow() + timedelta(seconds=timeout_seconds)
        last_count = baseline_count

        while datetime.utcnow() < deadline:
            snapshot = await get_device_inventory_snapshot()
            last_count = snapshot["total"]
            if last_count - baseline_count >= expected_min_increase:
                return last_count
            logger.info(
                "Waiting for device count to increase. Baseline: %d, "
                "Current: %d, Target increase: %d",
                baseline_count,
                last_count,
                expected_min_increase,
            )
            await asyncio.sleep(poll_interval)

        return last_count

    # ----------------------------
    # Test execution
    # ----------------------------

    # Step 0: Capture baseline metrics and device count
    baseline_metrics = await get_system_metrics()
    baseline_inventory = await get_device_inventory_snapshot()
    baseline_device_count = baseline_inventory["total"]
    test_start_time = datetime.utcnow()

    # Safety: define expected parameters
    target_device_count = 2000
    acceptable_loss_ratio = 0.95  # > 95% of 2000
    min_expected_devices = int(target_device_count * acceptable_loss_ratio)

    # Step 1 + 2: Prepare DHCP generator and start Profiler monitoring
    await start_dhcp_burst()

    # Step 3: Run the load test for 5 minutes
    load_duration_seconds = 5 * 60
    await asyncio.sleep(load_duration_seconds)

    # Best-effort: stop the burst (if still running)
    await stop_dhcp_burst_if_running()

    # Step 4: After test, verify number of newly discovered devices
    # Allow some additional time for late-arriving processing
    final_device_count = await wait_for_device_count_increase(
        baseline_count=baseline_device_count,
        expected_min_increase=min_expected_devices,
        timeout_seconds=600,  # up to 10 minutes post-burst
        poll_interval=20,
    )

    newly_discovered_devices = final_device_count - baseline_device_count
    logger.info(
        "Newly discovered devices after burst: %d (baseline=%d, final=%d)",
        newly_discovered_devices,
        baseline_device_count,
        final_device_count,
    )

    assert newly_discovered_devices >= min_expected_devices, (
        "Number of discovered devices is below acceptable threshold: "
        f"expected at least {min_expected_devices}, got {newly_discovered_devices}"
    )

    # Step 5: Measure time from DHCP request to device visibility in UI
    # NOTE: We do not have direct per-request timestamps from the generator.
    #       As an approximation, we use test_start_time for the burst start.
    #       Replace this with actual DHCP request timestamps if available.
    post_burst_inventory = await get_device_inventory_snapshot()
    sample_devices = post_burst_inventory["sample"]

    if not sample_devices:
        raise AssertionError("No devices found in sample set to calculate classification delay")

    classification_delays: List[float] = []
    for device in sample_devices:
        first_seen: datetime = device["first_seen"]
        # Ensure we only consider devices first seen after the burst start
        if first_seen < test_start_time:
            continue
        delay_seconds = (first_seen - test_start_time).total_seconds()
        if delay_seconds >= 0:
            classification_delays.append(delay_seconds)

    if not classification_delays:
        raise AssertionError(
            "No sampled devices had first-seen timestamps after burst start; "
            "cannot compute classification delay"
        )

    avg_delay = sum(classification_delays) / len(classification_delays)
    logger.info(
        "Average classification delay for sampled devices: %.2f seconds "
        "(samples=%d)",
        avg_delay,
        len(classification_delays),
    )

    # Acceptable classification delay threshold (e.g., 120 seconds)
    max_acceptable_delay_seconds = 120
    assert (
        avg_delay <= max_acceptable_delay_seconds
    ), f"Average classification delay too high: {avg_delay:.2f}s (limit {max_acceptable_delay_seconds}s)"

    # Step 6: Verify CPU and memory usage during / after burst are within safe limits
    # Capture metrics shortly after burst
    post_burst_metrics = await get_system_metrics()

    # These thresholds should be aligned with product sizing guidelines.
    # Placeholder values:
    max_safe_cpu = 90.0  # percent
    max_safe_memory = 90.0  # percent

    assert (
        post_burst_metrics["cpu"] <= max_safe_cpu
    ), f"CPU usage too high after burst: {post_burst_metrics['cpu']:.2f}% (limit {max_safe_cpu}%)"

    assert (
        post_burst_metrics["memory"] <= max_safe_memory
    ), (
        f"Memory usage too high after burst: "
        f"{post_burst_metrics['memory']:.2f}% (limit {max_safe_memory}%)"
    )

    # Postconditions: Profiler returns to near-baseline resource usage
    # Allow some cool-down time
    await asyncio.sleep(60)
    cooled_metrics = await get_system_metrics()

    # We tolerate some residual increase (e.g., +20% vs baseline)
    allowed_delta = 20.0
    cpu_delta = cooled_metrics["cpu"] - baseline_metrics["cpu"]
    mem_delta = cooled_metrics["memory"] - baseline_metrics["memory"]

    assert cpu_delta <= allowed_delta, (
        "CPU did not return to near-baseline after burst: "
        f"baseline={baseline_metrics['cpu']:.2f}%, cooled={cooled_metrics['cpu']:.2f}%, "
        f"delta={cpu_delta:.2f}% (allowed {allowed_delta}%)"
    )

    assert mem_delta <= allowed_delta, (
        "Memory did not return to near-baseline after burst: "
        f"baseline={baseline_metrics['memory']:.2f}%, cooled={cooled_metrics['memory']:.2f}%, "
        f"delta={mem_delta:.2f}% (allowed {allowed_delta}%)"
    )

    # Implicit assertion: Profiler did not crash
    # If the UI is responsive and metrics are retrievable, we treat that as
    # evidence that the Profiler remained operational during the test.