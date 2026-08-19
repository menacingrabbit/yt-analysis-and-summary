"""Integration tests for YouTube API accessibility via yt-dlp.

These tests make real network calls to YouTube and are designed to diagnose
HTTP 403 (Forbidden) errors that yt-dlp encounters. yt-dlp does not use the
official YouTube Data API; it scrapes public endpoints, which YouTube may
block with a 403.

Two layers of access are checked:
  1. **Metadata extraction** (``extract_info(download=False)``) — fetches the
     video title, formats, and stream URLs from YouTube's public pages/API.
  2. **Stream download** — makes a lightweight byte-range request to the
     audio stream URL to verify the actual media server responds, **without**
     downloading the full file.

Run a single test::

    pytest tests/test_youtube_api_access.py::TestYoutubeAccessibility::test_youtube_reachable -s

The ``-s`` flag disables output capture so diagnostic messages are visible.
"""

import re
import socket

import httpx
import pytest

from yt_dlp import YoutubeDL
from yt_dlp.utils import DownloadError

# This file makes real network calls to YouTube; skip it by default.
pytestmark = pytest.mark.network

# A widely available, short YouTube video used for connectivity checks.
_TEST_VIDEO_URL = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"

# A video the user reported getting a 403 on.
_USER_VIDEO_URL = "https://www.youtube.com/watch?v=u37h_2yliyY"

_BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

_HTTPS_403 = 403


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _check_connectivity():
    """Quick check that we have basic internet access to YouTube's domain."""
    try:
        socket.create_connection(("www.youtube.com", 443), timeout=10)
        return True
    except OSError:
        return False


def _extract_info_safe(url, opts):
    """Call ``extract_info`` with ``download=False`` and return (info, error).

    Returns ``(info, None)`` on success or ``(None, exception)`` on failure.
    The exception is always the raw yt-dlp exception so callers can inspect
    status codes and error messages.
    """
    try:
        with YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)
        return info, None
    except DownloadError as exc:
        return None, exc
    except Exception as exc:  # broad catch for diagnostics
        return None, exc


def _get_http_status(exc):
    """Extract the HTTP status code from a yt-dlp / urllib exception.

    yt-dlp wraps the underlying error so the original ``urllib`` exception is
    nested in ``exc.cause``. The HTTP status is accessible via
    ``exc.cause.code`` (``HTTPError``) or by scanning the message text.
    """
    cause = getattr(exc, "cause", None)
    code = getattr(cause, "code", None)
    if code is not None:
        return int(code)

    text = str(exc)
    match = re.search(r"HTTP error (\d+)", text)
    if match:
        return int(match.group(1))

    match = re.search(r"\b(403)\b", text)
    if match:
        return int(match.group(1))

    return None


def _make_ydl_opts(**overrides):
    """Build yt-dlp options matching production defaults.

    Uses the ANDROID player client, which avoids the HTTP 403 that YouTube
    returns for stream downloads via the default ANDROID_VR client.
    """
    opts = {
        "quiet": True,
        "no_warnings": True,
        "http_headers": {"User-Agent": _BROWSER_UA},
        "extractor_args": {"youtube": {"player_client": ["ANDROID"]}},
    }
    opts.update(overrides)
    return opts


def _get_best_audio_url(info):
    """Return the stream URL of the best audio format from an info dict."""
    formats = info.get("formats", []) or []
    # Prefer formats that actually have audio
    audio = [
        f
        for f in formats
        if f.get("acodec")
        and f.get("acodec") != "none"
        and f.get("ext") in ("m4a", "webm", "mp3", "mp4")
    ]
    if not audio:
        return None, None
    # Sort by tbr (bitrate in kbps), descending
    audio.sort(key=lambda f: f.get("tbr", 0), reverse=True)
    best = audio[0]
    return best.get("url"), best.get("format_id")


def _check_stream_url(url):
    """Make a lightweight Range request to verify the stream URL is accessible.

    Sends ``Range: bytes=0-1023`` (first 1 KB) to avoid downloading the full
    media. Returns ``(status_code, error)`` — ``status_code`` is None on
    connection errors.
    """
    if not url:
        return None, "No stream URL available"
    try:
        resp = httpx.head(
            url,
            headers={"User-Agent": _BROWSER_UA, "Range": "bytes=0-1023"},
            timeout=15,
            follow_redirects=True,
        )
        return resp.status_code, None
    except Exception as exc:  # broad catch for diagnostics
        return None, str(exc)


# ---------------------------------------------------------------------------
# Core accessibility tests
# ---------------------------------------------------------------------------


class TestYoutubeAccessibility:
    """Tests that verify YouTube is reachable via yt-dlp."""

    def test_youtube_reachable(self):
        """Verify that YouTube metadata can be fetched without errors.

        This is the primary accessibility check. If YouTube returns a 403,
        the test failure message includes diagnostic information to help
        understand the cause.
        """
        if not _check_connectivity():
            pytest.fail(
                "No network connectivity to www.youtube.com:443 – "
                "check your internet connection.",
                pytrace=False,
            )

        info, error = _extract_info_safe(_TEST_VIDEO_URL, _make_ydl_opts())

        if error is not None:
            status = _get_http_status(error)
            _raise_403_diagnostics(status, error)

        assert info is not None, "extract_info returned None unexpectedly"
        assert "id" in info, "Video info missing 'id' field"
        assert "title" in info, "Video info missing 'title' field"

    def test_youtube_no_403_on_info_extraction(self):
        """Specifically assert that the metadata endpoint does not return 403.

        YouTube's metadata page (the embed/watch page) is a separate endpoint
        from the video stream server. A 403 here indicates a different problem
        than a stream-level 403.
        """
        info, error = _extract_info_safe(_TEST_VIDEO_URL, _make_ydl_opts())

        if error is None:
            assert info is not None
            return

        status = _get_http_status(error)
        assert status != _HTTPS_403, (
            f"YouTube metadata endpoint returned HTTP 403.\n"
            f"yt-dlp error: {error}\n\n"
            "This differs from a stream-level 403. See "
            "test_youtube_reachable for troubleshooting."
        )

    def test_youtube_stream_url_accessible(self):
        """Verify the actual audio stream URL responds (not just metadata).

        This catches the case where metadata extraction succeeds but the
        videoplayback server (googlevideo.com) returns 403 — which is the
        exact scenario the user reported. Uses a lightweight HEAD request
        with a small byte range so the full file is never downloaded.
        """
        info, error = _extract_info_safe(_TEST_VIDEO_URL, _make_ydl_opts())
        if error is not None:
            pytest.skip(f"Info extraction failed: {error}")

        stream_url, fmt_id = _get_best_audio_url(info)
        assert stream_url is not None, (
            "No audio formats with codecs found in video info. "
            "This may indicate the JavaScript runtime is missing."
        )

        print(f"\nTesting stream URL (format_id={fmt_id})...")
        status, err = _check_stream_url(stream_url)

        if err:
            pytest.fail(
                f"Failed to connect to YouTube stream URL: {err}\n"
                f"Stream URL: {stream_url[:100]}..."
            )

        print(f"Stream URL responded: HTTP {status}")
        assert status in (200, 206), (
            f"YouTube stream URL returned HTTP {status}.\n"
            "A 403 here means the googlevideo.com server is blocking the "
            "request — typically due to the YouTube client type yt-dlp uses.\n\n"
            "Remedy: configure yt-dlp to use the ANDROID player client:\n"
            "  In src/yt/downloader.py, add to ydl_opts:\n"
            "    'extractor_args': {'youtube': {'player_client': ['ANDROID']}}\n"
            f"Stream URL: {stream_url[:120]}..."
        )


# ---------------------------------------------------------------------------
# YouTube client tests (diagnoses 403-on-download root cause)
# ---------------------------------------------------------------------------


class TestYoutubeClientAccessibility:
    """Tests that try different YouTube client types.

    YouTube exposes its content through several client types (WEB, IOS,
    ANDROID, ANDROID_VR, etc.). yt-dlp defaults to ANDROID_VR. We found that
    ANDROID_VR can return 403 on stream downloads while ANDROID succeeds.
    """

    @pytest.mark.parametrize("client", ["ANDROID", "ANDROID_VR", "IOS", "WEB"])
    def test_client_can_extract_stream_url(self, client):
        """Check that each YouTube client can produce a usable stream URL.

        Only tests metadata extraction (download=False) so it is lightweight.
        """
        opts = _make_ydl_opts(extractor_args={"youtube": {"player_client": [client]}})
        info, error = _extract_info_safe(_TEST_VIDEO_URL, opts)
        if error is not None:
            status = _get_http_status(error)
            print(f"  Client {client}: error, HTTP status={status}, msg={error}")
            # Not all clients support all videos — skip rather than fail.
            pytest.skip(f"Client {client} could not extract info: {error}")

        stream_url, fmt_id = _get_best_audio_url(info)
        if stream_url is None:
            pytest.skip(f"Client {client}: no audio formats found " "(JS runtime may be missing)")

        print(f"  Client {client}: OK — format_id={fmt_id}")
        assert stream_url is not None


# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------


def _raise_403_diagnostics(status, error):
    """Fail with a detailed 403 diagnostic message."""
    if status == _HTTPS_403:
        pytest.fail(
            "YouTube returned HTTP 403 (Forbidden).\n"
            "This typically means YouTube is blocking the request.\n\n"
            "Possible causes & remedies:\n"
            "  1. IP-level block / rate limit — try again in a few minutes "
            "or use a different network/VPN.\n"
            "  2. yt-dlp version is outdated — upgrade with "
            "'pip install -U yt-dlp'.\n"
            "  3. YouTube client type (ANDROID_VR) is blocked — switch to "
            "ANDROID client by adding to ydl_opts in src/yt/downloader.py:\n"
            "      'extractor_args': {'youtube': {'player_client': ['ANDROID']}}\n"
            "  4. User-Agent is being rejected — the test already uses a "
            "browser User-Agent.\n"
            "  5. JavaScript runtime missing — install Node.js or Deno so "
            "yt-dlp can fully process YouTube's player JS.\n"
            "  6. Cloudflare bot detection — try from a different IP.\n\n"
            f"Full error: {error}",
            pytrace=False,
        )
    else:
        pytest.fail(
            f"Network/API error (HTTP status: {status}): {error}\n\n"
            "This is not a 403. Check the error message above for details.",
            pytrace=False,
        )


class TestYoutubeDiagnostics:
    """Informational tests that print diagnostic data about the yt-dlp setup."""

    def test_youtube_version(self):
        """Print the installed yt-dlp version for debugging."""
        from yt_dlp.version import __version__

        print(f"\nyt-dlp version: {__version__}")
        assert __version__ is not None

    def test_youtube_url_validation(self):
        """Ensure the test URL is a valid YouTube URL before running tests."""
        from src.cli import validate_youtube_url

        validate_youtube_url(_TEST_VIDEO_URL)

    def test_js_runtime_available(self):
        """Check whether a JavaScript runtime is available for yt-dlp.

        yt-dlp needs Node.js or Deno to fully process YouTube's player JavaScript.
        Without it, some formats may be missing and extraction can fail.
        """
        import shutil

        runtimes = ["node", "deno", "bun", "quickjs"]
        available = [r for r in runtimes if shutil.which(r)]
        if available:
            print(f"\nJS runtimes available: {available}")
        else:
            print(
                "\nNo JavaScript runtime found. yt-dlp will work but some "
                "YouTube formats may be missing. Install Node.js or Deno."
            )
        # Don't fail — yt-dlp can work without JS for basic formats
        assert True


# ---------------------------------------------------------------------------
# User-specific video test
# ---------------------------------------------------------------------------


class TestUserVideoAccess:
    """Tests the specific video the user reported getting a 403 on."""

    def test_user_video_metadata(self):
        """Verify that metadata extraction works for the user's video."""
        if not _check_connectivity():
            pytest.skip("No network connectivity")

        info, error = _extract_info_safe(_USER_VIDEO_URL, _make_ydl_opts())
        if error is not None:
            status = _get_http_status(error)
            _raise_403_diagnostics(status, error)

        assert info is not None
        print(f"\nTitle: {info.get('title')}")

    def test_user_video_android_client_stream(self):
        """Test that the ANDROID client can access the user's video stream.

        This is the recommended fix for the 403 issue: use the ANDROID player
        client instead of the default ANDROID_VR.
        """
        opts = _make_ydl_opts(extractor_args={"youtube": {"player_client": ["ANDROID"]}})
        info, error = _extract_info_safe(_USER_VIDEO_URL, opts)
        if error is not None:
            pytest.skip(f"ANDROID client failed to extract info: {error}")

        stream_url, fmt_id = _get_best_audio_url(info)
        if stream_url is None:
            pytest.skip("No audio stream URL found")

        print(f"\nANDROID client stream URL (format_id={fmt_id}):")
        status, err = _check_stream_url(stream_url)
        print(f"Stream URL responded: HTTP {status}")
        assert status in (200, 206), (
            f"ANDROID client stream URL returned HTTP {status} for the user's "
            f"video. Error: {err}"
        )
