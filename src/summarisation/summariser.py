"""Convenient wrapper for summarisation.

Provides a ``summarise_and_save`` function that takes a transcript string,
uses the OpenRouter client to generate a summary, and writes the summary to a
specified output file.
"""

from pathlib import Path

from ..transcription.client import summarise
from ..utils.logging import logger

def summarise_and_save(transcript: str, out_dir: Path, slug: str) -> Path:
    """Summarise *transcript* and write the result to ``<slug>_summary.txt``.

    Args:
        transcript: Full transcript text.
        out_dir: Directory where the summary file will be placed.
        slug: Filename slug (already date‑prefixed) used for the summary file.

    Returns:
        Path to the written summary file.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = summarise(transcript)
    summary_path = out_dir / f"{slug}_summary.txt"
    summary_path.write_text(summary, encoding="utf-8")
    logger.info(f"Summary written to {summary_path}")
    return summary_path
