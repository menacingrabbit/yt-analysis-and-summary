"""Utility helpers for the yt package.

Provides a ``slugify`` function that creates a safe, date-prefixed filename
from a string, and a ``clean_title`` helper it uses internally.
"""

import datetime
import re

_MAX_LEN = 80
_DATE_LEN = len(datetime.date.today().strftime("%Y%m%d"))

# Leading YYYYMMDD- date prefix that slugify() prepends to filenames.
_DATE_PREFIX_RE = re.compile(r"^\d{8}-")
# Trailing -<video id> that downloader adds to audio filenames.
_VIDEO_ID_SUFFIX_RE = re.compile(r"-[A-Za-z0-9_-]{11}$")


def clean_title(text: str) -> str:
    """Clean *text* for use inside a filename slug."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\w\- ]+", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.lower()


def slugify(text: str) -> str:
    """Return a filesystem-safe slug for *text*.

    The slug consists of a ``YYYYMMDD`` date prefix, a hyphen, and a cleaned
    version of *text* truncated to fit within ``_MAX_LEN`` characters.
    """
    date_prefix = datetime.date.today().strftime("%Y%m%d")
    cleaned = clean_title(text)[: _MAX_LEN - _DATE_LEN - 1]
    return f"{date_prefix}-{cleaned}"


def title_from_stem(stem: str) -> str:
    """Best-effort recovery of a readable title from an audio filename stem.

    Used when the real video title is unavailable (e.g. resuming a legacy
    download). Strips the date prefix and trailing video ID, then turns the
    slug's hyphens back into spaces. The result is lossy: case and accents were
    already removed when the slug was created.
    """
    stem = _VIDEO_ID_SUFFIX_RE.sub("", _DATE_PREFIX_RE.sub("", stem))
    return stem.replace("-", " ").strip()
