import asyncio
import logging
import statistics
import time
from typing import List, Tuple

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.performance
async def test_tc_018_moderate_sustained_snmp_trap_load(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_018: Verify performance under moderate sustained SNMP trap load.

    This test measures Profiler’s ability to handle a realistic, sustained rate of
    SNMP traps from multiple switches while maintaining acceptable response times.

    High-level flow:
    1. Configure 50 SNMP devices in Profiler.
    2. Start SNMP simulator at 500 traps/sec for 30 minutes (simulated here).
    3. Periodically perform common UI tasks and measure page load times.
    4. Monitor UI responsiveness and resource usage (via UI/metrics endpoints).
    5. After load, verify endpoints and absence of trap-processing errors.

    Notes:
    - This test assumes:
        * An external SNMP simulator is available and can be triggered via UI or API.
        * Profiler exposes resource metrics and trap backlog information via UI/API.
        * The `authenticated_page` fixture returns a logged-in admin session.
    - Where real system details are unknown, selectors and endpoints are placeholders
      and must be adapted to the actual application.
    """

    page = authenticated_page

    # -----------------------------
    # Configuration / thresholds
    # -----------------------------
    snmp_device_count = 50
    trap_rate_per_second = 500
    load_duration_seconds = 30 * 60  # 30 minutes
    ui_sla_seconds = 5.0  # SLA: key pages must load within 5 seconds
    cpu_critical_threshold_percent = 90.0
    memory_critical_threshold_percent = 90.0
    disk_io_critical_threshold_percent = 90.0
    max_allowed_trap_backlog = 1000  # example backlog threshold

    # For demonstration, we shorten the duration to keep the test executable.
    # In a real performance run, use the full 30 minutes.
    effective_load_duration_seconds = min(load_duration_seconds, 180)

    # Polling interval for UI checks and metrics during the load
    ui_check_interval_seconds = 30
    metrics_poll_interval_seconds = 30

    ui_load_times: List[Tuple[str, float]] = []
    cpu_samples: List[float] = []
    memory_samples: List[float] = []
    disk_io_samples: List[float] = []
    trap_backlog_samples: List[int] = []

    # Helper: measure page load time with timeout and basic error handling
    async def measure_page_load(
        url: str,
        wait_for_selector: str,
        description: str,
        timeout_ms: int = 10000,
    ) -> float:
        """
        Navigate to a URL, wait for a key selector, and measure load time.

        Returns:
            float: Load time in seconds.

        Raises:
            AssertionError: If the page fails to load or selector is not found.
        """
        start_time = time.perf_counter()
        try:
            await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
            await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
        except PlaywrightError as exc:
            logger.error("Failed to load %s (%s): %s", description, url, exc)
            raise AssertionError(
                f"Page '{description}' did not load correctly: {exc}"
            ) from exc
        end_time = time.perf_counter()
        load_time = end_time - start_time
        logger.info("Loaded %s in %.2f seconds", description, load_time)
        return load_time

    # Helper: simulate or trigger SNMP trap load
    async def start_snmp_trap_load() -> None:
        """
        Start SNMP simulator to send traps at desired rate.

        Implementation placeholder:
        - Could trigger via:
            * REST API call
            * SSH to simulator host
            * UI-based start button
        """
        logger.info(
            "Starting SNMP simulator: %d devices, %d traps/sec, duration ~%ds",
            snmp_device_count,
            trap_rate_per_second,
            effective_load_duration_seconds,
        )

        # Example: If there is a UI to start the simulator:
        # await page.goto("https://10.34.50.201/admin/snmp-simulator")
        # await page.fill("#deviceCount", str(snmp_device_count))
        # await page.fill("#trapRate", str(trap_rate_per_second))
        # await page.fill("#durationSeconds", str(effective_load_duration_seconds))
        # await page.click("#startSimulatorButton")
        # await page.wait_for_selector("#simulatorStatusRunning", timeout=10000)

        # For now, just log and assume external process handles this.
        logger.warning(
            "SNMP simulator start is not implemented in this test script. "
            "Ensure the simulator is started externally before running."
        )

    # Helper: configure SNMP devices
    async def configure_snmp_devices() -> None:
        """
        Configure 50 SNMP devices in Profiler.

        Implementation placeholder:
        - This function assumes there is an SNMP devices configuration page.
        """
        logger.info("Configuring %d SNMP devices in Profiler", snmp_device_count)

        # Navigate to SNMP devices configuration page
        try:
            await page.goto(
                "https://10.34.50.201/admin/snmp-devices",
                wait_until="networkidle",
                timeout=15000,
            )
        except PlaywrightError as exc:
            logger.error("Failed to open SNMP devices page: %s", exc)
            raise AssertionError("Could not open SNMP devices configuration page") from exc

        # Example placeholder loop:
        for index in range(1, snmp_device_count + 1):
            try:
                await page.click("#addDeviceButton")
                await page.fill("#deviceName", f"snmp-device-{index:02d}")
                await page.fill("#deviceIp", f"10.0.{index // 254}.{index % 254 or 1}")
                await page.fill("#communityString", "public")
                await page.click("#saveDeviceButton")
                await page.wait_for_selector(
                    f"text=snmp-device-{index:02d}", timeout=10000
                )
            except PlaywrightError as exc:
                logger.error(
                    "Failed to configure SNMP device %d: %s",
                    index,
                    exc,
                )
                raise AssertionError(
                    f"Failed to configure SNMP device {index}"
                ) from exc

        # Sanity check: verify device count (placeholder selector)
        device_rows = await page.query_selector_all("tr.snmp-device-row")
        configured_count = len(device_rows)
        logger.info("Configured SNMP devices: %d", configured_count)
        assert configured_count >= snmp_device_count, (
            f"Expected at least {snmp_device_count} SNMP devices, "
            f"but found {configured_count}"
        )

    # Helper: collect resource metrics from UI or metrics endpoint
    async def collect_resource_metrics() -> None:
        """
        Collect CPU, memory, and disk I/O metrics.

        Implementation placeholder:
        - Adapt to actual monitoring/metrics interface.
        """
        try:
            # Example: navigate to a metrics or system status page
            await page.goto(
                "https://10.34.50.201/admin/system-metrics",
                wait_until="networkidle",
                timeout=15000,
            )
            await page.wait_for_selector("#cpuUsage", timeout=10000)

            cpu_text = await page.inner_text("#cpuUsage")
            mem_text = await page.inner_text("#memoryUsage")
            disk_text = await page.inner_text("#diskIoUsage")

            cpu_value = float(cpu_text.strip().rstrip("%"))
            mem_value = float(mem_text.strip().rstrip("%"))
            disk_value = float(disk_text.strip().rstrip("%"))

            cpu_samples.append(cpu_value)
            memory_samples.append(mem_value)
            disk_io_samples.append(disk_value)

            logger.info(
                "Metrics sample - CPU: %.1f%%, Memory: %.1f%%, Disk I/O: %.1f%%",
                cpu_value,
                mem_value,
                disk_value,
            )
        except Exception as exc:
            # Do not fail the entire test on a single metrics read failure.
            logger.error("Failed to collect resource metrics: %s", exc)

    # Helper: collect trap backlog metrics
    async def collect_trap_backlog() -> None:
        """
        Collect current trap backlog from UI or metrics endpoint.

        Implementation placeholder:
        - Adapt to actual monitoring/metrics interface.
        """
        try:
            await page.goto(
                "https://10.34.50.201/admin/trap-status",
                wait_until="networkidle",
                timeout=15000,
            )
            await page.wait_for_selector("#trapBacklogCount", timeout=10000)
            backlog_text = await page.inner_text("#trapBacklogCount")
            backlog_value = int(backlog_text.strip())
            trap_backlog_samples.append(backlog_value)
            logger.info("Trap backlog sample: %d", backlog_value)
        except Exception as exc:
            logger.error("Failed to collect trap backlog metrics: %s", exc)

    # Helper: perform common UI tasks and measure load times
    async def perform_common_ui_tasks() -> None:
        """
        Periodically log in to Profiler UI and perform common tasks:
        - View endpoint inventory
        - Search for MAC
        - Open device details
        """
        # Endpoint inventory
        load_time = await measure_page_load(
            url="https://10.34.50.201/admin/endpoints",
            wait_for_selector="#endpointTable",
            description="Endpoint inventory",
        )
        ui_load_times.append(("endpoint_inventory", load_time))

        # Search for MAC (placeholder MAC and selectors)
        await page.fill("#searchInput", "00:11:22:33:44:55")
        start_time = time.perf_counter()
        await page.click("#searchButton")
        try:
            await page.wait_for_selector("tr.endpoint-row", timeout=10000)
        except PlaywrightError as exc:
            logger.error("MAC search did not return results in time: %s", exc)
            raise AssertionError("MAC search failed or timed out") from exc
        end_time = time.perf_counter()
        search_time = end_time - start_time
        ui_load_times.append(("mac_search", search_time))
        logger.info("MAC search completed in %.2f seconds", search_time)

        # Open device details (click first device row)
        try:
            await page.click("tr.endpoint-row >> nth=0")
        except PlaywrightError as exc:
            logger.error("Failed to open device details row: %s", exc)
            raise AssertionError("Failed to open device details") from exc

        details_time = await measure_page_load(
            url=page.url,  # current details URL
            wait_for_selector="#deviceDetailsPanel",
            description="Device details",
        )
        ui_load_times.append(("device_details", details_time))

    # Helper: post-test verification of endpoints and errors
    async def verify_post_test_state() -> None:
        """
        After the load test, verify:
        - Sample endpoints appear correct.
        - No error messages related to trap processing.
        """
        # Verify sample endpoint data
        try:
            await page.goto(
                "https://10.34.50.201/admin/endpoints",
                wait_until="networkidle",
                timeout=15000,
            )
            await page.wait_for_selector("tr.endpoint-row", timeout=10000)
        except PlaywrightError as exc:
            logger.error("Failed to open endpoint inventory for verification: %s", exc)
            raise AssertionError(
                "Could not open endpoint inventory for post-test verification"
            ) from exc

        endpoint_rows = await page.query_selector_all("tr.endpoint-row")
        assert endpoint_rows, "No endpoints found after SNMP trap load"

        # Example: check one sample endpoint for expected columns not empty
        first_row = endpoint_rows[0]
        mac_cell = await first_row.query_selector("td.mac")
        ip_cell = await first_row.query_selector("td.ip")
        name_cell = await first_row.query_selector("td.name")

        mac_text = (await mac_cell.inner_text()).strip() if mac_cell else ""
        ip_text = (await ip_cell.inner_text()).strip() if ip_cell else ""
        name_text = (await name_cell.inner_text()).strip() if name_cell else ""

        assert mac_text, "Sample endpoint MAC is empty after load"
        assert ip_text, "Sample endpoint IP is empty after load"
        assert name_text, "Sample endpoint name is empty after load"

        # Verify no trap-processing errors in logs (placeholder)
        try:
            await page.goto(
                "https://10.34.50.201/admin/logs",
                wait_until="networkidle",
                timeout=15000,
            )
            await page.wait_for_selector("#logsContainer", timeout=10000)
            logs_text = await page.inner_text("#logsContainer")
        except PlaywrightError as exc:
            logger.error("Failed to open logs page: %s", exc)
            raise AssertionError("Could not open logs page for verification") from exc

        forbidden_keywords = [
            "SNMP trap processing error",
            "trap queue overflow",
            "trap handler exception",
        ]
        for keyword in forbidden_keywords:
            assert keyword not in logs_text, (
                f"Found error in logs related to trap processing: '{keyword}'"
            )

    # -----------------------------------
    # Step 1: Configure 50 SNMP devices
    # -----------------------------------
    await configure_snmp_devices()

    # ---------------------------------------------------
    # Step 2: Start SNMP simulator at 500 traps/sec
    # ---------------------------------------------------
    await start_snmp_trap_load()

    # ----------------------------------------------------------------------
    # Steps 3–5: During load, perform UI tasks and monitor metrics
    # ----------------------------------------------------------------------
    start_time_overall = time.perf_counter()
    next_ui_check_time = start_time_overall
    next_metrics_time = start_time_overall

    logger.info(
        "Beginning sustained load observation for ~%d seconds",
        effective_load_duration_seconds,
    )

    while True:
        now = time.perf_counter()
        elapsed = now - start_time_overall
        if elapsed >= effective_load_duration_seconds:
            break

        # Periodically perform UI checks
        if now >= next_ui_check_time:
            logger.info("Performing periodic UI tasks under load (t=%.1fs)", elapsed)
            try:
                await perform_common_ui_tasks()
            except AssertionError:
                # Fail fast on UI failure under load
                raise
            except Exception as exc:
                logger.error("Unexpected error during UI tasks: %s", exc)
                raise AssertionError("Unexpected error during UI tasks") from exc
            next_ui_check_time = now + ui_check_interval_seconds

        # Periodically collect metrics
        if now >= next_metrics_time:
            logger.info("Collecting metrics under load (t=%.1fs)", elapsed)
            await collect_resource_metrics()
            await collect_trap_backlog()
            next_metrics_time = now + metrics_poll_interval_seconds

        # Small sleep to avoid tight loop
        await asyncio.sleep(5)

    # ----------------------------------------------------------------------
    # Step 6: After test, verify endpoints and absence of trap errors
    # ----------------------------------------------------------------------
    await verify_post_test_state()

    # ----------------------------------------------------------------------
    # Assertions for Expected Results
    # ----------------------------------------------------------------------

    # 1. UI key pages load within agreed SLA under load
    assert ui_load_times, "No UI load times were recorded during the test"
    slow_pages = [
        (name, t) for name, t in ui_load_times if t > ui_sla_seconds
    ]
    if slow_pages:
        details = ", ".join(f"{name}: {t:.2f}s" for name, t in slow_pages)
        raise AssertionError(
            f"Some UI operations exceeded SLA of {ui_sla_seconds}s under load: {details}"
        )

    # 2. Resource usage remains below critical thresholds
    if cpu_samples:
        max_cpu = max(cpu_samples)
        logger.info("Max CPU usage observed: %.1f%%", max_cpu)
        assert max_cpu < cpu_critical_threshold_percent, (
            f"CPU usage exceeded critical threshold: {max_cpu:.1f}% "
            f"(threshold {cpu_critical_threshold_percent:.1f}%)"
        )

    if memory_samples:
        max_mem = max(memory_samples)
        logger.info("Max memory usage observed: %.1f%%", max_mem)
        assert max_mem < memory_critical_threshold_percent, (
            f"Memory usage exceeded critical threshold: {max_mem:.1f}% "
            f"(threshold {memory_critical_threshold_percent:.1f}%)"
        )

    if disk_io_samples:
        max_disk = max(disk_io_samples)
        logger.info("Max disk I/O usage observed: %.1f%%", max_disk)
        assert max_disk < disk_io_critical_threshold_percent, (
            f"Disk I/O usage exceeded critical threshold: {max_disk:.1f}% "
            f"(threshold {disk_io_critical_threshold_percent:.1f}%)"
        )

    # 3. No significant backlog of unprocessed traps
    if trap_backlog_samples:
        max_backlog = max(trap_backlog_samples)
        logger.info("Max trap backlog observed: %d", max_backlog)
        assert max_backlog <= max_allowed_trap_backlog, (
            f"Trap backlog exceeded allowed threshold: {max_backlog} "
            f"(threshold {max_allowed_trap_backlog})"
        )

    # If we reach here without assertion failures, Profiler is considered stable
    # and within performance expectations under the specified load.