"""Tests for src.utils.retry — only RetryableError is retried."""

import pytest

from src.utils.retry import RetryableError, retry


class PermanentError(Exception):
    """A fatal error that must not be retried."""


class TransientError(PermanentError, RetryableError):
    """A transient error that should be retried."""


def test_retries_transient_error(mocker):
    fn = mocker.Mock(side_effect=[TransientError(), TransientError(), "ok"])
    retried = retry(attempts=3)(fn)
    assert retried() == "ok"
    assert fn.call_count == 3


def test_does_not_retry_permanent_error(mocker):
    fn = mocker.Mock(side_effect=PermanentError("fatal"))
    retried = retry(attempts=3)(fn)
    with pytest.raises(PermanentError):
        retried()
    fn.assert_called_once()
