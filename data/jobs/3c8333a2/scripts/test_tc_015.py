import asyncio
import logging
from typing import Optional

import pytest
from playwright.async_api import Page, Error as PlaywrightError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_015_max_length_hostname_device_attribute_server(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_015: Boundary test – maximum-length hostname/IP for Device Attribute Server

    Verifies that the UI and backend correctly handle the maximum supported length
    of server hostnames or IP addresses in Device Attribute Server configuration.

    Steps:
        1. Go to the page where Device Attribute Server servers are defined/added.
        2. Click "Add Server".
        3. Enter a hostname at the maximum allowed length.
        4. Set other required fields (port, protocol) to valid values.
        5. Click "Save" or "Add".
        6. Verify that server appears correctly in Available Servers list
           without truncation or error.

    Expected:
        - Server is accepted and displayed correctly.
        - No UI truncation that affects usability or underlying value.
        - Long-named Device Attribute Server available for selection.
    """
    page: Page = authenticated_page

    # Helper configuration (adjust as appropriate for the real system)
    max_hostname_length: int = 253  # Common DNS max length; adjust if system-specific
    test_port: str = "8443"
    test_protocol: str = "HTTPS"

    # Locators (CSS/xpath) are placeholders and should be adapted to the AUT.
    # Using descriptive names to ease future maintenance.
    device_attribute_nav_selector: str = "a:has-text('Device Attribute Servers')"
    add_server_button_selector: str = "button:has-text('Add Server')"
    hostname_input_selector: str = "input[name='hostname']"
    port_input_selector: str = "input[name='port']"
    protocol_select_selector: str = "select[name='protocol']"
    save_button_selector: str = "button:has-text('Save'), button:has-text('Add')"
    available_servers_table_selector: str = "table#device-attribute-servers"
    available_servers_row_selector: str = (
        f"{available_servers_table_selector} tr"
    )

    async def safe_click(selector: str, description: str) -> None:
        """Click an element with error handling and logging."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            await page.click(selector)
        except PlaywrightError as exc:
            logger.error("Failed to click %s (%s): %s", description, selector, exc)
            pytest.fail(f"Unable to click {description}: {exc}")

    async def safe_fill(selector: str, value: str, description: str) -> None:
        """Fill an input with error handling and logging."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            await page.fill(selector, value)
        except PlaywrightError as exc:
            logger.error("Failed to fill %s (%s): %s", description, selector, exc)
            pytest.fail(f"Unable to fill {description}: {exc}")

    async def safe_select_option(
        selector: str, value: str, description: str
    ) -> None:
        """Select an option in a <select> with error handling."""
        try:
            await page.wait_for_selector(selector, state="visible", timeout=10000)
            await page.select_option(selector, value=value)
        except PlaywrightError as exc:
            logger.error("Failed to select option for %s (%s): %s",
                         description, selector, exc)
            pytest.fail(f"Unable to select option for {description}: {exc}")

    def build_max_length_hostname(length: int) -> str:
        """
        Build a syntactically valid hostname with the requested total length.

        Uses labels of length 63 (max per RFC) and adjusts the last label to
        reach the exact total length (including dots).
        """
        if length < 1:
            raise ValueError("Hostname length must be positive")

        # Start with repeated 63-char labels
        label = "a" * 63
        labels = [label]

        while True:
            hostname = ".".join(labels)
            if len(hostname) == length:
                return hostname
            if len(hostname) > length:
                break
            labels.append(label)

        # Adjust last label
        base = ".".join(labels[:-1])
        remaining = length - len(base) - 1  # minus dot before last label
        if remaining <= 0:
            raise ValueError("Cannot construct hostname of requested length")
        if remaining > 63:
            raise ValueError("Requested length not achievable with valid labels")

        labels[-1] = "b" * remaining
        hostname = ".".join(labels)
        if len(hostname) != length:
            raise ValueError("Failed to construct hostname of exact length")
        return hostname

    # Step 1: Go to the page where Device Attribute Server servers are defined/added.
    # Assuming authenticated_page already landed on admin welcome; navigate via menu.
    await safe_click(
        device_attribute_nav_selector,
        description="Device Attribute Servers navigation",
    )

    # Step 2: Click "Add Server".
    await safe_click(
        add_server_button_selector,
        description="Add Server button",
    )

    # Step 3: Enter a hostname at the maximum allowed length.
    try:
        max_length_hostname: str = build_max_length_hostname(max_hostname_length)
    except ValueError as exc:
        pytest.fail(f"Failed to build max-length hostname: {exc}")

    await safe_fill(
        hostname_input_selector,
        max_length_hostname,
        description="Hostname field",
    )

    # Step 4: Set other required fields (port, protocol) to valid values.
    await safe_fill(
        port_input_selector,
        test_port,
        description="Port field",
    )

    await safe_select_option(
        protocol_select_selector,
        value=test_protocol.lower(),  # e.g., "https"
        description="Protocol select",
    )

    # Step 5: Click "Save" or "Add".
    await safe_click(
        save_button_selector,
        description="Save/Add server button",
    )

    # Optional: wait for any toast/notification to disappear or success message.
    # This is defensive; selectors should be adapted to the real UI.
    try:
        await page.wait_for_timeout(1000)
    except PlaywrightError:
        # Non-critical; continue
        pass

    # Step 6: Verify that server appears correctly in Available Servers list
    # without truncation or error.
    try:
        await page.wait_for_selector(
            available_servers_table_selector, state="visible", timeout=15000
        )
    except PlaywrightError as exc:
        pytest.fail(
            f"Available Servers table not visible after saving server: {exc}"
        )

    # Locate the row containing our hostname
    matching_row: Optional[str] = None
    rows = await page.locator(available_servers_row_selector).all()
    for row in rows:
        row_text = (await row.inner_text()).strip()
        if max_length_hostname in row_text:
            matching_row = row_text
            break

    assert matching_row is not None, (
        "Newly added max-length hostname server was not found in the "
        "Available Servers list."
    )

    # Assert that the hostname is not truncated in the UI.
    # Here we assert that the exact hostname string appears in the row text.
    # If the UI uses ellipsis, this assertion will fail and the test will
    # highlight the truncation issue.
    assert max_length_hostname in matching_row, (
        "Hostname appears truncated or altered in the Available Servers list. "
        "Expected full hostname to be displayed."
    )

    # Additional sanity checks: no visible error message related to this action
    # (selectors below are placeholders; adjust to real AUT).
    error_selector_candidates = [
        ".error-message",
        ".alert.alert-danger",
        "div[role='alert'].error",
    ]

    for selector in error_selector_candidates:
        try:
            error_loc = page.locator(selector)
            if await error_loc.is_visible():
                error_text = await error_loc.inner_text()
                pytest.fail(
                    f"Unexpected error message visible after adding server: "
                    f"{error_text}"
                )
        except PlaywrightError:
            # If selector is not present, ignore and continue to next candidate.
            continue

    # Postcondition: Long-named Device Attribute Server available for selection.
    # This is already implicitly validated by presence in the Available Servers list,
    # but we can explicitly assert that the row is interactable (e.g., selectable).
    # Placeholder selector logic for checkbox or selection control in the row.
    selectable_locator = page.locator(
        f"{available_servers_row_selector}:has-text('{max_length_hostname}') "
        "input[type='checkbox'], "
        f"{available_servers_row_selector}:has-text('{max_length_hostname}') "
        "input[type='radio']"
    )

    try:
        if await selectable_locator.count() > 0:
            # If there is a selection control, ensure it is enabled.
            assert await selectable_locator.first.is_enabled(), (
                "Server row is present but not selectable; expected it to be "
                "available for profiler configuration."
            )
    except PlaywrightError as exc:
        # Non-fatal; log for debugging but do not fail the core boundary test.
        logger.warning(
            "Could not verify explicit selection control for the new server: %s",
            exc,
        )