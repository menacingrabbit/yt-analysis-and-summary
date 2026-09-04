"""Convenient wrapper for summarisation.

Provides a ``summarise_and_save`` function that takes a transcript string,
uses the OpenRouter client to generate a summary, and writes the summary to a
specified output file.
"""

from pathlib import Path

from ..transcription.client import summarise
from ..utils.logging import logger


def summarise_and_save(transcript: str, out_dir: Path, base_name: str) -> Path:
    """Summarise *transcript* and write the result to ``<base_name>_summary.txt``.

    Args:
        transcript: Full transcript text.
        out_dir: Directory where the summary file will be placed.
        base_name: Base filename (stem, without extension) for the summary file.

    Returns:
        Path to the written summary file.
    """
    summary = summarise(transcript)
    summary_path = out_dir / f"{base_name}_summary.txt"
    summary_path.write_text(summary, encoding="utf-8")
    logger.info(f"Summary written to {summary_path}")
    return summary_path
