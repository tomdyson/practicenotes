"""M7 — /api/v1 (django-ninja, session auth)."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from setlists.models import Set
from songs.models import Item, Song

pytestmark = pytest.mark.django_db

API = "/api/v1"


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice", "a@example.com", "pw-alice-9")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob", "b@example.com", "pw-bob-9")


@pytest.fixture
def as_alice(client, alice):
    client.force_login(alice)
    return client


def post_json(client, url, data):
    return client.post(url, data, content_type="application/json")


def patch_json(client, url, data):
    return client.patch(url, data, content_type="application/json")


class TestAuthAndDocs:
    def test_unauthenticated_is_401(self, client):
        assert client.get(f"{API}/owners").status_code == 401

    def test_docs_available(self, client):
        assert client.get(f"{API}/docs").status_code == 200

    def test_openapi_schema(self, client):
        response = client.get(f"{API}/openapi.json")
        assert response.status_code == 200
        paths = response.json()["paths"]
        assert f"{API}/owners/{{owner_slug}}/songs" in paths


class TestOwners:
    def test_list_owners(self, as_alice):
        response = as_alice.get(f"{API}/owners")
        assert response.status_code == 200
        assert response.json() == [{"slug": "alice", "kind": "user", "display_name": "alice"}]


class TestSongs:
    def test_song_crud_roundtrip(self, as_alice):
        # Create
        response = post_json(as_alice, f"{API}/owners/alice/songs", {"title": "June Hymn"})
        assert response.status_code == 201
        data = response.json()
        assert data["slug"] == "june-hymn"
        assert data["url"] == "/alice/june-hymn/"
        # List + detail
        assert len(as_alice.get(f"{API}/owners/alice/songs").json()) == 1
        assert as_alice.get(f"{API}/owners/alice/songs/june-hymn").json()["title"] == "June Hymn"
        # Patch title + visibility
        response = patch_json(
            as_alice,
            f"{API}/owners/alice/songs/june-hymn",
            {"title": "June Hymn (v2)", "visibility": "public"},
        )
        assert response.status_code == 200
        song = Song.objects.get(slug="june-hymn")
        assert song.title == "June Hymn (v2)"
        assert song.is_public
        # Delete
        assert as_alice.delete(f"{API}/owners/alice/songs/june-hymn").status_code == 204
        assert not Song.objects.exists()

    def test_bad_visibility_rejected(self, as_alice):
        post_json(as_alice, f"{API}/owners/alice/songs", {"title": "S"})
        response = patch_json(as_alice, f"{API}/owners/alice/songs/s", {"visibility": "friends"})
        assert response.status_code == 400

    def test_cannot_touch_other_owner(self, as_alice, bob):
        Song.objects.create(owner=bob.owner_profile, title="Bob's", slug="bobs")
        assert post_json(as_alice, f"{API}/owners/bob/songs", {"title": "X"}).status_code == 404
        assert as_alice.get(f"{API}/owners/bob/songs").status_code == 404
        assert as_alice.get(f"{API}/owners/bob/songs/bobs").status_code == 404


class TestItems:
    @pytest.fixture
    def song(self, alice):
        return Song.objects.create(owner=alice.owner_profile, title="Take", slug="take")

    def test_text_item_crud(self, as_alice, song):
        response = post_json(
            as_alice,
            f"{API}/owners/alice/songs/take/items",
            {"body": "[C]La", "format": "chordpro", "title": "Chords"},
        )
        assert response.status_code == 201
        item_id = response.json()["id"]
        assert response.json()["position"] == 1
        # Patch
        response = patch_json(
            as_alice,
            f"{API}/owners/alice/songs/take/items/{item_id}",
            {"body": "[D]La"},
        )
        assert response.status_code == 200
        assert Item.objects.get(pk=item_id).body == "[D]La"
        # Delete
        assert as_alice.delete(f"{API}/owners/alice/songs/take/items/{item_id}").status_code == 204

    def test_bad_format_rejected(self, as_alice, song):
        response = post_json(
            as_alice, f"{API}/owners/alice/songs/take/items", {"body": "x", "format": "docx"}
        )
        assert response.status_code == 400

    def test_upload(self, as_alice, song):
        response = as_alice.post(
            f"{API}/owners/alice/songs/take/items/upload",
            {"file": SimpleUploadedFile("take.mp3", b"\xff\xfb\x90\x00" * 8, "audio/mpeg")},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["kind"] == "audio"
        assert data["file_url"].endswith("/file")

    def test_upload_rejects_bad_type(self, as_alice, song):
        response = as_alice.post(
            f"{API}/owners/alice/songs/take/items/upload",
            {"file": SimpleUploadedFile("x.exe", b"MZ", "application/x-dos")},
        )
        assert response.status_code == 400

    def test_reorder(self, as_alice, song):
        items = [
            Item.objects.create(song=song, kind="text", body=f"i{i}", position=i) for i in (1, 2, 3)
        ]
        new_order = [items[2].pk, items[0].pk, items[1].pk]
        response = post_json(
            as_alice, f"{API}/owners/alice/songs/take/items/reorder", {"ids": new_order}
        )
        assert response.status_code == 200
        assert [item["id"] for item in response.json()] == new_order


class TestSets:
    @pytest.fixture
    def songs(self, alice):
        return [
            Song.objects.create(owner=alice.owner_profile, title=f"S{i}", slug=f"s{i}")
            for i in (1, 2)
        ]

    def test_set_crud_and_membership(self, as_alice, songs):
        # Create
        response = post_json(
            as_alice, f"{API}/owners/alice/sets", {"name": "June Gigs", "description": "d"}
        )
        assert response.status_code == 201
        assert response.json()["slug"] == "june-gigs"
        # Add songs
        for song in songs:
            response = post_json(
                as_alice, f"{API}/owners/alice/sets/june-gigs/songs", {"song_id": song.pk}
            )
            assert response.status_code == 200
        detail = as_alice.get(f"{API}/owners/alice/sets/june-gigs").json()
        assert [entry["song"]["slug"] for entry in detail["songs"]] == ["s1", "s2"]
        # Reorder
        response = post_json(
            as_alice,
            f"{API}/owners/alice/sets/june-gigs/reorder",
            {"song_ids": [songs[1].pk, songs[0].pk]},
        )
        assert [entry["song"]["slug"] for entry in response.json()["songs"]] == ["s2", "s1"]
        # Visibility via patch
        patch_json(as_alice, f"{API}/owners/alice/sets/june-gigs", {"visibility": "public"})
        assert Set.objects.get(slug="june-gigs").is_public
        # Remove a song
        assert (
            as_alice.delete(f"{API}/owners/alice/sets/june-gigs/songs/{songs[0].pk}").status_code
            == 204
        )
        # Delete the set (songs survive)
        assert as_alice.delete(f"{API}/owners/alice/sets/june-gigs").status_code == 204
        assert Song.objects.count() == 2

    def test_cannot_touch_other_owners_set(self, as_alice, bob):
        Set.objects.create(owner=bob.owner_profile, name="X", slug="x")
        assert as_alice.get(f"{API}/owners/bob/sets/x").status_code == 404
