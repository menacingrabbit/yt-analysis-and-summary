"""Logging setup using stdlib ``logging`` with a rich console handler.

Provides a module-level ``logger`` (a plain ``logging.Logger``) wired to a
``rich.logging.RichHandler`` so levels, ``logger.exception()`` tracebacks, and
markup-safe messages all behave as expected. Call :func:`configure` to set the
verbosity (e.g. from a CLI flag).
"""

import logging

from rich.logging import RichHandler

logger = logging.getLogger("yt-analysis-and-summary")
logger.addHandler(RichHandler(rich_tracebacks=True, keywords=["INFO", "WARN", "ERROR", "DEBUG"]))
logger.setLevel(logging.INFO)


def configure(level: int = logging.INFO) -> None:
    """Set the level for this project's logger."""
    logger.setLevel(level)
