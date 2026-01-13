import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List

import pytest
from playwright.async_api import Page, Browser, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


# -----------------------------
# Helper utilities
# -----------------------------

SAFE_CPU_THRESHOLD = 85.0       # percent, example sizing guideline
SAFE_RAM_THRESHOLD = 85.0       # percent, example sizing guideline
SAFE_DISK_THRESHOLD = 90.0      # percent, example sizing guideline
MAX_UI_LOAD_TIME_SEC = 5.0      # as per test case


@asynccontextmanager
async def measure_page_load_time(
    page: Page,
    url: str,
    wait_for_selector: str,
    timeout_ms: int = 10_000,
) -> AsyncIterator[float]:
    """
    Context manager to measure page load time for a given URL.

    It navigates to `url`, waits for a selector that indicates the page
    is ready, and yields the elapsed time in seconds.
    """
    start = page.context._loop.time()  # uses same event loop timing
    try:
        await page.goto(url, wait_until="networkidle", timeout=timeout_ms)
        await page.wait_for_selector(wait_for_selector, timeout=timeout_ms)
        end = page.context._loop.time()
        elapsed = end - start
        yield elapsed
    except PlaywrightTimeoutError as exc:
        logger.error("Timeout while loading page %s: %s", url, exc)
        raise
    except Exception as exc:
        logger.exception("Unexpected error while measuring page load time: %s", exc)
        raise


async def fetch_profiler_metrics(page: Page) -> Dict[str, float]:
    """
    Fetch CPU, RAM, and disk utilization from the Profiler UI or API.

    This is a placeholder implementation. Adapt selectors or API calls
    to your real system. The function returns a dictionary:

        {
            "cpu": float,
            "ram": float,
            "disk": float,
        }
    """
    metrics: Dict[str, float] = {"cpu": 0.0, "ram": 0.0, "disk": 0.0}

    try:
        # Example: navigate to a system status / metrics page
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/system_status.cgi",
            wait_until="networkidle",
            timeout=15_000,
        )

        # Example selectors – replace with real ones:
        cpu_text = await page.locator("#cpu-usage").inner_text()
        ram_text = await page.locator("#ram-usage").inner_text()
        disk_text = await page.locator("#disk-usage").inner_text()

        # Assume text like "72 %" or "72%"; strip non-digits and convert
        metrics["cpu"] = float("".join(ch for ch in cpu_text if ch.isdigit()))
        metrics["ram"] = float("".join(ch for ch in ram_text if ch.isdigit()))
        metrics["disk"] = float("".join(ch for ch in disk_text if ch.isdigit()))

        logger.info("Profiler metrics: CPU=%s%%, RAM=%s%%, Disk=%s%%",
                    metrics["cpu"], metrics["ram"], metrics["disk"])
    except PlaywrightTimeoutError as exc:
        logger.error("Timeout while fetching profiler metrics: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Error while fetching profiler metrics: %s", exc)
        raise

    return metrics


async def verify_dhcpv6_capture_enabled(page: Page) -> None:
    """
    Verify that DHCPv6 capturing and external sniffing are enabled.

    This function should navigate to the relevant configuration page and
    assert that the checkboxes / toggles are enabled.
    """
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/dhcpv6_config.cgi",
            wait_until="networkidle",
            timeout=15_000,
        )

        dhcpv6_capture_checkbox = page.locator("#dhcpv6-capture-enabled")
        external_sniff_checkbox = page.locator("#external-sniff-enabled")

        await dhcpv6_capture_checkbox.wait_for(state="visible", timeout=10_000)
        await external_sniff_checkbox.wait_for(state="visible", timeout=10_000)

        dhcpv6_capture_checked = await dhcpv6_capture_checkbox.is_checked()
        external_sniff_checked = await external_sniff_checkbox.is_checked()

        assert dhcpv6_capture_checked, (
            "DHCPv6 capturing is not enabled; "
            "ensure TC_005 configuration is applied."
        )
        assert external_sniff_checked, (
            "External port sniffing is not enabled; "
            "ensure TC_005 configuration is applied."
        )

        logger.info("DHCPv6 capturing and external sniffing are enabled.")
    except PlaywrightTimeoutError as exc:
        logger.error("Timeout while verifying DHCPv6 capture configuration: %s", exc)
        raise
    except AssertionError:
        # Re-raise assertion errors so pytest reports them properly
        raise
    except Exception as exc:
        logger.exception("Unexpected error while verifying DHCPv6 capture: %s", exc)
        raise


async def start_dhcpv6_traffic() -> None:
    """
    Trigger high-rate DHCPv6 traffic generation.

    Implementation is environment-specific (e.g., REST call to traffic
    generator, SSH command, etc.). This is a stub that should be
    replaced with actual integration code.
    """
    try:
        # TODO: Implement integration with real DHCPv6 traffic generator.
        # For now, just log the intention.
        logger.info(
            "Starting DHCPv6 traffic generator at 5000+ packets/min "
            "on monitored interface."
        )
        # Simulate API call delay
        await asyncio.sleep(1)
    except Exception as exc:
        logger.exception("Failed to start DHCPv6 traffic generator: %s", exc)
        raise


async def stop_dhcpv6_traffic() -> None:
    """
    Stop DHCPv6 traffic generation.

    Implementation is environment-specific. Stub for now.
    """
    try:
        logger.info("Stopping DHCPv6 traffic generator.")
        await asyncio.sleep(1)
    except Exception as exc:
        logger.exception("Failed to stop DHCPv6 traffic generator: %s", exc)
        raise


async def fetch_profiler_logs(page: Page) -> List[str]:
    """
    Fetch recent Profiler logs related to DHCPv6 collector.

    Returns a list of log lines (strings). Implementation is a stub and
    should be adapted to the real system.
    """
    try:
        await page.goto(
            "https://10.34.50.201/dana-na/auth/url_admin/logs_dhcpv6.cgi",
            wait_until="networkidle",
            timeout=15_000,
        )

        # Example: log entries in a table with rows having class ".log-row"
        log_rows = page.locator(".log-row")
        count = await log_rows.count()

        logs: List[str] = []
        for i in range(count):
            row_text = await log_rows.nth(i).inner_text()
            logs.append(row_text)

        logger.info("Fetched %d DHCPv6-related log entries.", len(logs))
        return logs
    except PlaywrightTimeoutError as exc:
        logger.error("Timeout while fetching DHCPv6 logs: %s", exc)
        raise
    except Exception as exc:
        logger.exception("Error while fetching DHCPv6 logs: %s", exc)
        raise


def assert_no_packet_loss_or_collector_errors(logs: List[str]) -> None:
    """
    Assert that logs do not contain indications of packet loss,
    buffer overflows, or collector failures.
    """
    error_keywords = [
        "dropped packet",
        "buffer overflow",
        "collector failure",
        "collector error",
        "packet loss",
    ]

    offending_lines = [
        line for line in logs
        if any(keyword.lower() in line.lower() for keyword in error_keywords)
    ]

    assert not offending_lines, (
        "Detected potential packet loss or collector errors in logs:\n"
        + "\n".join(offending_lines)
    )


# -----------------------------
# Test case
# -----------------------------


@pytest.mark.asyncio
async def test_tc_024_profiler_dhcpv6_capture_performance(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_024: Profiler DHCPv6 capturing performance under high DHCPv6 traffic.

    Validate that enabling DHCPv6 packet capturing and external port sniffing
    does not degrade system performance under high DHCPv6 traffic load.

    Steps:
    1. Ensure DHCPv6 capturing and external sniffing are enabled and active.
    2. Start the DHCPv6 traffic generator at 5,000+ DHCPv6 packets/min.
    3. Monitor Profiler CPU, RAM, and disk utilization.
    4. Monitor latency of Profiler UI (config page load time).
    5. Check logs for dropped packets, buffer overflows, or collector errors.

    Expected:
    - UI remains responsive (< 5 s load time).
    - Resource utilization stays within safe thresholds.
    - No significant packet loss or collector failures are logged.
    """
    page = authenticated_page

    # STEP 1: Ensure DHCPv6 capturing and external sniffing are enabled
    await verify_dhcpv6_capture_enabled(page)

    # STEP 2: Start high-rate DHCPv6 traffic
    await start_dhcpv6_traffic()

    # Ensure traffic is stopped even if assertions fail
    try:
        # STEP 3: Monitor Profiler CPU, RAM, and disk utilization
        metrics = await fetch_profiler_metrics(page)

        assert metrics["cpu"] < SAFE_CPU_THRESHOLD, (
            f"CPU utilization too high under DHCPv6 load: "
            f"{metrics['cpu']}% (threshold {SAFE_CPU_THRESHOLD}%)."
        )
        assert metrics["ram"] < SAFE_RAM_THRESHOLD, (
            f"RAM utilization too high under DHCPv6 load: "
            f"{metrics['ram']}% (threshold {SAFE_RAM_THRESHOLD}%)."
        )
        assert metrics["disk"] < SAFE_DISK_THRESHOLD, (
            f"Disk utilization too high under DHCPv6 load: "
            f"{metrics['disk']}% (threshold {SAFE_DISK_THRESHOLD}%)."
        )

        # STEP 4: Monitor latency of Profiler UI (configuration page)
        config_page_url = (
            "https://10.34.50.201/dana-na/auth/url_admin/dhcpv6_config.cgi"
        )
        # Selector that indicates page is ready – adjust to real UI:
        ready_selector = "#dhcpv6-capture-enabled"

        async with measure_page_load_time(
            page,
            config_page_url,
            ready_selector,
            timeout_ms=int(MAX_UI_LOAD_TIME_SEC * 1000) + 5_000,
        ) as load_time:
            # Context manager already measured; we just get value
            pass

        logger.info("Configuration page load time under load: %.2f s", load_time)
        assert load_time <= MAX_UI_LOAD_TIME_SEC, (
            f"Configuration UI load time too high under DHCPv6 load: "
            f"{load_time:.2f}s (threshold {MAX_UI_LOAD_TIME_SEC:.2f}s)."
        )

        # STEP 5: Check logs for dropped packets, buffer overflows, or errors
        logs = await fetch_profiler_logs(page)
        assert_no_packet_loss_or_collector_errors(logs)

    finally:
        # POSTCONDITION: Stop traffic and ensure Profiler still runs normally
        await stop_dhcpv6_traffic()

        # Optional: quick sanity check that DHCPv6 collector is still active
        try:
            await verify_dhcpv6_capture_enabled(page)
        except Exception as exc:
            # Log but do not hide primary test failures
            logger.error(
                "Postcondition check failed: DHCPv6 collector may not be active: %s",
                exc,
            )