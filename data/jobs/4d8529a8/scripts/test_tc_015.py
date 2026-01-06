import asyncio
import json
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, Optional

import pytest
from playwright.async_api import Page, Browser, Error as PlaywrightError

LOGGER = logging.getLogger(__name__)


@asynccontextmanager
async def _dhcp_injection_context(
    mac_address: str,
    hostname_payload: str,
    vendor_class_payload: str,
) -> AsyncIterator[None]:
    """
    Context manager placeholder for sending crafted DHCP packets.

    In a real test environment, this should:
      - Use a DHCP test tool / helper service (e.g., scapy or a custom microservice)
      - Send DISCOVER and REQUEST packets with the given MAC and options
      - Ensure PPS / Profiler can capture the traffic before yielding

    For this example, this function is a stub that simulates the wait time
    necessary for the Profiler to ingest and process the DHCP data.
    """
    try:
        # TODO: Replace this stub with actual DHCP packet generation and sending.
        LOGGER.info(
            "Simulating DHCP injection for MAC %s with hostname=%r, vendor_class=%r",
            mac_address,
            hostname_payload,
            vendor_class_payload,
        )
        # Simulate network propagation / processing delay
        await asyncio.sleep(3)
        yield
    finally:
        # Any cleanup for the DHCP tool would go here
        LOGGER.info("Completed DHCP injection simulation for MAC %s", mac_address)


async def _safe_get_text(page: Page, selector: str) -> Optional[str]:
    """Safely get inner text from a selector, returning None on failure."""
    try:
        element = await page.wait_for_selector(selector, timeout=10_000)
        return await element.inner_text()
    except PlaywrightError as exc:
        LOGGER.error("Failed to get text for selector %s: %s", selector, exc)
        return None


async def _safe_get_attribute(page: Page, selector: str, name: str) -> Optional[str]:
    """Safely get attribute from a selector, returning None on failure."""
    try:
        element = await page.wait_for_selector(selector, timeout=10_000)
        return await element.get_attribute(name)
    except PlaywrightError as exc:
        LOGGER.error(
            "Failed to get attribute %s for selector %s: %s", name, selector, exc
        )
        return None


@pytest.mark.asyncio
async def test_dhcp_malicious_options_sanitized(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_015: Security – Handling of malicious DHCP options (code injection patterns)

    Verifies that Profiler safely handles DHCP option values containing
    potentially malicious content (XSS/SQL injection patterns) in hostname
    and vendor class fields.

    Steps:
      1. Craft DHCP DISCOVER/REQUEST packets with malicious hostname/vendor class.
      2. Send packets so PPS captures them.
      3. Locate device record by MAC in Profiler UI.
      4. Inspect how hostname and vendor class are rendered.
      5. Check logs (and DB if exposed) for SQL errors or injection evidence.

    Expected:
      - UI renders payloads as plain text, with script tags escaped.
      - No JavaScript execution is triggered.
      - No SQL errors or injection signs in logs.
      - Device record is created and stored safely with special characters.
    """
    page = authenticated_page

    # Test data
    mac_address = "AA:BB:CC:DD:EE:13"
    hostname_payload = "<script>alert('xss')</script>"
    vendor_class_payload = "test'); DROP TABLE devices;--"

    # ----------------------------------------------------------------------
    # Step 1–2: Craft and send DHCP DISCOVER/REQUEST with malicious options
    # ----------------------------------------------------------------------
    async with _dhcp_injection_context(
        mac_address=mac_address,
        hostname_payload=hostname_payload,
        vendor_class_payload=vendor_class_payload,
    ):
        # While DHCP packets are being "sent", navigate to Profiler UI
        # NOTE: URL is given; the authenticated_page fixture should already
        # have a session. We still ensure we are on the correct base URL.
        try:
            await page.goto(
                "https://npre-miiqa2mp-eastus2.openai.azure.com/",
                wait_until="networkidle",
            )
        except PlaywrightError as exc:
            LOGGER.error("Failed to navigate to Profiler URL: %s", exc)
            pytest.fail(f"Navigation to Profiler failed: {exc}")

        # ------------------------------------------------------------------
        # Step 3: Locate device record for MAC AA:BB:CC:DD:EE:13
        # ------------------------------------------------------------------
        # The exact selectors depend on the Profiler UI. Below is a generic
        # example assuming:
        #   - There is a search input for MAC address.
        #   - Device rows appear in a table.
        #   - Each row has data attributes for MAC and columns for hostname
        #     and vendor class.
        #
        # Adjust selectors to match the real UI.
        device_search_selector = "input[data-test-id='device-search']"
        device_row_selector = f"tr[data-test-mac='{mac_address.lower()}']"
        hostname_cell_selector = f"{device_row_selector} td[data-test-field='hostname']"
        vendor_class_cell_selector = (
            f"{device_row_selector} td[data-test-field='vendor-class']"
        )

        try:
            # Wait for search box and search by MAC
            await page.wait_for_selector(device_search_selector, timeout=20_000)
            await page.fill(device_search_selector, mac_address)
            await page.keyboard.press("Enter")
        except PlaywrightError as exc:
            LOGGER.error("Failed to search for device by MAC: %s", exc)
            pytest.fail(f"Unable to search device by MAC: {exc}")

        # Wait for the device row to appear
        try:
            await page.wait_for_selector(device_row_selector, timeout=60_000)
        except PlaywrightError as exc:
            LOGGER.error("Device with MAC %s not found in UI: %s", mac_address, exc)
            pytest.fail(f"Device with MAC {mac_address} not found in UI: {exc}")

        # ------------------------------------------------------------------
        # Step 4: Inspect how hostname and vendor class are displayed in the UI
        # ------------------------------------------------------------------
        # Get text from hostname and vendor class cells
        hostname_text = await _safe_get_text(page, hostname_cell_selector)
        vendor_class_text = await _safe_get_text(page, vendor_class_cell_selector)

        assert (
            hostname_text is not None
        ), "Hostname cell text could not be retrieved from UI."
        assert (
            vendor_class_text is not None
        ), "Vendor class cell text could not be retrieved from UI."

        # UI should render payloads as plain text, not execute them.
        # We expect the raw dangerous sequences to be present as text,
        # but not interpreted as HTML/JS.
        #
        # Common patterns:
        #   - HTML entities for < and >, e.g., &lt;script&gt;...&lt;/script&gt;
        #   - Or the literal string rendered but not as HTML (depends on UI).
        #
        # Here we assert that the logical content is preserved and that the
        # raw script tag is not present in the DOM as HTML.
        #
        # Check that the text includes the meaningful content:
        assert "alert('xss')" in hostname_text, (
            "Hostname text does not contain expected XSS payload content. "
            f"Actual: {hostname_text!r}"
        )

        assert "DROP TABLE devices" in vendor_class_text, (
            "Vendor class text does not contain expected SQL payload content. "
            f"Actual: {vendor_class_text!r}"
        )

        # Ensure script tags are not interpreted as HTML in the cell.
        # If the UI escapes them, inner_text should show them literally or as
        # encoded entities, but the DOM should not contain an actual <script>
        # element inside that cell.
        try:
            script_child = await page.query_selector(
                f"{hostname_cell_selector} script"
            )
        except PlaywrightError as exc:
            LOGGER.error("Error while checking for script tag in hostname cell: %s", exc)
            script_child = None

        assert (
            script_child is None
        ), "A <script> element was found inside hostname cell; possible XSS vulnerability."

        # Also verify that inner HTML of the cell does not match the raw payload
        # exactly as HTML; it should be escaped or otherwise neutralized.
        try:
            hostname_inner_html = await page.inner_html(hostname_cell_selector)
        except PlaywrightError as exc:
            LOGGER.error(
                "Failed to retrieve inner HTML for hostname cell: %s", exc
            )
            hostname_inner_html = ""

        assert (
            "<script>alert('xss')</script>" not in hostname_inner_html
        ), (
            "Hostname cell inner HTML contains raw <script> tag, "
            "indicating unescaped XSS payload."
        )

        # Vendor class is not HTML, but we ensure it is rendered as text and
        # no suspicious HTML is introduced around it.
        try:
            vendor_inner_html = await page.inner_html(vendor_class_cell_selector)
        except PlaywrightError as exc:
            LOGGER.error(
                "Failed to retrieve inner HTML for vendor class cell: %s", exc
            )
            vendor_inner_html = ""

        assert (
            "<script" not in vendor_inner_html.lower()
        ), "Vendor class cell HTML contains unexpected <script> tag."

        # ------------------------------------------------------------------
        # Step 5: Monitor server logs and database for errors / SQL exceptions
        # ------------------------------------------------------------------
        # We use the browser console and network responses as proxies for
        # server-side errors. If your test environment exposes log endpoints
        # or DB inspection APIs, hook them here.
        #
        # Example: listen to console messages and network responses for errors.
        console_errors: Dict[str, Any] = {"messages": []}
        network_errors: Dict[str, Any] = {"responses": []}

        def _on_console_message(msg) -> None:
            if msg.type in {"error", "warning"}:
                console_errors["messages"].append(
                    {"type": msg.type, "text": msg.text}
                )

        async def _on_response(response) -> None:
            if response.status >= 500:
                try:
                    body = await response.text()
                except Exception:  # noqa: BLE001
                    body = "<unreadable>"
                network_errors["responses"].append(
                    {
                        "url": response.url,
                        "status": response.status,
                        "body": body[:500],
                    }
                )

        page.on("console", _on_console_message)
        page.on("response", lambda r: asyncio.create_task(_on_response(r)))

        # Trigger a minimal interaction to ensure any lazy-loaded logs or
        # detail panels are requested.
        try:
            await page.click(device_row_selector)
            await asyncio.sleep(2)
        except PlaywrightError as exc:
            LOGGER.warning("Failed to click device row for additional details: %s", exc)

        # Evaluate page context for any obvious JS errors related to XSS
        # (if the app stores error traces in a global object).
        try:
            js_errors = await page.evaluate(
                """() => {
                    const errors = window.__appErrors || [];
                    return Array.isArray(errors) ? errors : [];
                }"""
            )
        except PlaywrightError:
            js_errors = []

        # Assert there are no console or network indications of SQL injection
        # or server-side exceptions.
        # SQL-related strings to look for in logs/responses:
        sql_error_indicators = [
            "SQL",
            "SQLException",
            "syntax error",
            "ORA-",
            "psql:",
            "Mysql2::Error",
            "SQLiteException",
            "DROP TABLE",
        ]

        # Check console messages
        for msg in console_errors["messages"]:
            lower_text = msg["text"].lower()
            assert not any(
                indicator.lower() in lower_text for indicator in sql_error_indicators
            ), (
                "Console log contains SQL error / injection indicator: "
                f"{msg['text']!r}"
            )

        # Check network responses
        for resp in network_errors["responses"]:
            lower_body = resp["body"].lower()
            assert not any(
                indicator.lower() in lower_body for indicator in sql_error_indicators
            ), (
                "Network response body contains SQL error / injection indicator: "
                f"{resp['url']} -> {resp['status']}"
            )

        # Check JS error collection, if any
        if isinstance(js_errors, list):
            for err in js_errors:
                text = json.dumps(err)
                lower_text = text.lower()
                assert not any(
                    indicator.lower() in lower_text
                    for indicator in sql_error_indicators
                ), (
                    "Client-side error log contains SQL error / injection indicator: "
                    f"{text}"
                )

        # ------------------------------------------------------------------
        # Final sanity checks: device record exists and contains payload safely
        # ------------------------------------------------------------------
        # Ensure the device row is still present after interactions.
        try:
            await page.wait_for_selector(device_row_selector, timeout=10_000)
        except PlaywrightError as exc:
            LOGGER.error(
                "Device record disappeared from UI after interactions: %s", exc
            )
            pytest.fail(
                "Device record should remain visible; possible side-effect "
                "from malicious payload handling."
            )

        # Assert that the textual representation still contains the payload
        # (i.e., it was not truncated or silently dropped).
        assert hostname_payload.replace("<", "").replace(">", "")[:10].split(
            "alert"
        )[0] in hostname_text, (
            "Hostname appears to be unexpectedly altered or truncated; "
            f"actual: {hostname_text!r}"
        )

        assert "DROP TABLE" in vendor_class_text, (
            "Vendor class appears to be unexpectedly altered or truncated; "
            f"actual: {vendor_class_text!r}"
        )