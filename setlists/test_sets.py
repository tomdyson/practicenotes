import pytest
from django.contrib.auth.models import AnonymousUser

from setlists.models import Set, SetSong
from songs.models import Item, Song
from songs.services import can_view
from workspaces.slugs import generate_content_slug

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice", "a@example.com", "pw-alice-9")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob", "b@example.com", "pw-bob-9")


@pytest.fixture
def songs(alice):
    owner = alice.owner_profile
    return [
        Song.objects.create(owner=owner, title=f"Song {i}", slug=f"song-{i}") for i in (1, 2, 3)
    ]


@pytest.fixture
def gig_set(alice, songs):
    setlist = Set.objects.create(owner=alice.owner_profile, name="June Gigs", slug="june-gigs")
    for position, song in enumerate(songs[:2], start=1):
        SetSong.objects.create(set=setlist, song=song, position=position)
    return setlist


class TestCrossModelSlugs:
    def test_set_slug_avoids_song_slug(self, alice, songs):
        # songs fixture claimed song-1..3; a set named "Song 1" must not
        # collide in the shared /<owner>/<slug> namespace.
        assert generate_content_slug(alice.owner_profile, "Song 1") == "song-1-2"

    def test_song_slug_avoids_set_slug(self, alice, gig_set):
        assert generate_content_slug(alice.owner_profile, "June Gigs") == "june-gigs-2"


class TestSetCrud:
    def test_create(self, client, alice):
        client.force_login(alice)
        response = client.post(
            "/alice/sets/new", {"name": "Acoustic Night", "description": "short one"}
        )
        assert response.status_code == 302
        setlist = Set.objects.get(owner__slug="alice", slug="acoustic-night")
        assert setlist.created_by == alice

    def test_stranger_cannot_create(self, client, bob):
        client.force_login(bob)
        assert client.post("/alice/sets/new", {"name": "X"}).status_code == 404

    def test_set_page_resolves_via_content_url(self, client, alice, gig_set):
        client.force_login(alice)
        response = client.get("/alice/june-gigs/")
        assert response.status_code == 200
        assert b"June Gigs" in response.content

    def test_private_set_404_for_stranger(self, client, bob, gig_set):
        client.force_login(bob)
        assert client.get("/alice/june-gigs/").status_code == 404

    def test_public_set_viewable_logged_out(self, client, gig_set):
        gig_set.visibility = "public"
        gig_set.save()
        response = client.get("/alice/june-gigs/")
        assert response.status_code == 200

    def test_edit(self, client, alice, gig_set):
        client.force_login(alice)
        response = client.post(
            "/alice/sets/june-gigs/edit", {"name": "July Gigs", "description": ""}
        )
        assert response.status_code == 302
        gig_set.refresh_from_db()
        assert gig_set.name == "July Gigs"
        assert gig_set.slug == "june-gigs"

    def test_delete_keeps_songs(self, client, alice, gig_set, songs):
        client.force_login(alice)
        client.post("/alice/sets/june-gigs/delete")
        assert not Set.objects.filter(pk=gig_set.pk).exists()
        assert Song.objects.filter(owner__slug="alice").count() == 3


class TestSetSongs:
    def test_add_song(self, client, alice, gig_set, songs):
        client.force_login(alice)
        response = client.post("/alice/sets/june-gigs/songs/add", {"song": songs[2].pk})
        assert response.status_code == 302
        assert gig_set.set_songs.count() == 3
        assert gig_set.set_songs.last().song == songs[2]

    def test_add_song_twice_is_noop(self, client, alice, gig_set, songs):
        client.force_login(alice)
        client.post("/alice/sets/june-gigs/songs/add", {"song": songs[0].pk})
        assert gig_set.set_songs.filter(song=songs[0]).count() == 1

    def test_cannot_add_other_owners_song(self, client, alice, bob, gig_set):
        other_song = Song.objects.create(owner=bob.owner_profile, title="Mine", slug="mine")
        client.force_login(alice)
        response = client.post("/alice/sets/june-gigs/songs/add", {"song": other_song.pk})
        assert response.status_code == 404

    def test_remove_song(self, client, alice, gig_set):
        entry = gig_set.set_songs.first()
        client.force_login(alice)
        response = client.post(f"/alice/sets/june-gigs/songs/{entry.pk}/remove")
        assert response.status_code == 302
        assert gig_set.set_songs.count() == 1

    def test_reorder(self, client, alice, gig_set):
        entries = list(gig_set.set_songs.all())
        client.force_login(alice)
        response = client.post(
            "/alice/sets/june-gigs/reorder",
            {"entry": [str(entries[1].pk), str(entries[0].pk)]},
        )
        assert response.status_code == 204
        assert list(gig_set.set_songs.values_list("pk", flat=True)) == [
            entries[1].pk,
            entries[0].pk,
        ]

    def test_stranger_cannot_reorder(self, client, bob, gig_set):
        client.force_login(bob)
        assert client.post("/alice/sets/june-gigs/reorder", {"entry": ["1"]}).status_code == 404

    def test_set_page_renders_song_materials(self, client, alice, gig_set, songs):
        Item.objects.create(
            song=songs[0], kind="text", format="chordpro", body="[C]La la", position=1
        )
        client.force_login(alice)
        response = client.get("/alice/june-gigs/")
        assert b'class="cp-chord"' in response.content


class TestPublicSetExposesSongs:
    def test_private_song_in_public_set_is_viewable(self, gig_set, songs, bob):
        gig_set.visibility = "public"
        gig_set.save()
        assert can_view(AnonymousUser(), songs[0])
        assert can_view(bob, songs[0])

    def test_private_song_not_in_public_set_stays_hidden(self, gig_set, songs):
        gig_set.visibility = "public"
        gig_set.save()
        # songs[2] is not in the set.
        assert not can_view(AnonymousUser(), songs[2])

    def test_song_page_reachable_when_in_public_set(self, client, gig_set, songs):
        gig_set.visibility = "public"
        gig_set.save()
        assert client.get("/alice/song-1/").status_code == 200
        assert client.get("/alice/song-3/").status_code == 404
