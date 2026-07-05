"""Retry decorator using tenacity.

Provides a simple ``retry`` decorator that applies exponential back‑off
with a configurable number of attempts. Used for network calls to the OpenRouter
API. Also provides visibility into retry attempts via logging.
"""

from tenacity import (
    retry as _tenacity_retry,
    stop_after_attempt,
    wait_exponential,
)

from .logging import logger


def _log_retry(retry_state) -> None:
    """Log retry attempts with attempt number and wait information."""
    attempt = retry_state.attempt_number
    exception = retry_state.outcome.exception() if retry_state.outcome else None
    exc_name = type(exception).__name__ if exception else "unknown"
    logger.warning(f"Retry attempt {attempt} after {exc_name} error, retrying...")


def retry(attempts: int = 3):
    """Return a tenacity ``retry`` decorator.

    Args:
        attempts: Maximum number of attempts.
    """
    # Exponential back‑off: start at 1 s, double each retry, max 10 s.
    return _tenacity_retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        before_sleep=_log_retry,
        reraise=True,
    )
