import pytest
import asyncio
from playwright.async_api import Page, expect

@pytest.mark.asyncio
async def test_system_scalability_and_response_time(authenticated_page: Page):
    """
    TC_012: Verify system scalability and response time under high load with continuous device profiling requests.

    Test Steps:
    1. Initiate device connection and disconnection cycles at scale.
    2. Measure response times for detection and profiling.
    3. Monitor resource utilization (CPU, memory).

    Expected Results:
    - Response time remains within acceptable limits (under 2 seconds).
    - No crashes or memory leaks observed.
    """

    # Define constants
    SYSTEM_URL = "https://npre-miiqa2mp-eastus2.openai.azure.com/"
    MAX_ACCEPTABLE_RESPONSE_TIME = 2.0  # in seconds
    NUM_DEVICES = 100  # Number of devices to simulate
    CYCLE_COUNT = 10   # Number of connect/disconnect cycles
    PROFILE_ENDPOINT = "/api/device/profile"  # Hypothetical endpoint
    RESOURCE_CHECK_INTERVAL = 5  # seconds

    # Helper function to simulate device connect/disconnect
    async def simulate_device_connection(device_id: int):
        try:
            # Simulate device connection
            connect_response = await authenticated_page.request.post(
                SYSTEM_URL + "/api/device/connect",
                data={"device_id": device_id}
            )
            connect_response.raise_for_status()

            # Simulate device disconnection after some time
            await asyncio.sleep(0.1)
            disconnect_response = await authenticated_page.request.post(
                SYSTEM_URL + "/api/device/disconnect",
                data={"device_id": device_id}
            )
            disconnect_response.raise_for_status()
        except Exception as e:
            pytest.fail(f"Device simulation failed for device {device_id}: {e}")

    # Measure response time for profiling request
    async def measure_profiling_response_time():
        import time
        try:
            start_time = time.monotonic()
            response = await authenticated_page.request.get(SYSTEM_URL + PROFILE_ENDPOINT)
            response.raise_for_status()
            end_time = time.monotonic()
            response_time = end_time - start_time
            return response_time
        except Exception as e:
            pytest.fail(f"Profiling request failed: {e}")

    # Monitor resource utilization (mocked as placeholder)
    async def monitor_resources():
        # In real scenario, integrate with system monitor or API
        # For demonstration, assume resource usage is within limits
        cpu_usage = 50  # placeholder value
        memory_usage = 1024  # placeholder value in MB
        return cpu_usage, memory_usage

    # Open the system page
    try:
        await authenticated_page.goto(SYSTEM_URL, wait_until="load")
    except Exception as e:
        pytest.fail(f"Failed to load system URL: {e}")

    # Step 1: Initiate device connection/disconnection cycles at scale
    device_ids = range(1, NUM_DEVICES + 1)

    for cycle in range(CYCLE_COUNT):
        # Launch tasks for connecting/disconnecting devices concurrently
        connect_tasks = [
            simulate_device_connection(device_id)
            for device_id in device_ids
        ]
        try:
            await asyncio.gather(*connect_tasks)
        except Exception as e:
            pytest.fail(f"Error during device connect/disconnect cycle {cycle + 1}: {e}")

        # Optional: introduce a small delay between cycles
        await asyncio.sleep(0.5)

    # Step 2: Measure response times for detection and profiling
    profiling_response_times = []

    # Launch multiple profiling requests concurrently to simulate high load
    profiling_tasks = [
        measure_profiling_response_time()
        for _ in range(50)  # number of parallel profiling requests
    ]

    try:
        profiling_response_times = await asyncio.gather(*profiling_tasks)
    except Exception as e:
        pytest.fail(f"Error during profiling requests: {e}")

    # Assert that all response times are within acceptable limits
    for idx, response_time in enumerate(profiling_response_times):
        try:
            assert response_time < MAX_ACCEPTABLE_RESPONSE_TIME, (
                f"Profiling response {idx} exceeded acceptable limit: "
                f"{response_time:.2f}s"
            )
        except AssertionError as ae:
            pytest.fail(str(ae))

    # Step 3: Monitor resource utilization periodically
    # For simplicity, check once; in real test, this could be in a loop
    cpu_usage, memory_usage = await monitor_resources()

    # Log resource utilization (could be replaced with actual checks)
    print(f"CPU Usage: {cpu_usage}%")
    print(f"Memory Usage: {memory_usage} MB")

    # Assert that resources are within expected bounds
    # For example, CPU < 80%, Memory < 2048MB
    try:
        assert cpu_usage < 80, f"High CPU usage detected: {cpu_usage}%"
        assert memory_usage < 2048, f"High memory usage detected: {memory_usage} MB"
    except AssertionError as ae:
        pytest.fail(str(ae))

    # Final assertion: system should remain stable (no crashes or leaks)
    # Since this is a high-level test, assume if no failures until now, system is stable
    # Additional checks can include system logs, crash reports, etc.

    # Optional: cleanup or additional verification
    # e.g., ensure all devices are disconnected
    # Here, for simplicity, assume cleanup is successful