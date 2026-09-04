"""Audio file splitting utilities.

Splits large audio files into consecutive chunks of at most
``DEFAULT_CHUNK_DURATION`` seconds using ffmpeg's segment muxer.
Stream copy is used (``-c copy``) so no re-encoding occurs — this is fast
and lossless.
"""

import shutil
import subprocess
import tempfile
from pathlib import Path

from ..utils.logging import logger

# YouTube videos longer than ~10 minutes can exceed the OpenRouter
# transcription API's input limit. We split at 590 seconds (just under
# 10 minutes) to stay safely within the limit.
DEFAULT_CHUNK_DURATION = 590

# Prefix for the temporary directory that split_audio creates. cleanup_chunks
# uses it to recognise (and only ever remove) temp dirs it owns, never a
# directory that happens to contain a user's files.
_TEMP_DIR_PREFIX = "yt-split-"


def split_audio(audio_path: Path, chunk_duration: int = DEFAULT_CHUNK_DURATION) -> list[Path]:
    """Split *audio_path* into consecutive chunks of at most *chunk_duration* seconds.

    If the file is shorter than *chunk_duration* or ffmpeg is unavailable,
    a single-element list containing *audio_path* is returned (no split).

    Args:
        audio_path: Path to the input audio file (any ffmpeg-supported format).
        chunk_duration: Maximum duration of each chunk in seconds.

    Returns:
        Ordered list of chunk file paths. The first element is the
        beginning of the file and the last element is the end.
    """
    # Short-enough files are returned unchanged — no need to split.
    duration = _get_audio_duration(audio_path)
    if duration is not None and duration <= chunk_duration:
        logger.info(
            f"File is {duration:.1f}s — no splitting needed " f"(limit: {chunk_duration}s)."
        )
        return [audio_path]

    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        logger.warning("ffmpeg not found — cannot split audio file. " "Returning unsplit file.")
        return [audio_path]

    # Create a temporary directory for the chunk files.
    temp_dir = Path(tempfile.mkdtemp(prefix=_TEMP_DIR_PREFIX))
    chunk_pattern = temp_dir / "part_%03d.mp3"

    cmd = [
        ffmpeg_exe,
        "-y",  # overwrite outputs
        "-i",
        str(audio_path),
        "-f",
        "segment",
        "-segment_time",
        str(chunk_duration),
        "-c",
        "copy",
        "-reset_timestamps",
        "1",
        str(chunk_pattern),
    ]

    logger.info(f"Splitting {audio_path.name} into {chunk_duration}s chunks...")
    try:
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except subprocess.SubprocessError as exc:
        logger.warning(f"ffmpeg split failed ({exc}); returning unsplit file.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return [audio_path]

    # Collect chunk files in order.
    chunks = sorted(temp_dir.glob("part_*.mp3"))
    if not chunks:
        logger.warning("ffmpeg produced no chunks; returning unsplit file.")
        shutil.rmtree(temp_dir, ignore_errors=True)
        return [audio_path]

    logger.info(f"Split into {len(chunks)} chunk(s).")
    return chunks


def cleanup_chunks(chunks: list[Path]) -> None:
    """Remove temporary chunk files and the temp dir that produced them.

    Only directories created by :func:`split_audio` (identified by their
    ``yt-split-`` prefix) are removed. If *chunks* contains an unsplit original
    file or files elsewhere on disk, they are left untouched.

    Args:
        chunks: List of chunk file paths (as returned by ``split_audio``).
    """
    if not chunks:
        return

    # Only touch files that live inside a splitter-owned temp dir, so a user's
    # original audio file (e.g. the unsplit result) is never removed.
    temp_dirs = {chunk.parent for chunk in chunks if chunk.parent.name.startswith(_TEMP_DIR_PREFIX)}

    for chunk in chunks:
        if chunk.parent in temp_dirs:
            try:
                chunk.unlink()
            except OSError:
                pass  # already gone — nothing to clean up

    for temp_dir in temp_dirs:
        shutil.rmtree(temp_dir, ignore_errors=True)


def _get_audio_duration(path: Path) -> float | None:
    """Return the duration of *path* in seconds, or None if it cannot be determined.

    Uses ffprobe (shipped with ffmpeg) for an accurate reading without
    decoding the file.
    """
    ffprobe_exe = shutil.which("ffprobe")
    if not ffprobe_exe:
        return None

    try:
        result = subprocess.run(
            [
                ffprobe_exe,
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        return float(result.stdout.strip())
    except (subprocess.SubprocessError, ValueError):
        return None
