"""Tests for src.summarisation.summariser — template rendering on save."""

from src.summarisation.summariser import summarise_and_save
from src.summarisation.template import UNTITLED_VIDEO, render_summary


def test_written_summary_uses_canonical_template(tmp_path, mocker):
    raw = "Here is a summary.\n\n### Main Ideas\n\n- one\n- two\n\n### Key Takeaway\nTwo.\n"
    mocker.patch("src.summarisation.summariser.summarise", return_value=raw)

    path = summarise_and_save("transcript", tmp_path, "20260101-video-id", title="My Video")

    assert path == tmp_path / "20260101-video-id_summary.txt"
    assert path.read_text(encoding="utf-8") == render_summary("My Video", raw)


def test_empty_title_is_rendered_as_untitled(tmp_path, mocker):
    mocker.patch("src.summarisation.summariser.summarise", return_value="- one")

    path = summarise_and_save("transcript", tmp_path, "base", title="")

    assert path.read_text(encoding="utf-8").startswith(f"# {UNTITLED_VIDEO}\n")


def test_empty_model_response_still_writes_a_file(tmp_path, mocker):
    mocker.patch("src.summarisation.summariser.summarise", return_value="")

    path = summarise_and_save("transcript", tmp_path, "base", title="Title")

    content = path.read_text(encoding="utf-8")
    assert content.startswith("# Title\n")
    assert "## Key Points" in content
    assert "## Key Takeaway" in content
