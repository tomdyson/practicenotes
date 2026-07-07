"""Golden tests for the ChordPro parser and renderer."""

from songs import chordpro

WICHITA = """\
{title: Wichita Lineman}
{artist: Jimmy Webb}

[F]I am a lineman for the coun[C]ty
And I [G]drive the main [Am]road

{start_of_chorus}
And I [F]need you more than [C]want you
{end_of_chorus}

{comment: repeat to fade}
"""


def test_chord_alignment_simple():
    text = chordpro.render_text("[Am]Hello, [C]world")
    chord_line, lyric_line = text.splitlines()
    assert lyric_line == "Hello, world"
    assert chord_line == "Am     C"
    # Chords sit exactly above the syllables they belong to.
    assert chord_line.index("Am") == lyric_line.index("Hello")
    assert chord_line.index("C") == lyric_line.index("world")


def test_chord_alignment_mid_word():
    text = chordpro.render_text("Wich[Am]ita")
    chord_line, lyric_line = text.splitlines()
    assert lyric_line == "Wichita"
    assert chord_line == "    Am"


def test_crowded_chords_get_nudged_apart():
    text = chordpro.render_text("[Am7]I [Bm]a")
    chord_line, lyric_line = text.splitlines()
    assert chord_line == "Am7 Bm"
    assert lyric_line == "I a"


def test_line_without_chords():
    assert chordpro.render_text("Just some lyrics") == "Just some lyrics"


def test_directives_parse():
    blocks = chordpro.parse(WICHITA)
    kinds = [b.kind for b in blocks]
    assert kinds == ["title", "artist", "verse", "chorus", "comment"]
    assert blocks[0].text == "Wichita Lineman"
    assert blocks[1].text == "Jimmy Webb"
    assert blocks[4].text == "repeat to fade"


def test_short_form_directives_and_unknowns():
    source = "{t: Song}\n{c: Slowly}\n{capo: 2}\n{soc}\n[C]La\n{eoc}"
    blocks = chordpro.parse(source)
    kinds = [b.kind for b in blocks]
    # {capo} is unknown and silently ignored.
    assert kinds == ["title", "comment", "chorus"]


def test_render_html_structure():
    html = chordpro.render_html(WICHITA)
    assert '<div class="cp-title">Wichita Lineman</div>' in html
    assert 'class="cp-chord"' in html
    assert "cp-block cp-chorus" in html
    assert '<div class="cp-comment">repeat to fade</div>' in html


def test_render_html_escapes_user_content():
    html = chordpro.render_html("[C<b>]<script>alert(1)</script>")
    assert "<script>" not in html
    assert "&lt;script&gt;" in html
    assert "C&lt;b&gt;" in html


def test_html_chord_columns_match_text_rendering():
    """The HTML chord line must align identically to the plain-text one."""
    import re

    source = "[F]I am a lineman for the coun[C]ty"
    text_chords = chordpro.render_text(source).splitlines()[0]
    html = chordpro.render_html(source)
    chord_line_html = re.search(r'<div class="cp-chords">(.*?)</div>', html).group(1)
    stripped = re.sub(r"<[^>]+>", "", chord_line_html)
    assert stripped == text_chords
