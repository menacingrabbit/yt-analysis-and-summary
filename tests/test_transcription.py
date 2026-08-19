"""Tests for src.transcription.client — especially transcribe_split."""

from pathlib import Path

import pytest

from src.transcription.client import transcribe_split


class TestTranscribeSplit:
    """Tests for the transcribe_split function."""

    def test_transcribe_split_multiple_chunks(self, tmp_path):
        """Splitting should transcribe each chunk and concatenate results."""
        audio = tmp_path / "long.mp3"
        audio.write_bytes(b"")

        chunk1 = tmp_path / "part_000.mp3"
        chunk2 = tmp_path / "part_001.mp3"
        chunk3 = tmp_path / "part_002.mp3"
        chunk1.write_bytes(b"")
        chunk2.write_bytes(b"")
        chunk3.write_bytes(b"")

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.audio.splitter.split_audio",
                lambda path, chunk_duration=590: [chunk1, chunk2, chunk3],
            )
            mp.setattr("src.audio.splitter.cleanup_chunks", lambda chunks: None)
            mp.setattr(
                "src.transcription.client.transcribe",
                lambda path: {
                    chunk1: "First part text",
                    chunk2: "Second part text",
                    chunk3: "Third part text",
                }[path],
            )

            result = transcribe_split(audio, chunk_duration=590)

        assert "--- Part 1 ---" in result
        assert "First part text" in result
        assert "--- Part 2 ---" in result
        assert "Second part text" in result
        assert "--- Part 3 ---" in result
        assert "Third part text" in result

    def test_transcribe_split_single_chunk_calls_transcribe(self, tmp_path):
        """When the file is short enough, transcribe_split calls transcribe directly."""
        audio = tmp_path / "short.mp3"
        audio.write_bytes(b"")

        called_with = []

        def fake_split(path, chunk_duration=590):
            return [path]  # same file, no split needed

        def fake_transcribe(path):
            called_with.append(path)
            return "Full transcript"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.audio.splitter.split_audio", fake_split)
            cleanup_called = []
            mp.setattr(
                "src.audio.splitter.cleanup_chunks",
                lambda chunks: cleanup_called.append(True),
            )
            mp.setattr("src.transcription.client.transcribe", fake_transcribe)

            result = transcribe_split(audio, chunk_duration=590)

        assert result == "Full transcript"
        assert called_with == [audio]
        assert cleanup_called == [], "cleanup_chunks should not be called for single chunk"

    def test_transcribe_split_preserves_order(self, tmp_path):
        """Parts must appear in the correct order in the combined transcript."""
        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        chunks = [tmp_path / f"part_{i:03d}.mp3" for i in range(3)]
        for c in chunks:
            c.write_bytes(b"")

        def fake_transcribe(path):
            idx = chunks.index(path)
            return f"part-{idx + 1}"

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.audio.splitter.split_audio",
                lambda path, chunk_duration=590: chunks,
            )
            mp.setattr("src.audio.splitter.cleanup_chunks", lambda chunks: None)
            mp.setattr("src.transcription.client.transcribe", fake_transcribe)

            result = transcribe_split(audio)

        assert result.index("part-1") < result.index("part-2") < result.index("part-3")

    def test_transcribe_split_handles_empty_transcript(self, tmp_path):
        """Empty transcripts from a chunk should not break the combination."""
        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        chunks = [tmp_path / "part_000.mp3", tmp_path / "part_001.mp3"]
        for c in chunks:
            c.write_bytes(b"")

        def fake_transcribe(path):
            return "Some text" if path == chunks[0] else ""

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.audio.splitter.split_audio",
                lambda path, chunk_duration=590: chunks,
            )
            mp.setattr("src.audio.splitter.cleanup_chunks", lambda chunks: None)
            mp.setattr("src.transcription.client.transcribe", fake_transcribe)

            result = transcribe_split(audio)

        assert "Some text" in result
        # Empty part should not produce a "--- Part 2 ---" section
        assert "--- Part 2 ---" not in result

    def test_transcribe_split_default_chunk_duration(self, tmp_path):
        """Default chunk duration should be 590 seconds."""
        from src.audio.splitter import _DEFAULT_CHUNK_DURATION

        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        captured = {}

        def fake_split(path, chunk_duration=590):
            captured["chunk_duration"] = chunk_duration
            return [path]

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("src.audio.splitter.split_audio", fake_split)
            mp.setattr("src.audio.splitter.cleanup_chunks", lambda chunks: None)
            mp.setattr("src.transcription.client.transcribe", lambda path: "text")

            transcribe_split(audio)

        assert captured["chunk_duration"] == _DEFAULT_CHUNK_DURATION
        assert captured["chunk_duration"] == 590

    def test_transcribe_split_cleans_up_chunks(self, tmp_path):
        """cleanup_chunks must be called after transcription when chunks exist."""
        audio = tmp_path / "video.mp3"
        audio.write_bytes(b"")

        chunks = [tmp_path / f"part_{i:03d}.mp3" for i in range(2)]
        for c in chunks:
            c.write_bytes(b"")

        cleanup_called = []

        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(
                "src.audio.splitter.split_audio",
                lambda path, chunk_duration=590: chunks,
            )
            mp.setattr(
                "src.audio.splitter.cleanup_chunks",
                lambda cs: cleanup_called.append(list(cs)),
            )
            mp.setattr(
                "src.transcription.client.transcribe",
                lambda path: "text",
            )

            transcribe_split(audio)

        assert len(cleanup_called) == 1
        assert cleanup_called[0] == chunks
