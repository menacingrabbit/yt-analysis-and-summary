"""Shared fixtures for the test suite."""

import pytest


@pytest.fixture
def audio_file(tmp_path):
    """Return a factory that creates a dummy (empty) audio file."""

    def _make(name: str = "audio.mp3"):
        path = tmp_path / name
        path.write_bytes(b"")
        return path

    return _make


@pytest.fixture
def chunk_files(tmp_path):
    """Return a factory that creates *count* chunk files in a temp dir.

    Returns ``(temp_dir, [chunk_paths])``. The temp dir uses the same
    ``yt-split-`` prefix as the real splitter so ``cleanup_chunks`` treats it
    as a splitter-owned directory.
    """

    def _make(count: int, prefix: str = "yt-split-test"):
        temp_dir = tmp_path / prefix
        temp_dir.mkdir(exist_ok=True)
        paths = [temp_dir / f"part_{i:03d}.mp3" for i in range(count)]
        for path in paths:
            path.write_bytes(b"")
        return temp_dir, paths

    return _make


@pytest.fixture
def transcription_ctx(mocker):
    """Patch ``transcribe_split``'s dependencies; expose ``split``/``transcribe``.

    Attributes:
        split_audio: the patched ``src.transcription.client.split_audio`` mock.
        cleanup_chunks: the patched ``cleanup_chunks`` mock (so call counts and
            arguments are assertions directly on the mock).
        transcribe: the patched leaf ``transcribe`` mock.
    """
    ctx = mocker.MagicMock()
    ctx.split_audio = mocker.patch("src.transcription.client.split_audio")
    ctx.cleanup_chunks = mocker.patch("src.transcription.client.cleanup_chunks")
    ctx.transcribe = mocker.patch("src.transcription.client.transcribe")
    return ctx
