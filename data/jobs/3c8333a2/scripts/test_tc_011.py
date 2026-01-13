import asyncio
import logging
from typing import Any

import pytest
from playwright.async_api import Page, Browser, TimeoutError as PlaywrightTimeoutError

logger = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_tc_011_expired_admin_session_configuration_not_saved(
    authenticated_page: Page,
    browser: Browser,
) -> None:
    """
    TC_011: Attempt configuration changes with expired admin session

    Title:
        Attempt configuration changes with expired admin session

    Description:
        Validate that if the admin session times out before saving configuration,
        changes are not saved and the user is prompted to log in again.

    Preconditions:
        - Session timeout configured (e.g., 10 minutes).
        - Admin logged in and idle for a time near timeout.
        - `authenticated_page` fixture returns a logged-in admin page (TPSAdmin).

    Steps:
        1. Log in as TPSAdmin (via fixture).
        2. Navigate to Profiler Configuration > Settings > Basic Configuration.
        3. Wait until the session is expired (e.g., > timeout period).
        4. After timeout, change any field (e.g., check “Enable DHCPv6 packet capturing”).
        5. Click Save Changes.

    Expected Results:
        - System redirects to login page or shows session timeout message.
        - No configuration changes are saved.
        - Admin must re-login to perform changes.
    """
    page: Page = authenticated_page

    # Locators (update selectors as needed for your application)
    basic_config_menu_locator = page.get_by_role(
        "link", name="Basic Configuration", exact=True
    )
    profiler_config_menu_locator = page.get_by_role(
        "link", name="Profiler Configuration", exact=True
    )
    settings_menu_locator = page.get_by_role("link", name="Settings", exact=True)

    # Example checkbox for "Enable DHCPv6 packet capturing"
    dhcpv6_checkbox_locator = page.get_by_label(
        "Enable DHCPv6 packet capturing", exact=True
    )

    # Example "Save Changes" button
    save_changes_button_locator = page.get_by_role(
        "button", name="Save Changes", exact=True
    )

    # Locators for session timeout / login page detection
    login_username_locator = page.get_by_label("Username", exact=True)
    login_password_locator = page.get_by_label("Password", exact=True)
    login_button_locator = page.get_by_role("button", name="Sign In")

    session_timeout_message_locator = page.locator(
        "text=Your session has expired"
    )  # Adjust to actual message

    # 1. Log in as TPSAdmin (handled by authenticated_page fixture)
    #    We still validate we are on an authenticated page.
    try:
        await page.wait_for_load_state("networkidle", timeout=15000)
    except PlaywrightTimeoutError:
        logger.warning("Page did not reach networkidle state after login.")

    # 2. Navigate to Profiler Configuration > Settings > Basic Configuration
    #    Use robust navigation with error handling.
    try:
        await profiler_config_menu_locator.click(timeout=15000)
        await settings_menu_locator.click(timeout=15000)
        await basic_config_menu_locator.click(timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Failed to navigate to Basic Configuration page: {exc!r}")

    # Ensure Basic Configuration page is loaded by checking for a key element.
    try:
        await dhcpv6_checkbox_locator.wait_for(state="visible", timeout=15000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(
            "Basic Configuration page did not load correctly; "
            f"DHCPv6 checkbox not visible: {exc!r}"
        )

    # Capture the original state of the DHCPv6 checkbox to verify it does not change.
    try:
        original_checkbox_state: bool = await dhcpv6_checkbox_locator.is_checked()
    except Exception as exc:
        pytest.fail(
            f"Could not determine original state of DHCPv6 checkbox: {exc!r}"
        )

    # 3. Wait until the session is expired (> timeout period).
    #    NOTE: Adjust wait duration to your configured timeout. Here we simulate
    #    a shorter wait for automation (e.g., 70 seconds).
    #    In a real environment, you might want to use the actual timeout (e.g., 610s).
    simulated_timeout_seconds: int = 70
    logger.info(
        "Simulating idle time to trigger session timeout: %s seconds",
        simulated_timeout_seconds,
    )
    await asyncio.sleep(simulated_timeout_seconds)

    # 4. After timeout, change any field (toggle “Enable DHCPv6 packet capturing”).
    #    This should trigger a timeout check in the backend on save.
    try:
        await dhcpv6_checkbox_locator.click(timeout=15000)
    except PlaywrightTimeoutError as exc:
        # If the session already forced us to another page, this may fail.
        logger.warning(
            "Failed to interact with DHCPv6 checkbox after idle period; "
            "this might be due to session timeout: %r",
            exc,
        )

    # 5. Click "Save Changes".
    try:
        await save_changes_button_locator.click(timeout=15000)
    except PlaywrightTimeoutError as exc:
        # If the page already redirected due to timeout, the button might not exist.
        logger.warning(
            "Save Changes button not clickable (possibly due to timeout redirect): %r",
            exc,
        )

    # 6. Validate expected behavior:
    #    - System redirects to login page OR
    #    - Shows session timeout message.
    #    We wait for either condition.
    timeout_for_redirect_ms: int = 20000

    redirected_to_login: bool = False
    timeout_message_displayed: bool = False

    try:
        await asyncio.wait_for(
            _wait_for_any(
                [
                    _wait_for_locator_visible(login_username_locator),
                    _wait_for_locator_visible(session_timeout_message_locator),
                ]
            ),
            timeout=timeout_for_redirect_ms / 1000,
        )
    except asyncio.TimeoutError:
        # Neither login page nor timeout message appeared within the timeout.
        logger.error(
            "Neither login page nor session timeout message appeared "
            "after attempting to save with an expired session."
        )

    # Evaluate which condition is satisfied (if any)
    if await login_username_locator.is_visible():
        redirected_to_login = True

    if await session_timeout_message_locator.is_visible():
        timeout_message_displayed = True

    # Assert that at least one of the expected behaviors occurred.
    assert (
        redirected_to_login or timeout_message_displayed
    ), (
        "Expected to either be redirected to login page or see a session timeout "
        "message after saving with an expired session, but neither occurred."
    )

    # 7. Verify that configuration changes were NOT saved.
    #    If we are on login page, we must re-login and navigate back to verify.
    if redirected_to_login:
        # Attempt re-login with TPSAdmin credentials (replace with secure retrieval).
        await _relogin_as_admin(page)

        # Re-navigate to Basic Configuration page.
        try:
            await profiler_config_menu_locator.click(timeout=15000)
            await settings_menu_locator.click(timeout=15000)
            await basic_config_menu_locator.click(timeout=15000)
            await dhcpv6_checkbox_locator.wait_for(state="visible", timeout=15000)
        except PlaywrightTimeoutError as exc:
            pytest.fail(
                "Failed to re-navigate to Basic Configuration page after login: "
                f"{exc!r}"
            )

    else:
        # If timeout message is shown on the same page, we may need to dismiss it
        # or simply re-check the state of the field if still visible.
        logger.info("Session timeout message displayed; verifying config unchanged.")

    # Now verify that the DHCPv6 checkbox state is still the original one.
    try:
        current_checkbox_state: bool = await dhcpv6_checkbox_locator.is_checked()
    except Exception as exc:
        pytest.fail(
            f"Could not determine current state of DHCPv6 checkbox: {exc!r}"
        )

    assert (
        current_checkbox_state == original_checkbox_state
    ), (
        "Configuration change appears to have been saved despite session timeout. "
        f"Original state: {original_checkbox_state}, "
        f"current state: {current_checkbox_state}"
    )


async def _wait_for_locator_visible(locator: Any) -> None:
    """Helper coroutine to wait until a locator is visible."""
    await locator.wait_for(state="visible")


async def _wait_for_any(tasks: list) -> None:
    """
    Wait until any of the given coroutines completes successfully.

    This is a small helper to allow "OR" waiting between multiple conditions,
    such as login page or timeout message.
    """
    pending = {asyncio.create_task(task) for task in tasks}
    try:
        done, pending = await asyncio.wait(
            pending, return_when=asyncio.FIRST_COMPLETED
        )
        # Cancel all remaining tasks
        for task in pending:
            task.cancel()
        # Propagate exception from the first completed task if any
        for task in done:
            _ = task.result()
    finally:
        for task in pending:
            task.cancel()


async def _relogin_as_admin(page: Page) -> None:
    """
    Re-login as TPSAdmin.

    NOTE: Replace the credentials with secure retrieval (e.g., environment
    variables, secret manager) for real test environments.
    """
    username = "TPSAdmin"
    password = "CHANGE_ME_SECURELY"

    username_input = page.get_by_label("Username", exact=True)
    password_input = page.get_by_label("Password", exact=True)
    sign_in_button = page.get_by_role("button", name="Sign In")

    try:
        await username_input.fill(username)
        await password_input.fill(password)
        await sign_in_button.click()
        await page.wait_for_load_state("networkidle", timeout=20000)
    except PlaywrightTimeoutError as exc:
        pytest.fail(f"Failed to re-login as TPSAdmin after timeout: {exc!r}")