"""Convenient wrapper for summarisation.

Provides a ``summarise_and_save`` function that takes a transcript string,
uses the OpenRouter client to generate a summary, and writes the summary to a
specified output file.
"""

from pathlib import Path

from ..transcription.client import SummarisationError, summarise
from ..utils.logging import logger
from .template import is_empty_summary, render_summary


def summarise_and_save(transcript: str, out_dir: Path, base_name: str, *, title: str) -> Path:
    """Summarise *transcript* and write the result to ``<base_name>_summary.txt``.

    The written file always follows the canonical template from
    :mod:`src.summarisation.template` (title, key points, takeaway).

    Args:
        transcript: Full transcript text.
        out_dir: Directory where the summary file will be placed.
        base_name: Base filename (stem, without extension) for the summary file.
        title: Video title used as the document heading.

    Returns:
        Path to the written summary file.

    Raises:
        SummarisationError: Propagated from :func:`summarise` when the
            transcript is empty or the model returns no content, and raised
            here when the response carries no usable points or takeaway (for
            example headings with no body). A summary is never silently
            replaced by a placeholder, so the caller can fail the run.
    """
    # Raises rather than returning "" — an empty summary is a pipeline failure.
    raw = summarise(transcript)
    # The model can answer without failing while saying nothing: "## Key
    # Takeaway" alone is non-blank but has no content to render. Catch that
    # here, where the canonical template defines what "usable" means.
    if is_empty_summary(raw):
        raise SummarisationError(
            f"Summarisation returned no usable content ({len(raw)} chars of headings/structure only)"
        )
    summary = render_summary(title, raw)
    summary_path = out_dir / f"{base_name}_summary.txt"
    summary_path.write_text(summary, encoding="utf-8")
    logger.info(f"Summary written to {summary_path}")
    return summary_path
