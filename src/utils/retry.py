"""Retry decorator using tenacity.

Provides a simple ``retry`` decorator that applies exponential back‑off
with a configurable number of attempts. Used for network calls to the OpenRouter
API.
"""

from tenacity import retry as _tenacity_retry, stop_after_attempt, wait_exponential

def retry(attempts: int = 3):
    """Return a tenacity ``retry`` decorator.

    Args:
        attempts: Maximum number of attempts.
    """
    # Exponential back‑off: start at 1 s, double each retry, max 10 s.
    return _tenacity_retry(
        stop=stop_after_attempt(attempts),
        wait=wait_exponential(multiplier=1, min=1, max=10),
        reraise=True,
    )
