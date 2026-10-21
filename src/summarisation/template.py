"""Canonical summary template: normalisation and rendering.

The summarisation model is asked for a fixed structure, but models drift: they
add preambles ("Here is a summary…"), rename headings, or drop the takeaway
section entirely. This module turns whatever comes back into the canonical
document shape:

    # <video title>

    ## Key Points

    - <point>

    ## Key Takeaway

    <one sentence>

Normalisation is deterministic and dependency-free so it can be unit-tested
without network access.
"""

import re

KEY_POINTS_HEADING = "## Key Points"
KEY_TAKEAWAY_HEADING = "## Key Takeaway"
UNTITLED_VIDEO = "Untitled video"
NO_POINTS_TEXT = "- No summary was generated."
NO_TAKEAWAY_TEXT = "_No key takeaway was generated._"

# Markdown constructs we recognise in model output.
_ATX_RE = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$")
_BOLD_ONLY_RE = re.compile(r"^\s*\*\*(.+?)\*\*\s*:?\s*$")
_BULLET_RE = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_BARE_MARKER_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s*$")
_FENCE_RE = re.compile(r"^\s*```")
_OUTER_FENCE_RE = re.compile(r"^\s*```[^\n]*\n(.*)\n```\s*$", re.DOTALL)
_RULE_RE = re.compile(r"^\s*([-*_])\s*(\1\s*){2,}$")

# "Key Takeaway" / "Key takeaways" as a heading, with an optional inline body
# after a colon, e.g. "### Key Takeaway: Soccer is booming in the US."
_TAKEAWAY_HEADER_RE = re.compile(r"^(?:the\s+)?key\s+takeaways?\b\s*(:?)\s*", re.IGNORECASE)
# A *label* prefixing the takeaway sentence, e.g. "Key takeaway: ..." or
# "Takeaway: ...". Requires an unambiguous separator so that prose which merely
# starts with these words ("Takeaway culture is changing", "In summary, ...")
# keeps its opening words.
_TAKEAWAY_PREFIX_RE = re.compile(
    r"^(?:(?:the\s+)?key\s+takeaways?|takeaways?)\s*(?::|[-–—])\s*",
    re.IGNORECASE,
)
# A bold phrase followed by a colon is a label, e.g. "**Outcome**: ...", and is
# discarded along with its separator.
_LEADING_BOLD_COLON_RE = re.compile(r"^\*\*(.+?)\*\*\s*:\s*")
# A bold phrase *without* a colon is emphasis, not a label: "**The policy**
# changes ..." must keep its words, so only the markers are removed.
_LEADING_BOLD_RE = re.compile(r"^\*\*(.+?)\*\*")
# A bold segment that really is a discarded label ("**Key takeaway:**").
_LEADING_BOLD_LABEL_RE = re.compile(
    r"^\*\*((?:the\s+)?key\s+takeaways?|takeaways?)\s*:?\*\*\s*:?\s*", re.IGNORECASE
)
# Emphasis markers throughout a takeaway. The section is rendered as plain
# prose, so a stray leading marker in the model's text must not survive.
_EMPHASIS_MARKER_RE = re.compile(r"\*\*|__")


def _strip_emphasis(text: str) -> str:
    """Remove emphasis markers around a short heading-like string."""
    return text.strip().strip("*_`").strip()


def _header_text(line: str) -> str | None:
    """Return the heading text of *line*, or None if it is not a heading."""
    match = _ATX_RE.match(line)
    if match:
        return _strip_emphasis(match.group(2))
    match = _BOLD_ONLY_RE.match(line)
    if match:
        return _strip_emphasis(match.group(1))
    return None


def _takeaway_header(line: str) -> str | None:
    """If *line* is a takeaway heading, return its inline body (possibly "").

    Returns None when the line is not a takeaway heading. ATX, bold-only and
    plain-text headings are all accepted.
    """
    text = _header_text(line)
    if text is None:
        text = _strip_emphasis(line)
    match = _TAKEAWAY_HEADER_RE.match(text)
    if not match:
        return None
    rest = text[match.end() :]
    # Accept the heading only when nothing but an optional ":" body follows.
    if rest and not match.group(1):
        return None
    return rest.strip()


def _plain(line: str) -> str:
    """Return *line* as plain text, or "" for blanks and fence markers."""
    if not line.strip() or _FENCE_RE.match(line):
        return ""
    return _strip_emphasis(line)


def _clean_takeaway(text: str) -> str:
    """Collapse *text* into one clean takeaway line.

    Labels ("Key takeaway:", "**Takeaway:**") are removed, but a bold phrase
    that is part of the sentence keeps its words — only the markers go.
    """
    text = re.sub(r"\s+", " ", text).strip()
    text = _LEADING_BOLD_LABEL_RE.sub("", text)
    text = _TAKEAWAY_PREFIX_RE.sub("", text)
    text = _LEADING_BOLD_COLON_RE.sub("", text)
    text = _LEADING_BOLD_RE.sub(r"\1", text)
    text = _EMPHASIS_MARKER_RE.sub("", text)
    return text.strip().strip("\"'`“”‘’").strip()


def _build_points(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return ``(point_lines, trailing_prose)`` for the pre-takeaway *lines*.

    Content before the first bullet (preambles, renamed summary headings) is
    dropped; bullet markers are normalised to ``-``; headings after the first
    bullet are demoted to bold so the document keeps exactly two ``##`` lines.
    Non-bullet prose after the last bullet is returned separately as
    *trailing_prose*, since it is usually the takeaway paragraph.
    """
    points: list[str] = []
    trailing: list[str] = []
    seen_bullet = False

    for line in lines:
        if not line.strip() or _RULE_RE.match(line) or _FENCE_RE.match(line):
            continue
        if _BARE_MARKER_RE.match(line):
            continue  # dangling marker from a truncated response

        header = _header_text(line)
        if header is not None:
            if seen_bullet:
                points.append(f"**{header}**")
            continue  # before the first bullet: preamble / summary heading

        bullet = _BULLET_RE.match(line)
        if bullet:
            indent, _, content = bullet.groups()
            points.append(f"{indent}- {content.strip()}")
            seen_bullet = True
            trailing = []
            continue

        if not seen_bullet:
            continue  # preamble prose
        # After a bullet, prose is usually the takeaway paragraph; keep it
        # separate so it does not also become a bullet.
        trailing.append(line.strip())

    if not seen_bullet:
        # Prose-only response: every meaningful line becomes a bullet.
        prose = [
            line.strip()
            for line in lines
            if line.strip()
            and not _RULE_RE.match(line)
            and not _FENCE_RE.match(line)
            and not _BARE_MARKER_RE.match(line)
            and _header_text(line) is None
        ]
        points = [f"- {_strip_emphasis(line)}" for line in prose]
        trailing = prose

    return points, trailing


def _last_top_level_bullet(points: list[str]) -> str:
    """Return the text of the last top-level bullet in *points*."""
    for entry in reversed(points):
        match = _BULLET_RE.match(entry)
        if match and not match.group(1):
            return match.group(3)
    return ""


def normalise_summary(raw: str) -> tuple[list[str], str]:
    """Normalise model output into ``(point_lines, takeaway)``.

    ``point_lines`` are already-prefixed markdown bullets (sub-lines included).
    ``takeaway`` is a single line, or "" when none could be recovered.
    """
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    lines = [line.rstrip() for line in text.split("\n")]
    if not any(line.strip() for line in lines):
        return [], ""

    # A response wrapped in one fenced block: unwrap and normalise the inner text.
    stripped = "\n".join(lines).strip()
    fence_match = _OUTER_FENCE_RE.match(stripped)
    if fence_match:
        return normalise_summary(fence_match.group(1))

    # An odd number of fences means truncation inside a fence. Fences carry no
    # meaning for the template, so drop them all.
    if sum(1 for line in lines if _FENCE_RE.match(line)) % 2:
        lines = [line for line in lines if not _FENCE_RE.match(line)]

    split_index: int | None = None
    inline_takeaway = ""
    for i, line in enumerate(lines):
        inline = _takeaway_header(line)
        if inline is not None:
            split_index, inline_takeaway = i, inline
            break

    if split_index is None:
        body_lines: list[str] = lines
        takeaway_lines: list[str] | None = None
    else:
        body_lines = lines[:split_index]
        takeaway_lines = lines[split_index + 1 :]

    points, trailing = _build_points(body_lines)
    return points, _pick_takeaway(inline_takeaway, takeaway_lines, trailing, points)


def _is_section_heading(line: str) -> bool:
    """Return True if *line* starts a new section of the document.

    Inside the takeaway section a heading means "an extra section follows".
    A fully-bold line can be either a heading or a bolded takeaway sentence
    (``**Takeaway culture is changing.**``), so terminal punctuation is used to
    tell them apart: headings are noun phrases, sentences are terminated.
    """
    header = _header_text(line)
    if header is None:
        return False
    return header[-1:] not in ".!?"


def _pick_takeaway(
    inline: str,
    takeaway_lines: list[str] | None,
    trailing: list[str],
    points: list[str],
) -> str:
    """Choose the takeaway, falling back when the section is missing or empty."""
    if takeaway_lines is not None:
        parts = [inline] if inline else []
        for line in takeaway_lines:
            # The takeaway is the last section of the template, so any *other*
            # heading after it starts an extra section the model added
            # (sources, "Additional Context") that must not be folded into the
            # sentence. A repeated takeaway heading is not a new section — skip
            # it and keep reading.
            repeated = _takeaway_header(line)
            if repeated is not None:
                if repeated:
                    parts.append(repeated)
                continue
            if _is_section_heading(line):
                break
            if _BULLET_RE.match(line):
                # A takeaway written as a list item: keep its text, not "- ".
                parts.append(_BULLET_RE.match(line).group(3))
                continue
            plain = _plain(line)
            if plain:
                parts.append(plain)
        if parts:
            return _clean_takeaway(" ".join(parts))

    # No takeaway section (or an empty one): trailing prose after the last
    # bullet, then the last top-level bullet, then nothing.
    if trailing:
        return _clean_takeaway(" ".join(trailing))
    last = _last_top_level_bullet(points)
    if last:
        return _clean_takeaway(last)
    return ""


def is_empty_summary(raw: str) -> bool:
    """Return True if *raw* contains nothing usable for the template.

    A response can be non-blank yet carry no summary at all — headings with no
    body, only a code fence, only a preamble. Rendering it would emit the
    placeholder text, which would mask a failed summarisation.
    """
    return normalise_summary(raw) == ([], "")


def _clean_title(title: str) -> str:
    """Return *title* as a single-line H1-safe heading."""
    text = re.sub(r"[\x00-\x1f\x7f]+", " ", str(title or ""))
    text = re.sub(r"\s+", " ", text).strip()
    text = text.lstrip("#").strip()
    return text or UNTITLED_VIDEO


def render_summary(title: str, raw: str) -> str:
    """Render model output *raw* as the canonical summary document for *title*."""
    points, takeaway = normalise_summary(raw)
    point_block = "\n".join(points) if points else NO_POINTS_TEXT
    takeaway_block = takeaway or NO_TAKEAWAY_TEXT
    return (
        f"# {_clean_title(title)}\n\n"
        f"{KEY_POINTS_HEADING}\n\n"
        f"{point_block}\n\n"
        f"{KEY_TAKEAWAY_HEADING}\n\n"
        f"{takeaway_block}\n"
    )
