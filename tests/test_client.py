"""Tests for OpenRouter POST error-handling (transient vs permanent)."""

import httpx
import pytest

from src.transcription.client import (
    _AUDIO_API_URL,
    _post,
    TranscriptionError,
    TransientTranscriptionError,
)


def _response(status):
    request = httpx.Request("POST", _AUDIO_API_URL)
    return httpx.Response(status, json={"error": {"message": "boom"}}, request=request)


def test_post_raises_transient_for_retryable_status(mocker, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mocker.patch("httpx.post", return_value=_response(429))
    with pytest.raises(TransientTranscriptionError):
        _post(_AUDIO_API_URL, {}, TranscriptionError, TransientTranscriptionError)


def test_post_raises_permanent_for_fatal_status(mocker, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mocker.patch("httpx.post", return_value=_response(401))
    with pytest.raises(TranscriptionError) as exc_info:
        _post(_AUDIO_API_URL, {}, TranscriptionError, TransientTranscriptionError)
    assert not isinstance(exc_info.value, TransientTranscriptionError)


def test_post_returns_json_on_success(mocker, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mocker.patch("httpx.post", return_value=_response(200))
    data = _post(_AUDIO_API_URL, {}, TranscriptionError, TransientTranscriptionError)
    assert data == {"error": {"message": "boom"}}
