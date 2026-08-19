"""Utility helpers for the yt package.

Provides a ``slugify`` function that creates a safe, date-prefixed filename
from a string, and a ``clean_title`` helper it uses internally.
"""

import datetime
import re

_MAX_LEN = 80
_DATE_LEN = len(datetime.date.today().strftime("%Y%m%d"))


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
