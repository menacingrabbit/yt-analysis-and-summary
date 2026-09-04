"""Tests for resume / existing-file detection in src.yt.downloader."""

import os

from pathlib import Path

import src.yt.downloader as dl


def _touch(path: Path) -> None:
    path.write_bytes(b"")


def test_new_format_found_by_video_id(tmp_path):
    f = tmp_path / "20260717-clean-title-dQw4w9WgXcQ.mp3"
    _touch(f)
    assert dl._find_existing_audio(tmp_path, "dQw4w9WgXcQ", "clean-title") == f


def test_unrelated_video_not_matched_by_video_id(tmp_path):
    # A sibling video whose cleaned title is a suffix of another's.
    _touch(tmp_path / "20260717-the-interview.mp3")
    # Querying for "interview" must not return the sibling.
    assert dl._find_existing_audio(tmp_path, "OTHERID", "interview") is None


def test_legacy_file_matched_by_exact_title(tmp_path):
    f = tmp_path / "20260717-clean-title.mp3"
    _touch(f)
    assert dl._find_existing_audio(tmp_path, "", "clean-title") == f


def test_legacy_false_sibling_not_matched(tmp_path):
    # "the-interview" contains "interview"; the loose suffix glob would match it.
    _touch(tmp_path / "20260717-the-interview.mp3")
    assert dl._find_existing_audio(tmp_path, "", "interview") is None


def test_newest_returned_when_multiple_same_video(tmp_path):
    older = tmp_path / "20260101-clean-title-dQw4w9WgXcQ.mp3"
    newer = tmp_path / "20260202-clean-title-dQw4w9WgXcQ.mp3"
    _touch(older)
    _touch(newer)
    # Force distinct mtimes so the newest-file selection is deterministic.
    os.utime(older, (1_000_000, 1_000_000))
    os.utime(newer, (2_000_000, 2_000_000))
    assert dl._find_existing_audio(tmp_path, "dQw4w9WgXcQ", "clean-title") == newer


def test_written_name_is_found_on_resume(tmp_path):
    # The filename we write must be the one the resume check finds.
    slug = "20260717-clean-title"
    video_id = "dQw4w9WgXcQ"
    name = dl._audio_mp3_name(slug, video_id)
    _touch(tmp_path / name)
    found = dl._find_existing_audio(tmp_path, video_id, "clean-title")
    assert found == tmp_path / name
    assert found.suffix == ".mp3"


def test_mp3_name_includes_id_when_present_and_falls_back_without():
    assert dl._audio_mp3_name("20260717-clean-title", "") == "20260717-clean-title.mp3"
    assert dl._audio_mp3_name("20260717-clean-title", "abc123") == "20260717-clean-title-abc123.mp3"


def _make_fake_ydl(info, spy, tmp_path):
    """Fake yt_dlp.YoutubeDL: extract_info returns *info* and records downloads.

    prepare_filename yields a real temp file so download_audio's later
    original_path.unlink() succeeds without ffmpeg.
    """

    class _FakeYDL:
        def __init__(self, opts=None):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def extract_info(self, url, download=False):
            if download:
                spy["downloaded"] = True
            return info

        def prepare_filename(self, info):
            p = tmp_path / "downloaded-temp.webm"
            p.write_bytes(b"")
            return str(p)

    return _FakeYDL()


def test_download_audio_resumes_when_file_exists_empty_id(tmp_path, mocker):
    # YouTube returns no id -> written file keeps the slugify date prefix.
    info = {"title": "Clean Title", "id": ""}
    spy = {"downloaded": False}
    mocker.patch(
        "src.yt.downloader.YoutubeDL",
        return_value=_make_fake_ydl(info, spy, tmp_path),
    )

    # Simulate a prior run having written the resume file (date prefix from slugify).
    existing = tmp_path / dl._audio_mp3_name(dl.slugify("Clean Title"), "")
    existing.write_bytes(b"")

    result = dl.download_audio("https://youtu.be/abc", tmp_path)

    assert result == existing
    assert spy["downloaded"] is False  # resume skipped the actual download


def test_download_audio_downloads_when_file_absent_empty_id(tmp_path, mocker):
    info = {"title": "Clean Title", "id": ""}
    spy = {"downloaded": False}
    mocker.patch(
        "src.yt.downloader.YoutubeDL",
        return_value=_make_fake_ydl(info, spy, tmp_path),
    )
    mocker.patch("src.yt.downloader._run_ffmpeg")  # no ffmpeg in test env

    result = dl.download_audio("https://youtu.be/abc", tmp_path)

    expected = tmp_path / dl._audio_mp3_name(dl.slugify("Clean Title"), "")
    assert result == expected
    assert spy["downloaded"] is True  # no existing file -> real download attempted
