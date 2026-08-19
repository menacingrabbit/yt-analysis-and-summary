"""Retry decorator using tenacity.

Provides a ``retry`` decorator that applies exponential back-off for a
configurable number of attempts, retrying only transient (``RetryableError``)
failures. Used for network calls to the OpenRouter API.
"""

import logging

from tenacity import (
    before_sleep_log,
    retry as _tenacity_retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from .logging import logger


class RetryableError(Exception):
    """Marker base for errors that are transient and worth retrying."""


def retry(attempts: int = 3):
    """Return a tenacity ``retry`` decorator that retries ``RetryableError``.

    Args:
        attempts: Maximum number of attempts.
    """
    return _tenacity_retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        retry=retry_if_exception_type(RetryableError),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
