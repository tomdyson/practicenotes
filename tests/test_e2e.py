"""End-to-end browser tests (headless Chromium via Playwright).

Excluded from the default pytest run; execute with:  uv run pytest -m e2e

Each test drives the real dev server (pytest-django live_server) through a
real browser: signup with email-code verification, ChordPro rendering,
uploads, audio playback speed, drag reordering, and (after M6) public
share links.
"""

import io
import math
import os
import re
import struct
import wave

import pytest
from django.core import mail

pytest.importorskip("playwright.sync_api")
from playwright.sync_api import expect, sync_playwright  # noqa: E402

pytestmark = [pytest.mark.e2e, pytest.mark.django_db]


@pytest.fixture(scope="session")
def browser():
    # PLAYWRIGHT_CHROMIUM_EXECUTABLE lets environments with a pre-installed
    # Chromium (e.g. sandboxes) skip `playwright install`.
    executable = os.environ.get("PLAYWRIGHT_CHROMIUM_EXECUTABLE") or None
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path=executable)
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    yield page
    context.close()


def make_wav(seconds: float = 1.0, freq: float = 440.0) -> bytes:
    """A real, playable mono 16-bit WAV so <audio> genuinely decodes."""
    rate = 22050
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(rate)
        for i in range(int(rate * seconds)):
            sample = int(12000 * math.sin(2 * math.pi * freq * i / rate))
            w.writeframes(struct.pack("<h", sample))
    return buffer.getvalue()


FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 256
FAKE_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d4948445200000001000000010806000000"
    "1f15c4890000000d49444154789c626001000000ffff03000006000557"
    "bfabd40000000049454e44ae426082"
)


def signup(page, live_server, username, email, password):
    page.goto(live_server.url + "/accounts/signup/")
    page.fill("input[name=username]", username)
    page.fill("input[name=email]", email)
    page.fill("input[name=password1]", password)
    page.click("main form button[type=submit]:not([form])")
    # Email verification by code (printed to the in-process outbox).
    page.wait_for_url("**/confirm-email/**")
    code = re.search(r"^([A-Z0-9]{3,8}(?:-[A-Z0-9]{3,8})?)$", mail.outbox[-1].body, re.MULTILINE)
    assert code, "no verification code in outbox"
    page.fill("input[name=code]", code.group(1))
    page.click("main form button[type=submit]:not([form])")
    page.wait_for_url(live_server.url + "/")


def create_song(page, live_server, username, title):
    page.goto(f"{live_server.url}/{username}/songs/new")
    page.fill("input[name=title]", title)
    page.click("main form button[type=submit]:not([form])")
    page.wait_for_url("**/" + "*")


def test_full_song_workflow(page, live_server, tmp_path):
    signup(page, live_server, "erin", "erin@example.com", "correct-horse-e2e-9")

    # Create a song.
    create_song(page, live_server, "erin", "Wichita Lineman")
    expect(page.locator("h1")).to_contain_text("Wichita Lineman")

    # Paste ChordPro and verify chord/lyric alignment in the render.
    page.click("text=Add text")
    page.fill("input[name=title]", "Chords")
    page.select_option("select[name=format]", "chordpro")
    page.fill(
        "textarea[name=body]", "{title: Wichita Lineman}\n[F]I am a lineman for the coun[C]ty"
    )
    page.click("main form button[type=submit]:not([form])")
    chord_line = page.locator(".cp-chords").first
    lyric_line = page.locator(".cp-lyrics").first
    expect(chord_line).to_be_visible()
    # Chords render in mono with [C] above "ty" of "county": the chord line's
    # C must sit at the same column as lyric offset of "ty".
    chords_text = chord_line.inner_text()
    lyrics_text = lyric_line.inner_text()
    assert chords_text.startswith("F")
    assert chords_text.index("C") == lyrics_text.index("ty")
    # Both lines use the same monospace font.
    fonts = page.evaluate(
        """() => {
            const c = document.querySelector('.cp-chords');
            const l = document.querySelector('.cp-lyrics');
            return [getComputedStyle(c).fontFamily, getComputedStyle(l).fontFamily];
        }"""
    )
    assert fonts[0] == fonts[1]
    assert "JetBrains Mono" in fonts[0]

    # Upload an audio file and an image together.
    wav_path = tmp_path / "rehearsal.wav"
    wav_path.write_bytes(make_wav())
    png_path = tmp_path / "chart.png"
    png_path.write_bytes(FAKE_PNG)
    page.set_input_files("input[type=file]", [str(wav_path), str(png_path)])
    page.wait_for_url("**/wichita-lineman/")
    expect(page.locator("audio")).to_have_count(1)
    expect(page.locator("article img")).to_have_count(1)

    # Play the audio at 0.75x and confirm it is actually progressing.
    page.click("button:has-text('0.75×')")
    state = page.evaluate(
        """async () => {
            const audio = document.querySelector('audio');
            await audio.play();
            await new Promise(r => setTimeout(r, 400));
            return {rate: audio.playbackRate, time: audio.currentTime, paused: audio.paused};
        }"""
    )
    assert state["rate"] == 0.75
    assert state["paused"] is False
    assert state["time"] > 0

    # The image actually loaded (not a broken 404).
    assert page.evaluate(
        "() => { const i = document.querySelector('article img');"
        " return i.complete && i.naturalWidth > 0; }"
    )

    # Reorder: drag the first item (chords) to the bottom.
    handles = page.locator(".js-drag-handle")
    source_box = handles.nth(0).bounding_box()
    target_box = handles.nth(2).bounding_box()
    page.mouse.move(source_box["x"] + 5, source_box["y"] + 5)
    page.mouse.down()
    # A small initial move starts the drag before travelling to the target.
    page.mouse.move(source_box["x"] + 5, source_box["y"] + 25, steps=4)
    page.mouse.move(target_box["x"] + 5, target_box["y"] + 60, steps=25)
    page.wait_for_timeout(150)
    page.mouse.up()
    page.wait_for_timeout(500)  # allow the hx-post to land
    page.reload()
    first_card_text = page.locator(".js-sortable article").first.inner_text()
    assert "Chords" not in first_card_text, "chords item should no longer be first"


def test_private_song_hidden_from_stranger(page, live_server, browser):
    signup(page, live_server, "priva", "priva@example.com", "correct-horse-e2e-9")
    create_song(page, live_server, "priva", "Secret Song")
    song_url = page.url

    # A logged-out visitor gets a 404.
    context = browser.new_context()
    anon = context.new_page()
    response = anon.goto(song_url)
    assert response.status == 404
    context.close()
