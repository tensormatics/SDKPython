import logging
import time
from typing import Any, Callable, Optional, TypeVar, Union

T = TypeVar("T")


def poll(
    function: Callable[..., T],
    condition: Callable[[T], bool],
    interval: float = 2.0,
    timeout: Optional[float] = None,
    max_retries: Optional[int] = None,
    args: tuple = (),
    kwargs: dict = None,
    on_success: Optional[Callable[[T], Any]] = None,
    on_timeout: Optional[Callable[[int, Optional[T]], Any]] = None,
    on_exception: Optional[Callable[[Exception], Any]] = None,
) -> Union[T, None]:
    """
    Poll a function at specified intervals until a condition is met.

    Args:
        function: The function to call
        condition: Function that takes the return value of `function` and returns True when polling should stop
        interval: Time in seconds between calls
        timeout: Maximum time in seconds to poll before giving up
        max_retries: Maximum number of retries before giving up
        args: Positional arguments to pass to `function`
        kwargs: Keyword arguments to pass to `function`
        on_success: Callback function to call with the successful result
        on_timeout: Callback function to call on timeout with the number of attempts and last result
        on_exception: Callback function to call when an exception occurs in `function`

    Returns:
        The last return value from `function` or None if timeout/max_retries was reached

    Examples:
        ```python
        # Poll until a job is complete
        result = poll(
            function=check_job_status,
            condition=lambda status: status == "completed",
            interval=5.0,
            timeout=300,
            args=(job_id,)
        )

        # Poll with a custom breaking condition
        result = poll(
            function=get_task_result,
            condition=lambda r: r["status"] != "in_progress",
            interval=2.0,
            max_retries=10
        )
        ```
    """
    if kwargs is None:
        kwargs = {}

    start_time = time.time()
    attempts = 0
    last_result = None

    while True:
        try:
            attempts += 1
            last_result = function(*args, **kwargs)

            # Check if condition is satisfied
            if condition(last_result):
                if on_success:
                    on_success(last_result)
                return last_result

        except Exception as e:
            if on_exception:
                on_exception(e)
            logging.error(f"Exception in poll function: {str(e)}")

        # Check if we've reached timeout
        if timeout is not None and time.time() - start_time > timeout:
            if on_timeout:
                on_timeout(attempts, last_result)
            logging.warning(
                f"Polling timed out after {timeout} seconds ({attempts} attempts)"
            )
            return last_result

        # Check if we've reached max retries
        if max_retries is not None and attempts >= max_retries:
            if on_timeout:
                on_timeout(attempts, last_result)
            logging.warning(f"Polling reached max retries: {max_retries}")
            return last_result

        # Wait before next attempt
        time.sleep(interval)
