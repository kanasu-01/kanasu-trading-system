import time
from typing import Callable, Type, Tuple


class RetryPolicy:
    """
    Generic retry mechanism.
    """

    def __init__(
        self,
        max_retries: int = 3,
        delay_seconds: float = 1.0,
        retry_on: Tuple[Type[Exception], ...] = (Exception,),
    ):
        self.max_retries = max_retries
        self.delay_seconds = delay_seconds
        self.retry_on = retry_on

    def execute(self, fn: Callable, *args, **kwargs):
        last_exception = None

        for attempt in range(1, self.max_retries + 1):
            try:
                return fn(*args, **kwargs)
            except self.retry_on as e:
                last_exception = e
                if attempt < self.max_retries:
                    time.sleep(self.delay_seconds)

        raise last_exception
