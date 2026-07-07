"""M6 — sharing: visibility toggles, public pages, can_view everywhere."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from setlists.models import Set, SetSong
from songs.models import Item, Song

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice", "a@example.com", "pw-alice-9")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob", "b@example.com", "pw-bob-9")


@pytest.fixture
def song(alice):
    song = Song.objects.create(owner=alice.owner_profile, title="Lineman", slug="lineman")
    Item.objects.create(song=song, kind="text", format="chordpro", body="[F]I am", position=1)
    return song


@pytest.fixture
def audio_item(client, alice, song):
    client.force_login(alice)
    client.post(
        "/alice/lineman/items/upload",
        {
            "files": [
                SimpleUploadedFile("take.mp3", b"\xff\xfb\x90\x00" + b"\x00" * 64, "audio/mpeg")
            ]
        },
    )
    client.logout()
    return song.items.get(kind="audio")


class TestVisibilityToggle:
    def test_owner_toggles_song_public(self, client, alice, song):
        client.force_login(alice)
        response = client.post("/alice/lineman/visibility", {"visibility": "public"})
        assert response.status_code == 302
        song.refresh_from_db()
        assert song.is_public

    def test_owner_toggles_song_private_again(self, client, alice, song):
        song.visibility = "public"
        song.save()
        client.force_login(alice)
        client.post("/alice/lineman/visibility", {"visibility": "private"})
        song.refresh_from_db()
        assert not song.is_public

    def test_bogus_value_ignored(self, client, alice, song):
        client.force_login(alice)
        client.post("/alice/lineman/visibility", {"visibility": "friends-only"})
        song.refresh_from_db()
        assert song.visibility == "private"

    def test_stranger_cannot_toggle(self, client, bob, song):
        client.force_login(bob)
        response = client.post("/alice/lineman/visibility", {"visibility": "public"})
        assert response.status_code == 404
        song.refresh_from_db()
        assert not song.is_public

    def test_set_toggle(self, client, alice, song):
        setlist = Set.objects.create(owner=alice.owner_profile, name="Gigs", slug="gigs")
        client.force_login(alice)
        client.post("/alice/sets/gigs/visibility", {"visibility": "public"})
        setlist.refresh_from_db()
        assert setlist.is_public


class TestPublicPages:
    def test_public_song_page_logged_out(self, client, song):
        song.visibility = "public"
        song.save()
        response = client.get("/alice/lineman/")
        assert response.status_code == 200
        assert b"cp-chord" in response.content
        # No edit affordances for anonymous visitors.
        assert b"Make private" not in response.content
        assert b"items/new" not in response.content

    def test_public_song_file_logged_out(self, client, song, audio_item):
        song.visibility = "public"
        song.save()
        response = client.get(f"/alice/lineman/items/{audio_item.pk}/file")
        assert response.status_code == 200

    def test_private_song_file_404_logged_out(self, client, song, audio_item):
        response = client.get(f"/alice/lineman/items/{audio_item.pk}/file")
        assert response.status_code == 404

    def test_public_set_page_shows_song_materials_logged_out(self, client, alice, song):
        setlist = Set.objects.create(
            owner=alice.owner_profile, name="Gigs", slug="gigs", visibility="public"
        )
        SetSong.objects.create(set=setlist, song=song, position=1)
        response = client.get("/alice/gigs/")
        assert response.status_code == 200
        assert b"Lineman" in response.content
        assert b"cp-chord" in response.content
        assert b"Manage songs" not in response.content

    def test_file_in_public_set_accessible_logged_out(self, client, alice, song, audio_item):
        setlist = Set.objects.create(
            owner=alice.owner_profile, name="Gigs", slug="gigs", visibility="public"
        )
        SetSong.objects.create(set=setlist, song=song, position=1)
        response = client.get(f"/alice/lineman/items/{audio_item.pk}/file")
        assert response.status_code == 200

    def test_making_set_private_again_hides_songs(self, client, alice, song, audio_item):
        setlist = Set.objects.create(
            owner=alice.owner_profile, name="Gigs", slug="gigs", visibility="public"
        )
        SetSong.objects.create(set=setlist, song=song, position=1)
        assert client.get("/alice/lineman/").status_code == 200
        setlist.visibility = "private"
        setlist.save()
        assert client.get("/alice/lineman/").status_code == 404
        assert client.get(f"/alice/lineman/items/{audio_item.pk}/file").status_code == 404


class TestShareUi:
    def test_owner_sees_share_bar_and_copy_link(self, client, alice, song):
        song.visibility = "public"
        song.save()
        client.force_login(alice)
        response = client.get("/alice/lineman/")
        assert b"Copy link" in response.content
        assert b"Make private" in response.content

    def test_private_song_offers_make_public(self, client, alice, song):
        client.force_login(alice)
        response = client.get("/alice/lineman/")
        assert b"Make public" in response.content
