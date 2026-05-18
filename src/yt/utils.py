"""Utility helpers for the yt package.

Currently provides a `slugify` function that creates a safe filename from a
string, limiting the length to 80 characters and prefixing with a date.
"""

import re
import datetime
from pathlib import Path

_MAX_LEN = 80

def _clean(text: str) -> str:
    """Clean text for use as a filename slug."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[^\w\- ]+", "", text)
    text = re.sub(r"[\s_]+", "-", text)
    return text.lower()

def slugify(text: str) -> str:
    """Return a filesystem‑safe slug for *text*.

    The slug consists of a ``YYYYMMDD`` date prefix, a hyphen, and a cleaned
    version of *text* limited to ``_MAX_LEN`` characters.
    """
    date_prefix = datetime.date.today().strftime("%Y%m%d")
    clean = _clean(text)
    # Trim to fit within max length while keeping the date prefix
    if len(clean) > _MAX_LEN - len(date_prefix) - 1:
        clean = clean[: _MAX_LEN - len(date_prefix) - 1]
    return f"{date_prefix}-{clean}"
