"""OpenRouter API client for transcription and summarisation.

Provides two high‑level functions:
- ``transcribe`` – send an audio file and receive a transcript string.
- ``summarise`` – send a transcript and receive a concise summary.

Both functions are wrapped with the ``retry`` decorator to handle transient
network issues.
"""

import os
import base64
from pathlib import Path
from typing import Any, Dict

import httpx

from ..config import get_api_key
from ..utils.logging import logger
from ..utils.retry import retry

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
    response.raise_for_status()
    return response.json()

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
    fmt = audio_path.suffix.lstrip('.').lower() or "wav"
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
    response.raise_for_status()
    return response.json()

@retry(attempts=3)
def transcribe(audio_path: Path) -> str:
    """Transcribe *audio_path* using OpenRouter's audio transcription endpoint.

    The function reads the file, encodes it as base64, and sends a JSON payload
    matching the official example. The model defaults to the value of the
    ``OPENROUTER_TRANSCRIBE_MODEL`` environment variable.
    """
    model = os.getenv("OPENROUTER_TRANSCRIBE_MODEL", "mistralai/voxtral-mini-transcribe")
    logger.info(f"Transcribing audio file {audio_path} with model {model}")
    data = _post_audio_json(audio_path, model)
    # The response follows OpenAI's Whisper schema: {"text": "..."}
    return data.get("text", "").strip()

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
