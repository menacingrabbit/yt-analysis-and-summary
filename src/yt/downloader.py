"""YouTube audio downloader and converter.

Provides ``download_audio`` which uses ``yt_dlp`` to fetch the best audio
stream, converts it to MP3 via ffmpeg (if available), and reports progress
through ``tqdm``.
"""

import shutil
import subprocess
from pathlib import Path
from typing import Any

from yt_dlp import YoutubeDL
from tqdm import tqdm

from .utils import slugify
from ..utils.logging import logger

def _progress_hook(d: dict) -> None:
    """Hook for yt-dlp to forward progress to tqdm.

    yt-dlp passes dictionaries with a ``status`` key. We handle ``downloading``
    and update the global tqdm bar.
    """
    if d["status"] == "downloading":
        total = d.get("total_bytes") or d.get("total_bytes_estimate")
        downloaded = d.get("downloaded_bytes")
        if not hasattr(_progress_hook, "bar"):
            # Initialise tqdm bar on first call
            _progress_hook.bar = tqdm(total=total, unit="B", unit_scale=True, desc="Downloading")
        bar = _progress_hook.bar
        bar.total = total or bar.total
        bar.update(downloaded - bar.n)
    elif d["status"] == "finished":
        # Ensure bar completes
        if hasattr(_progress_hook, "bar"):
            _progress_hook.bar.close()
            # Print a newline to avoid overlapping with the next log message                                                                                                               
            print()  
            logger.info("Download finished, now converting (if ffmpeg is available)…")

def _run_ffmpeg(input_path: Path, output_path: Path) -> None:
    """Run ffmpeg to convert *input_path* to MP3 *output_path*.

    If ffmpeg is not installed or execution fails, the function copies the
    original file to the destination (preserving the original format) and logs a
    warning.
    """
    ffmpeg_exe = shutil.which("ffmpeg")
    if not ffmpeg_exe:
        logger.warning("ffmpeg not found – copying original file to destination without conversion.")
        output_path.write_bytes(input_path.read_bytes())
        return

    ffmpeg_cmd = [
        ffmpeg_exe,
        "-y",  # overwrite output if exists
        "-i",
        str(input_path),
        "-vn",
        "-acodec",
        "mp3",
        str(output_path),
    ]
    logger.info("Starting ffmpeg conversion…")
    try:
        subprocess.run(ffmpeg_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except Exception as exc:
        # Any error (including FileNotFoundError) falls back to copying.
        logger.warning(f"ffmpeg conversion failed ({exc}); copying original file instead.")
        output_path.write_bytes(input_path.read_bytes())
        return

def download_audio(url: str, out_dir: Path) -> Path:
    """Download the best audio from *url* into *out_dir* and return MP3 path.

    The function creates ``out_dir`` if it does not exist, generates a safe
    filename using :func:`slugify`, and runs ``ffmpeg`` to convert the downloaded
    file to MP3 when possible.
    """
    out_dir.mkdir(parents=True, exist_ok=True)

    # First extract info to get the title and generate our slug
    with YoutubeDL({"quiet": True, "no_warnings": True}) as ydl:
        info = ydl.extract_info(url, download=False)
        title = info.get("title", "audio")
        slug = slugify(title)

    # Use our slug as the base filename for yt-dlp
    temp_template = out_dir / f"{slug}.%(ext)s"
    ydl_opts: dict[str, Any] = {
        "format": "bestaudio/best",
        "outtmpl": str(temp_template),
        "progress_hooks": [_progress_hook],
        "quiet": True,
        "no_warnings": True,
    }
    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        original_path = Path(ydl.prepare_filename(info))

    title = info.get("title", "audio")
    slug = slugify(title)
    mp3_path = out_dir / f"{slug}.mp3"

    # Convert to MP3 using ffmpeg (or copy if unavailable/fails)
    _run_ffmpeg(original_path, mp3_path)

    # Remove the original download if it is different from the final output.
    try:
        if original_path.resolve() != mp3_path.resolve():
            original_path.unlink()
    except Exception:
        pass

    return mp3_path
