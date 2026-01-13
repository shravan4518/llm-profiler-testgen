import asyncio
import time
from typing import List

import pytest
from playwright.async_api import Browser, Page, Error as PlaywrightError

# NOTE:
# - This test assumes the existence of a `browser` fixture (async Browser)
#   and an `authenticated_page` fixture in conftest.py.
# - `authenticated_page` is not used directly here because we need 10
#   different admin sessions. We instead create 10 independent contexts.


@pytest.mark.asyncio
async def test_tc_023_concurrent_admin_profiler_config_edits(browser: Browser) -> None:
    """
    TC_023: Performance under concurrent admin edits to Profiler Configuration.

    This test validates system behavior and performance when multiple admins
    concurrently access and attempt to update Profiler configuration.

    Steps:
        1. Simultaneously log in as admin1–admin10 on 10 different sessions.
        2. Navigate each session to the Basic Configuration page.
        3. At roughly the same time, each admin modifies Profiler Name to a
           unique value and clicks "Save Changes".
        4. Measure response time and observe any errors/locking issues.
        5. Refresh the configuration page after all saves complete and record
           the final Profiler Name.

    Expected:
        - System handles concurrent requests without crashes or significant slowdown.
        - At most one configuration version persists (last write wins) with no corruption.
        - Response time for each save stays within acceptable limits (e.g., < 3 seconds).
        - Final configuration reflects the last successfully saved values.
    """

    base_url = "https://10.34.50.201/dana-na/auth/url_admin/welcome.cgi"
    admin_users = [f"admin{i}" for i in range(1, 11)]
    admin_password = "AdminPassword123!"  # TODO: replace with secure retrieval

    # Adjust selectors according to actual application.
    login_username_selector = "input[name='username']"
    login_password_selector = "input[name='password']"
    login_submit_selector = "button[type='submit']"

    # Profiler configuration selectors (example; update as needed)
    profiler_nav_selector = "a[href*='profiler-basic-config']"
    profiler_name_input_selector = "input[name='profilerName']"
    profiler_save_button_selector = "button:has-text('Save Changes')"
    profiler_success_toast_selector = "text=Configuration saved successfully"
    profiler_error_selector = ".error, .alert-danger"

    max_acceptable_response_time_sec = 3.0

    contexts = []
    pages: List[Page] = []

    # Helper to close all contexts safely
    async def close_all_contexts() -> None:
        for context in contexts:
            try:
                await context.close()
            except PlaywrightError:
                # Ignore close errors to avoid masking test failures
                pass

    try:
        # ------------------------------------------------------------------
        # STEP 1: Open 10 independent browser contexts and log in as admin1–admin10
        # ------------------------------------------------------------------
        for username in admin_users:
            context = await browser.new_context()
            page = await context.new_page()
            contexts.append(context)
            pages.append(page)

        async def login(page: Page, username: str) -> None:
            await page.goto(base_url, wait_until="networkidle")
            await page.fill(login_username_selector, username)
            await page.fill(login_password_selector, admin_password)
            async with page.expect_navigation(wait_until="networkidle"):
                await page.click(login_submit_selector)
            # Basic sanity check that login succeeded (adjust selector as needed)
            assert "welcome" in page.url.lower(), f"Login failed for {username}"

        # Perform logins concurrently
        await asyncio.gather(
            *[login(page, username) for page, username in zip(pages, admin_users)]
        )

        # ------------------------------------------------------------------
        # STEP 2: All navigate to Basic Configuration page
        # ------------------------------------------------------------------
        async def navigate_to_profiler_basic_config(page: Page) -> None:
            # If there is a direct URL, prefer that over navigation by click.
            # Example:
            # await page.goto("https://10.34.50.201/admin/profiler/basic", wait_until="networkidle")
            # For now, use navigation via link:
            await page.click(profiler_nav_selector)
            await page.wait_for_selector(profiler_name_input_selector)

        await asyncio.gather(
            *[navigate_to_profiler_basic_config(page) for page in pages]
        )

        # ------------------------------------------------------------------
        # STEP 3: Concurrently update Profiler Name and save
        # ------------------------------------------------------------------
        unique_profiler_names = [
            f"Profiler_Concurrent_{i}" for i in range(1, len(pages) + 1)
        ]

        # Store timing and result for each admin save
        save_results = []

        async def update_profiler_name(
            page: Page, new_name: str, admin_username: str
        ):

            # Ensure the field is visible and ready
            await page.wait_for_selector(profiler_name_input_selector)

            # Clear existing value and enter new one
            await page.fill(profiler_name_input_selector, "")
            await page.fill(profiler_name_input_selector, new_name)

            # Synchronize start of save as much as possible
            await asyncio.sleep(0)  # yield control to event loop

            start_time = time.perf_counter()
            try:
                # Wait for either success toast or some network stabilization
                async with page.expect_response(
                    lambda resp: resp.url.endswith(".cgi") and resp.request.method == "POST"
                ):
                    await page.click(profiler_save_button_selector)

                # Optionally wait for success toast or confirmation
                try:
                    await page.wait_for_selector(
                        profiler_success_toast_selector, timeout=5000
                    )
                    success = True
                    error_message = ""
                except PlaywrightError:
                    # If no toast, check for an error element
                    error_elements = await page.query_selector_all(
                        profiler_error_selector
                    )
                    if error_elements:
                        error_texts = [
                            (await e.text_content()) or "" for e in error_elements
                        ]
                        success = False
                        error_message = " | ".join(error_texts)
                    else:
                        # Neither success nor explicit error, treat as warning
                        success = False
                        error_message = "No explicit success or error message detected."

            except PlaywrightError as exc:
                success = False
                error_message = f"Playwright error during save: {exc}"

            end_time = time.perf_counter()
            response_time = end_time - start_time

            save_results.append(
                {
                    "admin": admin_username,
                    "profiler_name": new_name,
                    "success": success,
                    "error_message": error_message,
                    "response_time": response_time,
                }
            )

        # Launch concurrent updates
        await asyncio.gather(
            *[
                update_profiler_name(page, name, username)
                for page, name, username in zip(
                    pages, unique_profiler_names, admin_users
                )
            ]
        )

        # ------------------------------------------------------------------
        # STEP 4: Measure response times and assert performance/robustness
        # ------------------------------------------------------------------
        # Assert that no Playwright-level crashes occurred during saves
        assert len(save_results) == len(
            pages
        ), "Not all admin saves completed; potential crash or hang."

        # Log response times and errors for debugging
        slow_saves = []
        failed_saves = []
        for result in save_results:
            if not result["success"]:
                failed_saves.append(result)
            if result["response_time"] > max_acceptable_response_time_sec:
                slow_saves.append(result)

        # Assert performance: response times within acceptable limits
        assert (
            len(slow_saves) == 0
        ), f"Some saves exceeded {max_acceptable_response_time_sec}s: {slow_saves}"

        # Assert robustness: no explicit errors/locking issues surfaced
        assert (
            len(failed_saves) == 0
        ), f"Some saves failed or had errors: {failed_saves}"

        # ------------------------------------------------------------------
        # STEP 5: Refresh configuration page and verify final Profiler Name
        # ------------------------------------------------------------------
        # Choose one of the pages (e.g., last admin) to check final persisted value
        final_check_page = pages[-1]
        last_admin = admin_users[-1]
        last_profiler_name = unique_profiler_names[-1]

        # Refresh and re-open Profiler Basic Configuration to ensure fresh state
        await final_check_page.reload(wait_until="networkidle")
        await navigate_to_profiler_basic_config(final_check_page)

        # Read the current Profiler Name
        current_profiler_value = await final_check_page.input_value(
            profiler_name_input_selector
        )

        # ASSERTION: At most one configuration version persists, "last write wins"
        # In many systems, concurrent updates resolve with last request overwriting
        # previous ones. Here we assume the last admin's value should be persisted.
        assert (
            current_profiler_value == last_profiler_name
        ), (
            "Profiler configuration does not reflect the last successfully saved "
            f"value. Expected '{last_profiler_name}', got '{current_profiler_value}'."
        )

    finally:
        # ------------------------------------------------------------------
        # POSTCONDITIONS: Clean up all contexts
        # ------------------------------------------------------------------
        await close_all_contexts()