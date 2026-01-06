import asyncio
from typing import List, Dict

import pytest
from playwright.async_api import Page, Error, TimeoutError as PlaywrightTimeoutError


@pytest.mark.asyncio
async def test_profiler_handles_broadcast_and_relayed_dhcpv4_requests(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_005: Validate Profiler handles both broadcast and relayed DHCPv4 requests.

    Description:
        Ensure Profiler captures local broadcast DHCPv4 and DHCPv4 received via relay
        and processes both correctly.

    Preconditions (assumed satisfied by test environment):
        - PPS internal interface connected to VLAN 100 with direct broadcast DHCP.
        - VLAN 200 uses DHCP relay (IP helper) to PPS internal IP.
        - DHCP sniffing mode: "DHCP Helper for internal ports."

    Expected Results:
        - Profiler captures and processes DHCPv4 broadcast from VLAN 100.
        - Profiler captures and processes DHCPv4 relayed packets from VLAN 200.
        - Both endpoints have distinct entries with correct VLAN/IP information
          and OS classification.
        - Two device records exist, each reflecting the appropriate capture method
          (broadcast vs relay, as seen in logs).
    """
    page = authenticated_page

    # Test data
    mac_vlan100 = "AA:BB:CC:DD:EE:05"
    mac_vlan200 = "AA:BB:CC:DD:EE:06"

    # These are placeholders; adjust to real selectors/labels in your UI.
    discovered_devices_url = (
        "https://npre-miiqa2mp-eastus2.openai.azure.com/profiler/discovered-devices"
    )
    device_table_selector = "table#discovered-devices-table"
    device_row_selector = f"{device_table_selector} tbody tr"
    search_input_selector = "input[data-testid='device-search-input']"
    vlan_cell_selector = "td[data-column='vlan']"
    ip_cell_selector = "td[data-column='ip']"
    os_cell_selector = "td[data-column='os']"
    mac_cell_selector = "td[data-column='mac']"
    capture_method_cell_selector = "td[data-column='capture_method']"

    # Helper: wait for a device row containing a given MAC address
    async def wait_for_device_by_mac(
        mac_address: str,
        timeout_ms: int = 120_000,
    ) -> Dict[str, str]:
        """
        Polls the Discovered Devices table until a row with the given MAC appears
        or the timeout is reached. Returns a dict with key fields for assertions.
        """
        end_time = asyncio.get_event_loop().time() + (timeout_ms / 1000.0)

        last_error: Exception | None = None

        while asyncio.get_event_loop().time() < end_time:
            try:
                await page.goto(discovered_devices_url, wait_until="networkidle")

                # Basic sanity check: table is visible
                await page.wait_for_selector(device_table_selector, timeout=10_000)

                # Optional: filter by MAC if a search/filter field exists
                if await page.locator(search_input_selector).is_visible():
                    await page.fill(search_input_selector, "")
                    await page.fill(search_input_selector, mac_address)
                    # Give UI a moment to filter
                    await page.wait_for_timeout(1_000)

                rows = page.locator(device_row_selector)
                row_count = await rows.count()

                for i in range(row_count):
                    row = rows.nth(i)
                    mac_text = (await row.locator(mac_cell_selector).inner_text()).strip().upper()
                    if mac_text == mac_address.upper():
                        vlan_text = (await row.locator(vlan_cell_selector).inner_text()).strip()
                        ip_text = (await row.locator(ip_cell_selector).inner_text()).strip()
                        os_text = (await row.locator(os_cell_selector).inner_text()).strip()
                        capture_method_text = (
                            await row.locator(capture_method_cell_selector).inner_text()
                        ).strip()

                        return {
                            "mac": mac_text,
                            "vlan": vlan_text,
                            "ip": ip_text,
                            "os": os_text,
                            "capture_method": capture_method_text,
                        }

                # If not found, wait a bit and retry
                await page.wait_for_timeout(5_000)

            except (PlaywrightTimeoutError, Error) as exc:
                # Capture last error but continue until overall timeout
                last_error = exc
                await page.wait_for_timeout(5_000)

        # If we exit the loop, the device was not found
        error_message = (
            f"Device with MAC {mac_address} was not discovered within "
            f"{timeout_ms / 1000:.0f} seconds."
        )
        if last_error:
            error_message += f" Last UI error: {last_error!r}"
        raise AssertionError(error_message)

    # Helper: validate common fields of a discovered device
    def assert_device_fields(
        device: Dict[str, str],
        expected_mac: str,
        expected_vlan: str | None = None,
        expected_capture_method_keywords: List[str] | None = None,
    ) -> None:
        """
        Assert that the device record has expected MAC, VLAN, capture method,
        and basic sanity for IP/OS fields.
        """
        assert device["mac"] == expected_mac.upper(), (
            f"MAC mismatch: expected {expected_mac}, got {device['mac']}"
        )

        if expected_vlan is not None:
            assert device["vlan"] == expected_vlan, (
                f"VLAN mismatch for MAC {expected_mac}: "
                f"expected {expected_vlan}, got {device['vlan']}"
            )

        # IP should not be empty (device should have received an address)
        assert device["ip"], f"IP address is empty for MAC {expected_mac}"

        # OS classification should not be empty; exact value may vary
        assert device["os"], f"OS classification is empty for MAC {expected_mac}"

        if expected_capture_method_keywords:
            capture_method_lower = device["capture_method"].lower()
            for keyword in expected_capture_method_keywords:
                assert keyword.lower() in capture_method_lower, (
                    f"Capture method for MAC {expected_mac} does not contain "
                    f"expected keyword '{keyword}'. Actual: '{device['capture_method']}'"
                )

    # -------------------------------------------------------------------------
    # Step 1: Connect endpoint MAC AA:BB:CC:DD:EE:05 directly to VLAN 100
    #         where PPS is in the same broadcast domain.
    # -------------------------------------------------------------------------
    # NOTE: This step is assumed to be handled by the test environment
    # (e.g., lab automation, physical setup). Here we only document it.
    # If you have an API to control endpoints/switches, integrate it here.

    # -------------------------------------------------------------------------
    # Step 2: Trigger DHCP (reboot or `ipconfig /renew`) on first endpoint.
    # -------------------------------------------------------------------------
    # NOTE: Same as above, this is assumed to be done externally.
    # Optionally, you could call a helper API here to trigger DHCP on the endpoint.
    # For demonstration, we just wait a bit to allow DHCP/Profiler to process.
    await asyncio.sleep(10)

    # -------------------------------------------------------------------------
    # Step 3: In Profiler UI, verify discovery of device with MAC AA:BB:CC:DD:EE:05.
    # -------------------------------------------------------------------------
    try:
        device_vlan100 = await wait_for_device_by_mac(mac_vlan100)
    except AssertionError as exc:
        # Graceful error handling with clear context
        raise AssertionError(
            f"Broadcast DHCP device (VLAN 100) was not discovered: {exc}"
        ) from exc

    # Assert expected fields for VLAN 100 / broadcast device
    assert_device_fields(
        device=device_vlan100,
        expected_mac=mac_vlan100,
        expected_vlan="100",
        expected_capture_method_keywords=["broadcast"],
    )

    # -------------------------------------------------------------------------
    # Step 4: Connect endpoint MAC AA:BB:CC:DD:EE:06 to VLAN 200,
    #         which uses IP helper to forward DHCP to PPS.
    # -------------------------------------------------------------------------
    # Again, assumed to be controlled externally. Documented for clarity.

    # -------------------------------------------------------------------------
    # Step 5: Trigger DHCP on second endpoint.
    # -------------------------------------------------------------------------
    # Assumed external; wait to allow DHCP/Profiler processing.
    await asyncio.sleep(10)

    # -------------------------------------------------------------------------
    # Step 6: Verify in Profiler > Discovered Devices that both MAC addresses
    #         are discovered and classified.
    # -------------------------------------------------------------------------
    try:
        device_vlan200 = await wait_for_device_by_mac(mac_vlan200)
    except AssertionError as exc:
        raise AssertionError(
            f"Relayed DHCP device (VLAN 200) was not discovered: {exc}"
        ) from exc

    # Assert expected fields for VLAN 200 / relay device
    assert_device_fields(
        device=device_vlan200,
        expected_mac=mac_vlan200,
        expected_vlan="200",
        expected_capture_method_keywords=["relay", "helper"],
    )

    # -------------------------------------------------------------------------
    # Final assertions: Both endpoints exist, are distinct, and show correct
    # VLAN/IP information and OS classification.
    # -------------------------------------------------------------------------
    assert device_vlan100["mac"] != device_vlan200["mac"], (
        "Discovered MAC addresses should be distinct for the two endpoints."
    )
    assert device_vlan100["vlan"] != device_vlan200["vlan"], (
        "VLAN values should differ between broadcast (100) and relay (200) endpoints."
    )
    assert device_vlan100["ip"] != device_vlan200["ip"], (
        "IP addresses should be distinct for the two endpoints."
    )

    # Optional: log for debugging (pytest -s)
    print(
        f"Discovered broadcast device: {device_vlan100}\n"
        f"Discovered relayed device: {device_vlan200}"
    )