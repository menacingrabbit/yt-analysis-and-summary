"""Tests for the canonical summary template (src.summarisation.template)."""

import pytest

from src.summarisation.template import (
    KEY_POINTS_HEADING,
    KEY_TAKEAWAY_HEADING,
    NO_TAKEAWAY_TEXT,
    UNTITLED_VIDEO,
    normalise_summary,
    render_summary,
)


def _section_headers(rendered: str) -> list[str]:
    return [line for line in rendered.splitlines() if line.startswith("## ")]


def _assert_canonical(rendered: str) -> None:
    """Assert the rendered document has the canonical skeleton."""
    assert rendered.startswith("# ")
    assert rendered.endswith("\n") and not rendered.endswith("\n\n")
    assert _section_headers(rendered) == [KEY_POINTS_HEADING, KEY_TAKEAWAY_HEADING]


class TestNormalise:
    def test_preamble_and_atx_headings_are_removed(self):
        raw = (
            "Here is a summary of the transcript in bullet points, followed by a "
            "one-sentence key takeaway.\n\n"
            "### Main Ideas, Arguments, and Conclusions\n\n"
            "- **Policy:** YouTube's new policy\n"
            "- **Impact:** Creators are affected\n\n"
            "### Key Takeaway\nThe policy changes how creators monetise.\n"
        )
        points, takeaway = normalise_summary(raw)
        assert points == [
            "- **Policy:** YouTube's new policy",
            "- **Impact:** Creators are affected",
        ]
        assert takeaway == "The policy changes how creators monetise."

    def test_bold_only_headings(self):
        raw = (
            "Here is a bullet point summary of the transcript.\n\n"
            "**Main Ideas, Arguments, and Conclusions**\n\n"
            "- 60% of German households rent\n\n"
            "**Key Takeaway**\nStocks and ETFs beat the alternatives.\n"
        )
        points, takeaway = normalise_summary(raw)
        assert points == ["- 60% of German households rent"]
        assert takeaway == "Stocks and ETFs beat the alternatives."

    def test_missing_takeaway_falls_back_to_last_bullet(self):
        raw = (
            "### Bullet Point Summary\n\n"
            "- **Initial observation**: The speaker predicted a disaster\n"
            "- **Outcome**: Fandom grew rapidly\n"
        )
        points, takeaway = normalise_summary(raw)
        assert len(points) == 2
        # The bold label is dropped from the takeaway, not kept as a prefix.
        assert takeaway == "Fandom grew rapidly"

    def test_bare_bullets_without_headers(self):
        raw = (
            "- Adobe added a depth-range masking feature\n"
            "- It uses a depth map to select areas\n"
        )
        points, takeaway = normalise_summary(raw)
        assert points == [
            "- Adobe added a depth-range masking feature",
            "- It uses a depth map to select areas",
        ]
        # Last bullet is the only plausible takeaway source.
        assert takeaway == "It uses a depth map to select areas"

    def test_numbered_and_nested_lists_become_dash_bullets(self):
        raw = (
            "### Summary of Key Points\n\n"
            "1. First major point\n"
            "2. Second major point\n"
            "   1. Nested detail\n"
            "   2) Other nested detail\n\n"
            "### Key Takeaway\nAll of it matters.\n"
        )
        points, _ = normalise_summary(raw)
        # Indentation is preserved as it appeared in the source text.
        assert points == [
            "- First major point",
            "- Second major point",
            "   - Nested detail",
            "   - Other nested detail",
        ]

    def test_outer_fenced_block_is_unwrapped(self):
        raw = "```markdown\n## Key Points\n\n- one\n\n## Key Takeaway\nTwo.\n```"
        points, takeaway = normalise_summary(raw)
        assert points == ["- one"]
        assert takeaway == "Two."

    def test_empty_and_whitespace_input(self):
        assert normalise_summary("") == ([], "")
        assert normalise_summary("   \n\n\t\n") == ([], "")

    def test_truncated_response_drops_fences_and_dangling_marker(self):
        raw = "```markdown\n## Key Points\n\n- a complete point\n- another point\n-\n"
        points, _ = normalise_summary(raw)
        assert points == ["- a complete point", "- another point"]

    def test_takeaway_header_with_inline_body(self):
        raw = "## Key Points\n\n- point one\n\n### Key Takeaway: Soccer is booming.\n"
        points, takeaway = normalise_summary(raw)
        assert points == ["- point one"]
        assert takeaway == "Soccer is booming."

    def test_empty_takeaway_section_falls_back(self):
        raw = "### Summary of Main Ideas\n\n- Only bullet\n\n### Key Takeaway\n\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "Only bullet"

    def test_trailing_prose_after_last_bullet_is_takeaway(self):
        raw = "### Key Points\n\n- point one\n- point two\n\nOverall, the tool saves time.\n"
        points, takeaway = normalise_summary(raw)
        assert points == ["- point one", "- point two"]
        assert takeaway == "Overall, the tool saves time."

    def test_prose_only_response_becomes_bullets(self):
        points, takeaway = normalise_summary("First idea.\nSecond idea.")
        assert points == ["- First idea.", "- Second idea."]
        assert takeaway == "First idea. Second idea."

    def test_takeaway_stops_at_an_appended_section(self):
        """Regression: extra sections after the takeaway must not leak into it."""
        raw = (
            "## Key Points\n\n"
            "- a\n\n"
            "## Key Takeaway\n"
            "The main point.\n"
            "## Additional Context\n"
            "- note\n"
        )
        _, takeaway = normalise_summary(raw)
        assert takeaway == "The main point."

    def test_takeaway_stops_at_an_appended_bold_section(self):
        raw = "## Key Takeaway\nThe main point.\n\n**Sources**\n- note\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "The main point."

    def test_takeaway_stops_before_appended_bullets_section(self):
        raw = "## Key Takeaway\nMain sentence.\n\n## Further Reading\n- one\n- two\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "Main sentence."

    def test_takeaway_wrapped_in_a_bullet_loses_the_marker(self):
        raw = "## Key Takeaway\n- The main point.\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "The main point."

    def test_duplicate_empty_takeaway_heading_is_skipped(self):
        raw = "## Key Points\n- a\n## Key Takeaway\n## Key Takeaway\nReal sentence.\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "Real sentence."

    def test_fully_bold_takeaway_bullet_keeps_its_text(self):
        """Regression: emphasis markers are stripped, not the whole phrase."""
        _, takeaway = normalise_summary("## Key Takeaway\n- **The main point.**\n")
        assert takeaway == "The main point."

    def test_bold_subject_keeps_its_words(self):
        raw = "## Key Takeaway\n**The policy** changes how creators monetise.\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "The policy changes how creators monetise."

    def test_bold_label_is_removed(self):
        raw = "## Key Takeaway\n**Key takeaway:** The policy matters.\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "The policy matters."

    def test_fully_bold_sentence_is_not_a_heading(self):
        raw = "## Key Takeaway\n**Takeaway culture is changing.**\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "Takeaway culture is changing."

    def test_prose_starting_with_takeaway_keeps_its_words(self):
        raw = "## Key Takeaway\nTakeaway culture is changing.\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "Takeaway culture is changing."

    def test_prose_starting_with_in_summary_keeps_its_words(self):
        raw = "## Key Takeaway\nIn summary, the tool saves time.\n"
        _, takeaway = normalise_summary(raw)
        assert takeaway == "In summary, the tool saves time."

    def test_labelled_takeaway_prefix_is_removed(self):
        for raw in (
            "## Key Takeaway\nKey takeaway: The tool saves time.\n",
            "## Key Takeaway\nTakeaway - The tool saves time.\n",
        ):
            _, takeaway = normalise_summary(raw)
            assert takeaway == "The tool saves time."

    def test_heading_after_first_bullet_is_demoted(self):
        raw = (
            "## Key Points\n\n"
            "- first\n"
            "### Sub-heading\n"
            "- second\n\n"
            "## Key Takeaway\nDone.\n"
        )
        points, _ = normalise_summary(raw)
        assert points == ["- first", "**Sub-heading**", "- second"]


class TestRender:
    def test_canonical_document(self):
        raw = "### Key Points\n\n- one\n- two\n\n### Key Takeaway\nTwo matters.\n"
        rendered = render_summary("A Great Video", raw)
        assert rendered == (
            "# A Great Video\n"
            "\n"
            "## Key Points\n"
            "\n"
            "- one\n"
            "- two\n"
            "\n"
            "## Key Takeaway\n"
            "\n"
            "Two matters.\n"
        )
        _assert_canonical(rendered)

    @pytest.mark.parametrize("title", ["", "   ", "\n\n"])
    def test_empty_title_falls_back(self, title):
        assert render_summary(title, "- x").startswith(f"# {UNTITLED_VIDEO}\n")

    def test_title_with_newlines_and_leading_hashes_is_sanitised(self):
        rendered = render_summary("# A\nnew *line*", "- x")
        assert rendered.splitlines()[0] == "# A new *line*"
        _assert_canonical(rendered)

    def test_empty_response_uses_placeholders(self):
        rendered = render_summary("Title", "")
        assert NO_TAKEAWAY_TEXT in rendered
        assert "- No summary was generated." in rendered
        _assert_canonical(rendered)

    def test_rendering_is_idempotent(self):
        raw_samples = [
            "Here is a summary.\n\n### Main Ideas\n\n- a\n- b\n\n### Key Takeaway\nC.\n",
            "**Main Ideas**\n\n- a\n\n**Key Takeaway**\nB.\n",
            "- only bullets\n- no takeaway",
            "## Key Points\n\n1. numbered\n   - nested\n\n## Key Takeaway\nInline.\n",
        ]
        for raw in raw_samples:
            first = render_summary("Title", raw)
            assert normalise_summary(first) == normalise_summary(raw)
            assert render_summary("Title", first) == first
