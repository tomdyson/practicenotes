import pytest

from songs.models import Item, Song
from songs.services import can_view, generate_slug

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice", "a@example.com", "pw-alice-9")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob", "b@example.com", "pw-bob-9")


@pytest.fixture
def song(alice):
    owner = alice.owner_profile
    return Song.objects.create(
        owner=owner, title="Wichita Lineman", slug="wichita-lineman", created_by=alice
    )


def login(client, user):
    client.force_login(user)


class TestSlugGeneration:
    def test_basic(self, alice):
        assert generate_slug(alice.owner_profile, "Wichita Lineman") == "wichita-lineman"

    def test_collision_appends_counter(self, alice, song):
        assert generate_slug(alice.owner_profile, "Wichita Lineman") == "wichita-lineman-2"

    def test_reserved_word_skipped(self, alice):
        assert generate_slug(alice.owner_profile, "Admin") == "admin-2"

    def test_empty_title_falls_back(self, alice):
        assert generate_slug(alice.owner_profile, "!!!") == "untitled"


class TestSongCrud:
    def test_create(self, client, alice):
        login(client, alice)
        response = client.post("/alice/songs/new", {"title": "June Hymn"})
        assert response.status_code == 302
        song = Song.objects.get(owner__slug="alice", slug="june-hymn")
        assert song.created_by == alice
        assert not song.is_public

    def test_cannot_create_for_other_owner(self, client, alice, bob):
        login(client, bob)
        response = client.post("/alice/songs/new", {"title": "Sneaky"})
        assert response.status_code == 404
        assert not Song.objects.filter(title="Sneaky").exists()

    def test_owner_views_own_private_song(self, client, alice, song):
        login(client, alice)
        response = client.get("/alice/wichita-lineman/")
        assert response.status_code == 200
        assert b"Wichita Lineman" in response.content

    def test_stranger_gets_404_for_private_song(self, client, bob, song):
        login(client, bob)
        assert client.get("/alice/wichita-lineman/").status_code == 404

    def test_anonymous_gets_404_for_private_song(self, client, song):
        assert client.get("/alice/wichita-lineman/").status_code == 404

    def test_edit_title(self, client, alice, song):
        login(client, alice)
        response = client.post("/alice/wichita-lineman/edit", {"title": "Wichita"})
        assert response.status_code == 302
        song.refresh_from_db()
        assert song.title == "Wichita"
        assert song.slug == "wichita-lineman"  # slug is stable

    def test_delete(self, client, alice, song):
        login(client, alice)
        response = client.post("/alice/wichita-lineman/delete")
        assert response.status_code == 302
        assert not Song.objects.filter(pk=song.pk).exists()

    def test_stranger_cannot_delete(self, client, bob, song):
        login(client, bob)
        assert client.post("/alice/wichita-lineman/delete").status_code == 404
        assert Song.objects.filter(pk=song.pk).exists()


class TestCanView:
    def test_public_song_viewable_by_anonymous(self, song):
        from django.contrib.auth.models import AnonymousUser

        song.visibility = "public"
        song.save()
        assert can_view(AnonymousUser(), song)

    def test_private_song_not_viewable_by_stranger(self, song, bob):
        assert not can_view(bob, song)

    def test_private_song_viewable_by_owner(self, song, alice):
        assert can_view(alice, song)


class TestTextItems:
    def test_create_text_item(self, client, alice, song):
        login(client, alice)
        response = client.post(
            "/alice/wichita-lineman/items/new",
            {"title": "Chords", "format": "chordpro", "body": "[F]I am a lineman"},
        )
        assert response.status_code == 302
        item = song.items.get()
        assert item.kind == Item.Kind.TEXT
        assert item.format == "chordpro"
        assert item.position == 1

    def test_chordpro_item_renders_chords(self, client, alice, song):
        Item.objects.create(
            song=song, kind="text", format="chordpro", body="[F]I am a lineman", position=1
        )
        login(client, alice)
        response = client.get("/alice/wichita-lineman/")
        assert b'class="cp-chord"' in response.content

    def test_monospace_item_renders_pre(self, client, alice, song):
        Item.objects.create(
            song=song, kind="text", format="monospace", body="e|---0---|", position=1
        )
        login(client, alice)
        response = client.get("/alice/wichita-lineman/")
        assert b"e|---0---|" in response.content
        assert b"prose-chords" in response.content

    def test_edit_text_item(self, client, alice, song):
        item = Item.objects.create(song=song, kind="text", format="plain", body="v1", position=1)
        login(client, alice)
        response = client.post(
            f"/alice/wichita-lineman/items/{item.pk}/edit",
            {"title": "", "format": "plain", "body": "v2"},
        )
        assert response.status_code == 302
        item.refresh_from_db()
        assert item.body == "v2"

    def test_delete_item(self, client, alice, song):
        item = Item.objects.create(song=song, kind="text", body="bye", position=1)
        login(client, alice)
        client.post(f"/alice/wichita-lineman/items/{item.pk}/delete")
        assert not song.items.exists()

    def test_stranger_cannot_add_items(self, client, bob, song):
        login(client, bob)
        response = client.post(
            "/alice/wichita-lineman/items/new",
            {"title": "", "format": "plain", "body": "graffiti"},
        )
        assert response.status_code == 404


class TestReorder:
    def test_reorder(self, client, alice, song):
        items = [
            Item.objects.create(song=song, kind="text", body=f"item {i}", position=i)
            for i in (1, 2, 3)
        ]
        login(client, alice)
        new_order = [items[2].pk, items[0].pk, items[1].pk]
        response = client.post(
            "/alice/wichita-lineman/items/reorder",
            {"item": [str(pk) for pk in new_order]},
        )
        assert response.status_code == 204
        assert list(song.items.values_list("pk", flat=True)) == new_order

    def test_stranger_cannot_reorder(self, client, bob, song):
        Item.objects.create(song=song, kind="text", body="x", position=1)
        login(client, bob)
        response = client.post("/alice/wichita-lineman/items/reorder", {"item": ["1"]})
        assert response.status_code == 404
