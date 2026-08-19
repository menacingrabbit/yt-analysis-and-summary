"""OpenRouter API client for transcription and summarisation.

Provides two high‑level functions:
- ``transcribe`` – send an audio file and receive a transcript string.
- ``summarise`` – send a transcript and receive a concise summary.

Both functions are wrapped with the ``retry`` decorator to handle transient
network issues.
"""

import os
import base64
import re
from pathlib import Path
from typing import Any, Dict, NoReturn

import httpx

from ..config import get_api_key
from ..utils.logging import logger
from ..utils.retry import retry


class TranscriptionError(RuntimeError):
    """Raised when audio transcription fails due to API or network issues."""

    pass


class SummarisationError(RuntimeError):
    """Raised when summarisation fails due to API or network issues."""

    pass


# OpenRouter endpoint for audio transcriptions (expects JSON with base64 audio).
_AUDIO_API_URL = "https://openrouter.ai/api/v1/audio/transcriptions"
# Chat endpoint for summarisation.
_CHAT_API_URL = "https://openrouter.ai/api/v1/chat/completions"


def _get_headers() -> dict:
    """Get headers with API key, evaluated lazily."""
    return {"Authorization": f"Bearer {get_api_key()}"}


def _post_chat(payload: Dict[str, Any]) -> Dict[str, Any]:
    """POST JSON payload to the chat endpoint and return the parsed JSON."""
    response = httpx.post(
        _CHAT_API_URL,
        headers={**_get_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=60.0,
    )
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        _raise_with_details(exc, SummarisationError)


def _raise_with_details(exc: httpx.HTTPStatusError, error_cls: type) -> NoReturn:
    """Raise a custom error with more user-friendly details from an HTTPStatusError.

    Follows OpenRouter's error format: {"error": {"code": number, "message": string, ...}}
    See: https://openrouter.ai/docs/api/reference/errors-and-debugging
    """
    response = exc.response
    status = response.status_code

    # Parse OpenRouter error response format (try JSON first)
    error_msg = ""
    metadata = None
    content_type = response.headers.get("content-type", "")
    response_text = response.text

    # Check if response is HTML (Cloudflare error pages often have wrong content-type)
    is_html = (
        "text/html" in content_type
        or response_text.strip().startswith("<!DOCTYPE html>")
        or response_text.strip().startswith("<html")
    )

    if is_html:
        # Extract title from Cloudflare error page for cleaner message
        title_match = re.search(r"<title>([^<]+)</title>", response_text)
        if title_match:
            error_msg = title_match.group(1)
        else:
            error_msg = response.reason_phrase or f"HTTP {status} error"
    else:
        try:
            error_data = response.json()
            error_obj = error_data.get("error", {})
            error_msg = error_obj.get("message", "")
            metadata = error_obj.get("metadata")
        except Exception:
            error_msg = response_text or ""

    # Ensure we have a meaningful error message
    if not error_msg:
        error_msg = response.reason_phrase or f"HTTP {status} error"

    # Friendly messages based on status code (following OpenRouter docs)
    status_hints = {
        400: "Invalid request - check your parameters",
        401: "Authentication failed - check your OPENROUTER_API_KEY",
        402: "Payment required - add more credits to your OpenRouter account",
        403: "Access forbidden - check permissions or content policy",
        404: "Resource not found",
        408: "Request timeout - try again",
        429: "Rate limit exceeded - wait before retrying",
        502: "Bad gateway - provider returned invalid response",
        503: "Service unavailable - no providers available",
        504: "Gateway timeout - provider took too long to respond",
    }
    hint = status_hints.get(status)
    if hint:
        full_msg = f"{error_msg} ({hint})"
    else:
        full_msg = f"{error_msg} (HTTP {status})"

    # Log metadata for debugging if present (e.g., mid-stream streaming errors)
    if metadata:
        logger.debug(f"API error metadata: {metadata}")

    raise error_cls(full_msg) from exc


def _post_audio_json(audio_path: Path, model: str) -> Dict[str, Any]:
    """POST JSON payload with base64‑encoded audio to the transcription endpoint.

    The payload follows the OpenRouter example:
    {
        "model": "mistralai/voxtral-mini-transcribe",
        "input_audio": {
            "data": "<base64‑encoded‑audio>",
            "format": "wav"
        }
    }
    """
    audio_bytes = audio_path.read_bytes()
    audio_b64 = base64.b64encode(audio_bytes).decode()
    # Determine format from file extension; default to "wav" if unknown.
    fmt = audio_path.suffix.lstrip(".").lower() or "wav"

    payload = {
        "model": model,
        "input_audio": {"data": audio_b64, "format": fmt},
    }

    response = httpx.post(
        _AUDIO_API_URL,
        headers={**_get_headers(), "Content-Type": "application/json"},
        json=payload,
        timeout=60.0,
    )
    try:
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as exc:
        _raise_with_details(exc, TranscriptionError)


@retry(attempts=3)
def transcribe(audio_path: Path) -> str:
    """Transcribe *audio_path* using OpenRouter's audio transcription endpoint.

    The function reads the file, encodes it as base64, and sends a JSON payload
    matching the official example. The model defaults to the value of the
    ``OPENROUTER_TRANSCRIBE_MODEL`` environment variable.
    """
    # model backup #1: mistralai/voxtral-mini-transcribe
    model = os.getenv(
        "OPENROUTER_TRANSCRIBE_MODEL", "mistralai/voxtral-mini-transcribe"
    )
    logger.info(f"Transcribing audio file {audio_path} with model {model}")
    data = _post_audio_json(audio_path, model)
    # The response follows OpenAI's Whisper schema: {"text": "..."}
    return data.get("text", "").strip()


@retry(attempts=3)
def transcribe_split(
    audio_path: Path, chunk_duration: int = 590
) -> str:
    """Transcribe *audio_path*, splitting into chunks if too long.

    If the audio exceeds *chunk_duration* seconds, it is split into
    consecutive parts, each transcribed separately, and the transcripts
    are concatenated in order. This works around OpenRouter's ~10-minute
    input limit for long audio files.

    Args:
        audio_path: Path to the audio file to transcribe.
        chunk_duration: Maximum seconds per chunk (default 590, just under
            10 minutes).

    Returns:
        The combined transcript string.
    """
    from ..audio.splitter import split_audio, cleanup_chunks

    chunks = split_audio(audio_path, chunk_duration=chunk_duration)

    logger.info(
        f"Transcribing {len(chunks)} chunk(s) from {audio_path.name}"
    )

    try:
        if len(chunks) == 1 and chunks[0].resolve() == audio_path.resolve():
            # No splitting occurred — transcribe the original file directly.
            return transcribe(audio_path)

        parts = []
        for i, chunk_path in enumerate(chunks, start=1):
            logger.info(f"Transcribing chunk {i}/{len(chunks)}: {chunk_path.name}")
            text = transcribe(chunk_path)
            if text:
                parts.append(f"--- Part {i} ---\n{text}")

        combined = "\n".join(parts)
        return combined.strip()
    finally:
        if len(chunks) > 1:
            cleanup_chunks(chunks)


@retry(attempts=3)
def summarise(transcript: str) -> str:
    """Summarise *transcript* using OpenRouter's chat endpoint.

    Sends a concise prompt that asks for a bullet‑point summary.
    """
    logger.info(f"Summarising transcript (length={len(transcript)} chars)")
    prompt = (
        "Summarise the following transcript in bullet points, focusing on the main ideas, arguments, and conclusions. Write detailed but concise summaries. Finally, write 1 sentence summarising the key takeaway. Use concise language.\n\n"
        "```\n"
        f"{transcript}\n"
        "```"
    )
    payload = {
        "model": os.getenv("OPENROUTER_SUMMARISE_MODEL", "anthropic/claude-3-5-sonnet"),
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": 1024,
    }
    data = _post_chat(payload)
    return data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
