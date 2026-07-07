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
    # Surface browser-side problems in pytest's captured stdout.
    page.on("console", lambda m: print(f"[console.{m.type}] {m.text}"))
    page.on("pageerror", lambda e: print(f"[pageerror] {e}"))
    page.on("requestfailed", lambda r: print(f"[requestfailed] {r.url} {r.failure}"))
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


def wait_ready(page):
    """Wait until stylesheets have loaded and Alpine has initialised —
    CI runners are slow enough that JS/CSS-dependent steps race otherwise."""
    page.wait_for_load_state("load")
    page.wait_for_function("() => window.Alpine !== undefined")


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
    # The stylesheet must be served and contain the chord rules…
    css = page.request.get(live_server.url + "/static/css/tailwind.css")
    assert css.status == 200, f"stylesheet not served: {css.status}"
    assert "cp-chords" in css.text(), "built stylesheet is missing the ChordPro rules"
    # …and be applied: monospace font on both lines and whitespace preserved
    # (chords align by character column).
    wait_ready(page)
    styles = page.evaluate(
        """() => {
            const c = getComputedStyle(document.querySelector('.cp-chords'));
            const l = getComputedStyle(document.querySelector('.cp-lyrics'));
            return {fonts: [c.fontFamily, l.fontFamily], ws: c.whiteSpace};
        }"""
    )
    assert styles["ws"] == "pre", f"stylesheet not applied? white-space={styles['ws']}"
    assert styles["fonts"][0] == styles["fonts"][1]
    assert "JetBrains Mono" in styles["fonts"][0]
    # Chords render with [C] above "ty" of "county": the chord line's C must
    # sit at the same column as the lyric offset of "ty".
    chords_text = chord_line.text_content()
    lyrics_text = lyric_line.text_content()
    assert chords_text.startswith("F")
    assert chords_text.index("C") == lyrics_text.index("ty")

    # Upload an audio file and an image together. (The file input auto-submits
    # via Alpine, so Alpine must be initialised before selecting files.)
    wait_ready(page)
    wav_path = tmp_path / "rehearsal.wav"
    wav_path.write_bytes(make_wav())
    png_path = tmp_path / "chart.png"
    png_path.write_bytes(FAKE_PNG)
    with page.expect_navigation():
        page.set_input_files("input[type=file]", [str(wav_path), str(png_path)])
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

    # Reorder: drag the first item (chords) to the bottom. SortableJS must
    # have initialised for the drag to register.
    wait_ready(page)
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


def test_set_sharing_workflow(page, live_server, tmp_path, browser):
    """M6: build a set, toggle it public, open it logged out; private stays 404."""
    signup(page, live_server, "sasha", "sasha@example.com", "correct-horse-e2e-9")

    # Two songs, one with a chart and a recording.
    create_song(page, live_server, "sasha", "Opener")
    page.click("text=Add text")
    page.select_option("select[name=format]", "chordpro")
    page.fill("textarea[name=body]", "[C]Start me [G]up")
    page.click("main form button[type=submit]:not([form])")
    wait_ready(page)
    wav_path = tmp_path / "take.wav"
    wav_path.write_bytes(make_wav(0.5))
    with page.expect_navigation():
        page.set_input_files("input[type=file]", [str(wav_path)])
    expect(page.locator("audio")).to_have_count(1)
    create_song(page, live_server, "sasha", "Closer")

    # Build a set with both songs.
    page.goto(f"{live_server.url}/sasha/sets/new")
    page.fill("input[name=name]", "June Gigs")
    page.click("main form button[type=submit]:not([form])")
    page.wait_for_url("**/june-gigs/")
    page.select_option("select[name=song]", label="Opener")
    page.click("button:has-text('Add song')")
    page.select_option("select[name=song]", label="Closer")
    page.click("button:has-text('Add song')")
    expect(page.locator(".js-sortable input[name=entry]")).to_have_count(2)

    # Still private: a logged-out visitor gets 404s for the set and the song.
    set_url = f"{live_server.url}/sasha/june-gigs/"
    song_url = f"{live_server.url}/sasha/opener/"
    anon_context = browser.new_context()
    anon = anon_context.new_page()
    assert anon.goto(set_url).status == 404
    assert anon.goto(song_url).status == 404

    # Toggle the set public and copy the share link.
    page.click("button:has-text('Make public')")
    page.wait_for_load_state()
    expect(page.locator("span.text-emerald-700")).to_have_text("Public")
    expect(page.locator("button:has-text('Copy link')")).to_be_visible()

    # Logged out: the set page now renders the songs and their materials.
    assert anon.goto(set_url).status == 200
    expect(anon.locator("h1")).to_contain_text("June Gigs")
    expect(anon.locator(".cp-chords").first).to_be_visible()
    expect(anon.locator("audio")).to_have_count(1)
    # The audio file itself is served (via the can_view public-set rule).
    audio_src = anon.locator("audio").get_attribute("src")
    assert anon.request.get(live_server.url + audio_src).status == 200
    # Songs in the public set resolve directly too; no edit UI anywhere.
    assert anon.goto(song_url).status == 200
    assert anon.locator("text=Make private").count() == 0
    # Other private content is still hidden.
    assert anon.goto(f"{live_server.url}/sasha/closer/").status == 200  # in public set
    assert anon.goto(f"{live_server.url}/sasha/").status == 404  # owner page stays private

    # Toggle back to private: everything disappears for strangers again.
    page.click("button:has-text('Make private')")
    expect(page.locator("button:has-text('Make public')")).to_be_visible()
    assert anon.goto(set_url).status == 404
    assert anon.goto(song_url).status == 404
    anon_context.close()


def test_passkey_signup_and_login(page, live_server):
    """Passkey signup, then passkey login, with a CDP virtual authenticator.

    Regression test for the base template dropping allauth's extra_body
    block, which carries the login page's hidden mfa_login form + scripts.
    """
    cdp = page.context.new_cdp_session(page)
    cdp.send("WebAuthn.enable")
    cdp.send(
        "WebAuthn.addVirtualAuthenticator",
        {
            "options": {
                "protocol": "ctap2",
                "transport": "internal",
                "hasResidentKey": True,
                "hasUserVerification": True,
                "isUserVerified": True,
                "automaticPresenceSimulation": True,
            }
        },
    )

    # Sign up by passkey: identify, verify email by code, then create the key.
    page.goto(live_server.url + "/accounts/signup/passkey/")
    page.fill("input[name=username]", "keira")
    page.fill("input[name=email]", "keira@example.com")
    page.click("main form button[type=submit]:not([form])")
    page.wait_for_url("**/confirm-email/**")
    code = re.search(r"^([A-Z0-9]{3,8}(?:-[A-Z0-9]{3,8})?)$", mail.outbox[-1].body, re.MULTILINE)
    page.fill("input[name=code]", code.group(1))
    page.click("main form button[type=submit]:not([form])")
    # Passkey creation form (the virtual authenticator answers the prompt).
    expect(page.locator("input[name=name]")).to_be_visible()
    page.fill("input[name=name]", "Test key")
    wait_ready(page)
    page.click("#mfa_webauthn_signup")
    page.wait_for_url(live_server.url + "/")
    expect(page.locator("header nav")).to_contain_text("keira")

    # Log out, then sign back in with the passkey alone.
    page.click("header nav button:has-text('keira')")
    page.click("header nav form button:has-text('Log out')")
    page.wait_for_url(live_server.url + "/")
    page.goto(live_server.url + "/accounts/login/")
    wait_ready(page)
    page.click("#passkey_login")
    page.wait_for_url(live_server.url + "/")
    expect(page.locator("header nav")).to_contain_text("keira")


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
