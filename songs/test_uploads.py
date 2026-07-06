import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from songs.models import Item, Song

pytestmark = pytest.mark.django_db

# A tiny but valid-enough MP3 frame header followed by junk.
FAKE_MP3 = b"\xff\xfb\x90\x00" + b"\x00" * 128
FAKE_PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
FAKE_PDF = b"%PDF-1.4\n%%EOF\n"


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice", "a@example.com", "pw-alice-9")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob", "b@example.com", "pw-bob-9")


@pytest.fixture
def song(alice):
    return Song.objects.create(owner=alice.owner_profile, title="Take", slug="take")


def upload(client, files):
    return client.post("/alice/take/items/upload", {"files": files})


class TestUpload:
    def test_upload_audio_image_pdf(self, client, alice, song):
        client.force_login(alice)
        response = upload(
            client,
            [
                SimpleUploadedFile("rehearsal.mp3", FAKE_MP3, "audio/mpeg"),
                SimpleUploadedFile("chart.png", FAKE_PNG, "image/png"),
                SimpleUploadedFile("score.pdf", FAKE_PDF, "application/pdf"),
            ],
        )
        assert response.status_code == 302
        kinds = list(song.items.values_list("kind", flat=True))
        assert kinds == ["audio", "image", "pdf"]
        audio = song.items.get(kind="audio")
        assert audio.original_filename == "rehearsal.mp3"
        assert audio.content_type == "audio/mpeg"
        assert audio.size == len(FAKE_MP3)
        assert audio.file.name.startswith("items/")
        assert audio.file.name.endswith(".mp3")

    def test_unsupported_extension_rejected(self, client, alice, song):
        client.force_login(alice)
        response = upload(client, [SimpleUploadedFile("virus.exe", b"MZ", "application/x-dos")])
        assert response.status_code == 302
        assert not song.items.exists()

    def test_over_cap_rejected(self, client, alice, song, settings):
        settings.MAX_UPLOAD_BYTES = 10
        client.force_login(alice)
        response = upload(client, [SimpleUploadedFile("big.mp3", FAKE_MP3, "audio/mpeg")])
        assert response.status_code == 302
        assert not song.items.exists()

    def test_stranger_cannot_upload(self, client, bob, song):
        client.force_login(bob)
        response = upload(client, [SimpleUploadedFile("x.mp3", FAKE_MP3, "audio/mpeg")])
        assert response.status_code == 404

    def test_positions_append_after_existing(self, client, alice, song):
        Item.objects.create(song=song, kind="text", body="lyrics", position=1)
        client.force_login(alice)
        upload(client, [SimpleUploadedFile("a.mp3", FAKE_MP3, "audio/mpeg")])
        assert song.items.get(kind="audio").position == 2


class TestFileServing:
    @pytest.fixture
    def audio_item(self, client, alice, song):
        client.force_login(alice)
        upload(client, [SimpleUploadedFile("a.mp3", FAKE_MP3, "audio/mpeg")])
        client.logout()
        return song.items.get()

    def file_url(self, item):
        return f"/alice/take/items/{item.pk}/file"

    def test_owner_can_fetch_file(self, client, alice, audio_item):
        client.force_login(alice)
        response = client.get(self.file_url(audio_item))
        assert response.status_code == 200
        assert response.headers["Content-Type"] == "audio/mpeg"
        assert b"".join(response.streaming_content) == FAKE_MP3

    def test_stranger_gets_404(self, client, bob, audio_item):
        client.force_login(bob)
        assert client.get(self.file_url(audio_item)).status_code == 404

    def test_anonymous_gets_404_for_private(self, client, audio_item):
        assert client.get(self.file_url(audio_item)).status_code == 404

    def test_anonymous_can_fetch_public_song_file(self, client, song, audio_item):
        song.visibility = "public"
        song.save()
        assert client.get(self.file_url(audio_item)).status_code == 200

    def test_text_item_has_no_file(self, client, alice, song):
        item = Item.objects.create(song=song, kind="text", body="x", position=1)
        client.force_login(alice)
        assert client.get(self.file_url(item)).status_code == 404
