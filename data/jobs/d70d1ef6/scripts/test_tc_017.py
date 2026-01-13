import asyncio
import logging
from typing import Dict, Any

import pytest
from playwright.async_api import Page, Error as PlaywrightError, expect

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
@pytest.mark.integration
@pytest.mark.medium
async def test_tc_017_ldap_collector_integration(
    authenticated_page: Page,
    browser,
) -> None:
    """
    TC_017: Integration of Profiler with LDAP collector configuration

    Validate that configuring LDAP collector in Profiler allows endpoint
    attributes from LDAP to be collected and used.

    Prerequisites:
        - LDAP server `ldap1.domain.local` reachable from Profiler with test user entries.
        - Profiler LDAP collector feature available.

    Steps:
        1. Log in as `ppsadmin`.
        2. Navigate to Profiler > Profiler Configuration > LDAP Collector.
        3. Enable LDAP collector.
        4. Enter LDAP connection details.
        5. Test connection (if button available).
        6. Click `Save Changes`.
        7. Trigger or wait for a profiling cycle.
        8. Verify LDAP attributes are populated for known endpoints.

    Expected:
        - LDAP connection test succeeds.
        - Profiler logs show successful binding and queries to LDAP.
        - Endpoint records show attributes retrieved from LDAP.
    """

    page: Page = authenticated_page

    # --- Test data / configuration (adjust to real system values) ---
    ldap_config: Dict[str, Any] = {
        "host": "ldap1.domain.local",
        "port": "389",
        "use_ssl": False,
        "bind_dn": "cn=profiler-bind,ou=service-accounts,dc=domain,dc=local",
        "bind_password": "ChangeMe123!",  # NOTE: replace with secure secret management
        "base_dn": "dc=domain,dc=local",
        "search_filter": "(objectClass=user)",
        "test_endpoint_identifier": "00:11:22:33:44:55",  # MAC or other key
        "expected_owner": "John Doe",
        "expected_department": "Engineering",
    }

    # Helper selectors – these are *examples* and should be aligned with actual UI
    profiler_menu_selector = "text=Profiler"
    profiler_config_menu_selector = "text=Profiler Configuration"
    ldap_collector_menu_selector = "text=LDAP Collector"

    ldap_enable_checkbox_selector = "input[type='checkbox'][name='ldap_enabled']"
    ldap_host_input_selector = "input[name='ldap_host']"
    ldap_port_input_selector = "input[name='ldap_port']"
    ldap_ssl_checkbox_selector = "input[type='checkbox'][name='ldap_ssl']"
    ldap_bind_dn_input_selector = "input[name='ldap_bind_dn']"
    ldap_bind_password_input_selector = "input[name='ldap_bind_password']"
    ldap_base_dn_input_selector = "input[name='ldap_base_dn']"
    ldap_filter_input_selector = "input[name='ldap_filter']"

    ldap_test_connection_button_selector = "button:has-text('Test Connection')"
    ldap_test_success_selector = "text=Connection test successful"
    ldap_save_button_selector = "button:has-text('Save Changes')"
    ldap_save_success_selector = "text=Configuration saved successfully"

    # Profiler log / status selectors (examples)
    profiler_log_tab_selector = "text=Profiler Logs"
    ldap_log_entry_selector = "text=LDAP bind successful"
    ldap_query_log_selector = "text=LDAP query executed"

    # Endpoint UI selectors (examples)
    endpoints_menu_selector = "text=Endpoints"
    endpoint_search_input_selector = "input[name='endpoint_search']"
    endpoint_search_button_selector = "button:has-text('Search')"
    endpoint_result_row_selector = "tr.endpoint-row"
    endpoint_owner_cell_selector = "td[data-column='owner']"
    endpoint_department_cell_selector = "td[data-column='department']"

    # ------------------------------------------------------------------
    # 1–2. Navigate to Profiler > Profiler Configuration > LDAP Collector
    # ------------------------------------------------------------------
    try:
        # The authenticated_page fixture should already be on an admin landing page.
        # Navigate through menus to LDAP Collector configuration.
        await page.wait_for_load_state("networkidle")

        await page.click(profiler_menu_selector)
        await page.click(profiler_config_menu_selector)
        await page.click(ldap_collector_menu_selector)

        # Wait for LDAP collector form to be visible
        await expect(page.locator(ldap_enable_checkbox_selector)).to_be_visible()
    except PlaywrightError as exc:
        logger.error("Failed to navigate to LDAP Collector configuration: %s", exc)
        pytest.fail(f"Navigation to LDAP Collector failed: {exc}")

    # ----------------------------------------------
    # 3. Enable LDAP collector (ensure checkbox on)
    # ----------------------------------------------
    try:
        ldap_enable_checkbox = page.locator(ldap_enable_checkbox_selector)
        await expect(ldap_enable_checkbox).to_be_visible()
        is_checked = await ldap_enable_checkbox.is_checked()
        if not is_checked:
            await ldap_enable_checkbox.check()
        # Assert it is enabled
        assert await ldap_enable_checkbox.is_checked(), "LDAP collector checkbox is not enabled."
    except PlaywrightError as exc:
        logger.error("Failed to enable LDAP collector: %s", exc)
        pytest.fail(f"Enabling LDAP collector failed: {exc}")

    # -------------------------------------------------
    # 4. Enter LDAP connection details into form fields
    # -------------------------------------------------
    try:
        await page.fill(ldap_host_input_selector, ldap_config["host"])
        await page.fill(ldap_port_input_selector, ldap_config["port"])

        ldap_ssl_checkbox = page.locator(ldap_ssl_checkbox_selector)
        ssl_checked = await ldap_ssl_checkbox.is_checked()
        if ldap_config["use_ssl"] and not ssl_checked:
            await ldap_ssl_checkbox.check()
        elif not ldap_config["use_ssl"] and ssl_checked:
            await ldap_ssl_checkbox.uncheck()

        await page.fill(ldap_bind_dn_input_selector, ldap_config["bind_dn"])
        await page.fill(ldap_bind_password_input_selector, ldap_config["bind_password"])
        await page.fill(ldap_base_dn_input_selector, ldap_config["base_dn"])
        await page.fill(ldap_filter_input_selector, ldap_config["search_filter"])
    except PlaywrightError as exc:
        logger.error("Failed to fill LDAP collector configuration: %s", exc)
        pytest.fail(f"Filling LDAP configuration failed: {exc}")

    # ---------------------------------------------------------
    # 5. Test connection (if the 'Test Connection' button exists)
    # ---------------------------------------------------------
    try:
        test_button = page.locator(ldap_test_connection_button_selector)
        if await test_button.count() > 0:
            await test_button.click()
            # Wait for a success message (or fail if not present)
            await expect(page.locator(ldap_test_success_selector)).to_be_visible(
                timeout=60_000
            )
        else:
            logger.warning("Test Connection button not available; skipping explicit test.")
    except PlaywrightError as exc:
        logger.error("LDAP connection test failed: %s", exc)
        pytest.fail(f"LDAP connection test did not succeed: {exc}")

    # ------------------------------------------------
    # 6. Click 'Save Changes' and verify configuration
    # ------------------------------------------------
    try:
        await page.click(ldap_save_button_selector)
        await expect(page.locator(ldap_save_success_selector)).to_be_visible(
            timeout=60_000
        )
    except PlaywrightError as exc:
        logger.error("Saving LDAP configuration failed: %s", exc)
        pytest.fail(f"Saving LDAP configuration failed: {exc}")

    # -----------------------------------------------------------------
    # 7. Trigger or wait for a profiling cycle
    #    (Implementation depends on product; here we wait with polling)
    # -----------------------------------------------------------------
    # If there is a "Run Now" profiler button, you could click it here.
    # For now, we wait for a reasonable time window for the cycle to run.
    profiling_wait_seconds = 120
    logger.info(
        "Waiting up to %s seconds for profiler cycle to complete.", profiling_wait_seconds
    )
    await asyncio.sleep(profiling_wait_seconds)

    # -------------------------------------------------------------------------
    # 8a. Check Profiler logs for successful LDAP binding and query execution
    # -------------------------------------------------------------------------
    try:
        # Navigate to logs tab/section
        await page.click(profiler_menu_selector)
        await page.click(profiler_log_tab_selector)

        # Wait for logs to load and verify expected entries
        await expect(page.locator(ldap_log_entry_selector)).to_be_visible(
            timeout=60_000
        )
        await expect(page.locator(ldap_query_log_selector)).to_be_visible(
            timeout=60_000
        )
    except PlaywrightError as exc:
        logger.error("Failed to verify LDAP-related logs: %s", exc)
        pytest.fail(f"LDAP logs verification failed: {exc}")

    # -------------------------------------------------------------------------
    # 8b. Verify endpoint records show LDAP attributes (owner, department, etc.)
    # -------------------------------------------------------------------------
    try:
        # Navigate to Endpoints or reporting UI
        await page.click(endpoints_menu_selector)

        # Search for a known endpoint that should have LDAP attributes
        await page.fill(
            endpoint_search_input_selector, ldap_config["test_endpoint_identifier"]
        )
        await page.click(endpoint_search_button_selector)

        # Wait for search results
        result_row = page.locator(endpoint_result_row_selector).first
        await expect(result_row).to_be_visible(timeout=60_000)

        owner_cell = result_row.locator(endpoint_owner_cell_selector)
        department_cell = result_row.locator(endpoint_department_cell_selector)

        await expect(owner_cell).to_be_visible()
        await expect(department_cell).to_be_visible()

        owner_text = (await owner_cell.inner_text()).strip()
        department_text = (await department_cell.inner_text()).strip()

        # Assertions: LDAP-derived attributes should be populated and match expectations
        assert owner_text, "Endpoint owner attribute is empty; LDAP data not populated."
        assert department_text, "Endpoint department attribute is empty; LDAP data not populated."

        # If specific expected values are known from LDAP, assert them:
        assert (
            owner_text == ldap_config["expected_owner"]
        ), f"Owner mismatch: expected '{ldap_config['expected_owner']}', got '{owner_text}'."
        assert (
            department_text == ldap_config["expected_department"]
        ), (
            "Department mismatch: expected "
            f"'{ldap_config['expected_department']}', got '{department_text}'."
        )

    except PlaywrightError as exc:
        logger.error("Failed to verify endpoint LDAP attributes in UI: %s", exc)
        pytest.fail(f"Endpoint LDAP attribute verification failed: {exc}")

    # -------------------------------------------------------------------------
    # Postcondition: LDAP collector remains active
    # -------------------------------------------------------------------------
    try:
        # Navigate back to LDAP collector configuration to confirm it is still enabled
        await page.click(profiler_menu_selector)
        await page.click(profiler_config_menu_selector)
        await page.click(ldap_collector_menu_selector)

        ldap_enable_checkbox = page.locator(ldap_enable_checkbox_selector)
        await expect(ldap_enable_checkbox).to_be_visible()
        assert await ldap_enable_checkbox.is_checked(), (
            "LDAP collector is not enabled after profiling cycle; "
            "postcondition not satisfied."
        )
    except PlaywrightError as exc:
        logger.error("Failed to verify LDAP collector postcondition: %s", exc)
        pytest.fail(f"Postcondition verification failed: {exc}")