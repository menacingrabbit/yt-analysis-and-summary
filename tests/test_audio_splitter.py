"""Tests for src.audio.splitter module."""

from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

from src.audio.splitter import split_audio, cleanup_chunks, _get_audio_duration


class TestSplitAudio:
    """Tests for the split_audio function."""

    def test_short_file_returns_single(self, tmp_path):
        """A file shorter than the chunk duration should not be split."""
        audio = tmp_path / "short.mp3"
        audio.write_bytes(b"")

        with patch(
            "src.audio.splitter._get_audio_duration", return_value=30.0
        ):
            chunks = split_audio(audio, chunk_duration=590)

        assert len(chunks) == 1
        assert chunks[0] == audio

    def test_long_file_splits_with_ffmpeg(self, tmp_path):
        """A long file should be split via ffmpeg into multiple chunks."""
        audio = tmp_path / "long.mp3"
        audio.write_bytes(b"")

        with patch(
            "src.audio.splitter._get_audio_duration", return_value=1500.0
        ), patch("src.audio.splitter.shutil.which") as mock_which, patch(
            "src.audio.splitter.subprocess.run"
        ) as mock_run, patch(
            "src.audio.splitter.tempfile.mkdtemp", return_value=str(tmp_path / "tmp")
        ):
            mock_which.return_value = "/usr/bin/ffmpeg"
            # Simulate ffmpeg creating 3 chunk files
            tmp_dir = tmp_path / "tmp"
            tmp_dir.mkdir(exist_ok=True)
            (tmp_dir / "part_000.mp3").write_bytes(b"")
            (tmp_dir / "part_001.mp3").write_bytes(b"")
            (tmp_dir / "part_002.mp3").write_bytes(b"")

            chunks = split_audio(audio, chunk_duration=590)

        assert len(chunks) == 3
        assert chunks[0].name == "part_000.mp3"
        assert chunks[1].name == "part_001.mp3"
        assert chunks[2].name == "part_002.mp3"
        # Verify ffmpeg was called with the right arguments
        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert "-f" in cmd
        assert "segment" in cmd
        assert str(590) in cmd

    def test_no_ffmpeg_fallback(self, tmp_path):
        """If ffmpeg is unavailable, return the original file unsplit."""
        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        with patch(
            "src.audio.splitter._get_audio_duration", return_value=1500.0
        ), patch("src.audio.splitter.shutil.which", return_value=None):
            chunks = split_audio(audio, chunk_duration=590)

        assert len(chunks) == 1
        assert chunks[0] == audio

    def test_ffmpeg_failure_fallback(self, tmp_path):
        """If ffmpeg fails, return the original file unsplit."""
        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        with patch(
            "src.audio.splitter._get_audio_duration", return_value=1500.0
        ), patch("src.audio.splitter.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
            "src.audio.splitter.subprocess.run",
            side_effect=__import__("subprocess").CalledProcessError(1, "ffmpeg"),
        ), patch(
            "src.audio.splitter.tempfile.mkdtemp", return_value=str(tmp_path / "tmp")
        ):
            chunks = split_audio(audio, chunk_duration=590)

        assert len(chunks) == 1
        assert chunks[0] == audio

    def test_no_duration_info_still_tries_split(self, tmp_path):
        """If duration can't be determined, still attempt the split."""
        audio = tmp_path / "unknown.mp3"
        audio.write_bytes(b"")

        with patch(
            "src.audio.splitter._get_audio_duration", return_value=None
        ), patch("src.audio.splitter.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
            "src.audio.splitter.subprocess.run"
        ) as mock_run, patch(
            "src.audio.splitter.tempfile.mkdtemp", return_value=str(tmp_path / "tmp")
        ):
            tmp_dir = tmp_path / "tmp"
            tmp_dir.mkdir(exist_ok=True)
            (tmp_dir / "part_000.mp3").write_bytes(b"")
            mock_run.return_value = MagicMock(returncode=0)

            chunks = split_audio(audio, chunk_duration=590)

        # Should have attempted to split via ffmpeg
        mock_run.assert_called_once()

    def test_chunks_are_ordered(self, tmp_path):
        """Returned chunk paths should be sorted (part_000, part_001, ...)."""
        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        with patch(
            "src.audio.splitter._get_audio_duration", return_value=1500.0
        ), patch("src.audio.splitter.shutil.which", return_value="/usr/bin/ffmpeg"), patch(
            "src.audio.splitter.subprocess.run"
        ), patch(
            "src.audio.splitter.tempfile.mkdtemp", return_value=str(tmp_path / "tmp")
        ):
            tmp_dir = tmp_path / "tmp"
            tmp_dir.mkdir(exist_ok=True)
            (tmp_dir / "part_002.mp3").write_bytes(b"")
            (tmp_dir / "part_000.mp3").write_bytes(b"")
            (tmp_dir / "part_001.mp3").write_bytes(b"")

            chunks = split_audio(audio, chunk_duration=590)

        assert len(chunks) == 3
        assert chunks[0].name == "part_000.mp3"
        assert chunks[1].name == "part_001.mp3"
        assert chunks[2].name == "part_002.mp3"


class TestCleanupChunks:
    """Tests for the cleanup_chunks function."""

    def test_removes_files_and_dir(self, tmp_path):
        """cleanup_chunks should remove chunk files and the parent temp dir."""
        chunk_dir = tmp_path / "tmp"
        chunk_dir.mkdir()
        f1 = chunk_dir / "part_000.mp3"
        f2 = chunk_dir / "part_001.mp3"
        f1.write_bytes(b"")
        f2.write_bytes(b"")

        cleanup_chunks([f1, f2])

        assert not f1.exists()
        assert not f2.exists()
        assert not chunk_dir.exists()

    def test_empty_list_is_noop(self):
        """cleanup_chunks with an empty list should not raise."""
        cleanup_chunks([])
        assert True  # no exception = pass

    def test_missing_file_silent(self, tmp_path):
        """cleanup_chunks should not raise if a file is already gone."""
        chunk_dir = tmp_path / "tmp"
        chunk_dir.mkdir()
        existing = chunk_dir / "part_000.mp3"
        existing.write_bytes(b"")
        already_gone = chunk_dir / "part_001.mp3"

        cleanup_chunks([existing, already_gone])

        assert not existing.exists()
        assert not chunk_dir.exists()


class TestGetAudioDuration:
    """Tests for the _get_audio_duration helper."""

    def test_returns_none_without_ffprobe(self):
        """Should return None when ffprobe is not installed."""
        with patch("src.audio.splitter.shutil.which", return_value=None):
            assert _get_audio_duration(Path("/fake/audio.mp3")) is None

    def test_returns_duration(self, tmp_path):
        """Should return the parsed duration from ffprobe output."""
        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"")

        with patch("src.audio.splitter.shutil.which", return_value="/usr/bin/ffprobe"), patch(
            "src.audio.splitter.subprocess.run"
        ) as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0, stdout="42.5\n", stderr=""
            )
            result = _get_audio_duration(audio)

        assert result == 42.5

    def test_returns_none_on_error(self, tmp_path):
        """Should return None if ffprobe fails."""
        import subprocess

        audio = tmp_path / "test.mp3"
        audio.write_bytes(b"")

        with patch("src.audio.splitter.shutil.which", return_value="/usr/bin/ffprobe"), patch(
            "src.audio.splitter.subprocess.run",
            side_effect=subprocess.SubprocessError("ffprobe failed"),
        ):
            result = _get_audio_duration(audio)

        assert result is None
