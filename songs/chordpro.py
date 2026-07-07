"""A small, tolerant ChordPro parser and HTML renderer.

Parses chord tokens like [Am7] and the common directives ({title}, {artist},
{comment}, {start_of_chorus}/{end_of_chorus} and their short forms), ignoring
directives it doesn't know. Chords stay structured (chord, position) so
transposition can be added later (backlog #10).

Rendering pairs a chord line with its lyric line, aligned by character
column — correct as long as the output is set in a monospace font.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import escape

CHORD_RE = re.compile(r"\[([^\[\]]+)\]")
DIRECTIVE_RE = re.compile(r"^\{\s*([a-zA-Z_]+)\s*(?::\s*(.*?)\s*)?\}\s*$")

# Canonical names for the directives we understand.
DIRECTIVE_ALIASES = {
    "t": "title",
    "title": "title",
    "st": "subtitle",
    "subtitle": "subtitle",
    "artist": "artist",
    "c": "comment",
    "ci": "comment",
    "comment": "comment",
    "comment_italic": "comment",
    "soc": "start_of_chorus",
    "start_of_chorus": "start_of_chorus",
    "eoc": "end_of_chorus",
    "end_of_chorus": "end_of_chorus",
}


@dataclass
class Segment:
    """A run of lyrics preceded by an optional chord."""

    chord: str | None
    text: str


@dataclass
class Line:
    segments: list[Segment] = field(default_factory=list)

    @property
    def has_chords(self) -> bool:
        return any(s.chord for s in self.segments)


@dataclass
class Block:
    """A group of lines: a verse, a chorus, or a one-line comment/heading."""

    kind: str  # "verse" | "chorus" | "comment" | "title" | "subtitle" | "artist"
    lines: list[Line] = field(default_factory=list)
    text: str = ""  # for comment/title/subtitle/artist blocks


def parse_line(raw: str) -> Line:
    segments: list[Segment] = []
    pos = 0
    chord: str | None = None
    for match in CHORD_RE.finditer(raw):
        text = raw[pos : match.start()]
        if text or chord is not None:
            segments.append(Segment(chord, text))
        chord = match.group(1).strip()
        pos = match.end()
    segments.append(Segment(chord, raw[pos:]))
    return Line(segments)


def parse(source: str) -> list[Block]:
    blocks: list[Block] = []
    current: Block | None = None
    in_chorus = False

    def close_current():
        nonlocal current
        if current is not None and current.lines:
            blocks.append(current)
        current = None

    for raw in source.splitlines():
        stripped = raw.strip()
        directive = DIRECTIVE_RE.match(stripped)
        if directive:
            name = DIRECTIVE_ALIASES.get(directive.group(1).lower())
            value = directive.group(2) or ""
            if name == "start_of_chorus":
                close_current()
                in_chorus = True
            elif name == "end_of_chorus":
                close_current()
                in_chorus = False
            elif name in ("title", "subtitle", "artist", "comment"):
                close_current()
                blocks.append(Block(kind=name, text=value))
            # Unknown directives are ignored.
            continue
        if not stripped:
            close_current()
            continue
        if current is None:
            current = Block(kind="chorus" if in_chorus else "verse")
        current.lines.append(parse_line(raw.rstrip()))
    close_current()
    return blocks


def _line_to_text(line: Line) -> tuple[str, list[tuple[int, str]]]:
    """Flatten a line to its lyric text plus (column, chord) placements."""
    lyric = ""
    chords: list[tuple[int, str]] = []
    for segment in line.segments:
        if segment.chord:
            chords.append((len(lyric), segment.chord))
        lyric += segment.text
    return lyric.rstrip(), chords


def _render_chord_line(chords: list[tuple[int, str]]) -> str:
    """Build the chord line, nudging chords right when they would collide."""
    out = ""
    for column, chord in chords:
        if len(out) > column:
            column = len(out) + 1 if out else len(out)
        out += " " * (column - len(out))
        out += chord
    return out


def _chord_line_html(chords: list[tuple[int, str]]) -> str:
    out = ""
    visible_len = 0
    for column, chord in chords:
        if visible_len > column:
            column = visible_len + 1 if visible_len else visible_len
        out += " " * (column - visible_len)
        visible_len = column
        out += f'<span class="cp-chord">{escape(chord)}</span>'
        visible_len += len(chord)
    return out


def render_html(source: str) -> str:
    """Render ChordPro source to HTML. Escapes all user content."""
    parts: list[str] = ['<div class="chordpro">']
    for block in parse(source):
        if block.kind == "title":
            parts.append(f'<div class="cp-title">{escape(block.text)}</div>')
        elif block.kind in ("subtitle", "artist"):
            parts.append(f'<div class="cp-subtitle">{escape(block.text)}</div>')
        elif block.kind == "comment":
            parts.append(f'<div class="cp-comment">{escape(block.text)}</div>')
        else:
            css = "cp-block cp-chorus" if block.kind == "chorus" else "cp-block"
            lines_html: list[str] = []
            for line in block.lines:
                lyric, chords = _line_to_text(line)
                if chords:
                    lines_html.append(f'<div class="cp-chords">{_chord_line_html(chords)}</div>')
                if lyric or not chords:
                    lines_html.append(f'<div class="cp-lyrics">{escape(lyric) or "&nbsp;"}</div>')
            parts.append(f'<div class="{css}">{"".join(lines_html)}</div>')
    parts.append("</div>")
    return "".join(parts)


def render_text(source: str) -> str:
    """Plain-text rendering (chord line above lyric line); used in tests."""
    out: list[str] = []
    for block in parse(source):
        if block.kind in ("title", "subtitle", "artist", "comment"):
            out.append(block.text)
            continue
        for line in block.lines:
            lyric, chords = _line_to_text(line)
            if chords:
                out.append(_render_chord_line(chords))
            if lyric or not chords:
                out.append(lyric)
        out.append("")
    while out and not out[-1]:
        out.pop()
    return "\n".join(out)
