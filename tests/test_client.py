"""Tests for OpenRouter POST error-handling (transient vs permanent)."""

import httpx
import pytest

from src.summarisation.template import KEY_POINTS_HEADING, KEY_TAKEAWAY_HEADING
from src.transcription.client import (
    _AUDIO_API_URL,
    _CHAT_API_URL,
    _SUMMARY_PROMPT,
    _post,
    SummarisationError,
    summarise,
    TranscriptionError,
    TransientTranscriptionError,
    TransientSummarisationError,
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


def test_summary_prompt_requests_the_canonical_template():
    prompt = _SUMMARY_PROMPT.format(transcript="hello transcript")
    assert KEY_POINTS_HEADING in prompt
    assert prompt.index(KEY_POINTS_HEADING) < prompt.index(KEY_TAKEAWAY_HEADING)
    assert "Here is a summary" in prompt  # forbidden by instruction, not used literally
    assert "```\nhello transcript\n```" in prompt  # .format() still resolves


def _chat_response(payload):
    request = httpx.Request("POST", _CHAT_API_URL)
    return httpx.Response(200, json=payload, request=request)


def test_summarise_returns_content(mocker, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    mocker.patch(
        "httpx.post",
        return_value=_chat_response({"choices": [{"message": {"content": "  A summary.  "}}]}),
    )
    assert summarise("a transcript") == "A summary."


def test_summarise_empty_transcript_fails_without_calling_the_api(mocker, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    post = mocker.patch("httpx.post")
    with pytest.raises(SummarisationError):
        summarise("   \n  ")
    post.assert_not_called()  # deterministic: no credit spent on a doomed request


def test_summarise_blank_content_is_retried_then_fails(mocker, monkeypatch):
    """An empty completion is treated as transient and retried."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    post = mocker.patch(
        "httpx.post",
        return_value=_chat_response({"choices": [{"message": {"content": "   "}}]}),
    )
    with pytest.raises(TransientSummarisationError):
        summarise("a transcript")
    assert post.call_count == 3  # retry() makes 3 attempts


def test_summarise_no_choices_is_retried_then_fails(mocker, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key")
    post = mocker.patch("httpx.post", return_value=_chat_response({"choices": []}))
    with pytest.raises(TransientSummarisationError):
        summarise("a transcript")
    assert post.call_count == 3
