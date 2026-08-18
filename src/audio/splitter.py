"""Audio file splitting utilities.

Splits large audio files into consecutive chunks of at most
``_DEFAULT_CHUNK_DURATION`` seconds using ffmpeg's segment muxer.
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
_DEFAULT_CHUNK_DURATION = 590


def split_audio(
    audio_path: Path, chunk_duration: int = _DEFAULT_CHUNK_DURATION
) -> list[Path]:
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
    # Check if the file is already short enough — no need to split.
    if _get_audio_duration(audio_path) is not None:
        duration = _get_audio_duration(audio_path)
        if duration is not None and duration <= chunk_duration:
            logger.info(
                f"File is {duration:.1f}s — no splitting needed "
                f"(limit: {chunk_duration}s)."
            )
            return [audio_path]

    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        logger.warning(
            "ffmpeg not found — cannot split audio file. "
            "Returning unsplit file."
        )
        return [audio_path]

    # Create a temporary directory for the chunk files.
    temp_dir = Path(tempfile.mkdtemp(prefix="yt-split-"))
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

    logger.info(
        f"Splitting {audio_path.name} into {chunk_duration}s chunks..."
    )
    try:
        subprocess.run(
            cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
        )
    except subprocess.SubprocessError as exc:
        logger.warning(f"ffmpeg split failed ({exc}); returning unsplit file.")
        _rmtree_quiet(temp_dir)
        return [audio_path]

    # Collect chunk files in order.
    chunks = sorted(temp_dir.glob("part_*.mp3"))
    if not chunks:
        logger.warning(
            "ffmpeg produced no chunks; returning unsplit file."
        )
        _rmtree_quiet(temp_dir)
        return [audio_path]

    logger.info(f"Split into {len(chunks)} chunk(s).")
    return chunks


def cleanup_chunks(chunks: list[Path]) -> None:
    """Remove temporary chunk files and their parent directory if empty.

    Args:
        chunks: List of chunk file paths (as returned by ``split_audio``).
    """
    if not chunks:
        return

    temp_parent = None
    for chunk in chunks:
        try:
            chunk.unlink()
        except OSError:
            pass
        # The parent is the temp dir created by split_audio.
        if temp_parent is None and chunk.parent != chunk.parent.parent:
            temp_parent = chunk.parent

    if temp_parent is not None:
        _rmtree_quiet(temp_parent)


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


def _rmtree_quiet(path: Path) -> None:
    """Remove a directory tree, ignoring errors."""
    import shutil as _shutil

    try:
        _shutil.rmtree(path, ignore_errors=True)
    except Exception:  # noqa: BLE001
        pass
