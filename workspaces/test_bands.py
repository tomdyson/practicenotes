from datetime import timedelta

import pytest
from django.utils import timezone

from songs.models import Song
from workspaces.models import Band, BandInvite, Membership, Owner

pytestmark = pytest.mark.django_db


@pytest.fixture
def alice(django_user_model):
    return django_user_model.objects.create_user("alice", "a@example.com", "pw-alice-9")


@pytest.fixture
def bob(django_user_model):
    return django_user_model.objects.create_user("bob", "b@example.com", "pw-bob-9")


@pytest.fixture
def carol(django_user_model):
    return django_user_model.objects.create_user("carol", "c@example.com", "pw-carol-9")


@pytest.fixture
def band(alice):
    band = Band.objects.create(name="The Quiet Ones", created_by=alice)
    Owner.objects.create(slug="quiet-ones", kind=Owner.Kind.BAND, band=band)
    Membership.objects.create(band=band, user=alice, role=Membership.Role.OWNER)
    return band


@pytest.fixture
def bob_member(band, bob):
    return Membership.objects.create(band=band, user=bob, role=Membership.Role.MEMBER)


class TestBandCreation:
    def test_create_band_claims_owner_slug(self, client, alice):
        client.force_login(alice)
        response = client.post("/bands/new", {"name": "Slow Club", "slug": "slow-club"})
        assert response.status_code == 302
        owner = Owner.objects.get(slug="slow-club")
        assert owner.kind == Owner.Kind.BAND
        assert owner.band.name == "Slow Club"
        membership = owner.band.memberships.get()
        assert membership.user == alice
        assert membership.role == Membership.Role.OWNER

    def test_band_cannot_take_username_slug(self, client, alice, bob):
        client.force_login(alice)
        response = client.post("/bands/new", {"name": "Bob Impostors", "slug": "bob"})
        assert response.status_code == 200  # form error
        assert not Band.objects.filter(name="Bob Impostors").exists()

    def test_band_cannot_take_reserved_slug(self, client, alice):
        client.force_login(alice)
        response = client.post("/bands/new", {"name": "Admins", "slug": "admin"})
        assert response.status_code == 200
        assert not Band.objects.filter(name="Admins").exists()

    def test_username_cannot_take_band_slug(self, client, band):
        response = client.post(
            "/accounts/signup/",
            {
                "username": "quiet-ones",
                "email": "q@example.com",
                "password1": "horse-battery-9",
            },
        )
        assert response.status_code == 200
        from django.contrib.auth.models import User

        assert not User.objects.filter(username="quiet-ones").exists()


class TestBandPermissions:
    def test_member_can_create_band_song(self, client, band, bob_member, bob):
        client.force_login(bob)
        response = client.post("/quiet-ones/songs/new", {"title": "Our Tune"})
        assert response.status_code == 302
        assert Song.objects.filter(owner__slug="quiet-ones", title="Our Tune").exists()

    def test_member_can_view_band_private_song(self, client, band, bob_member, bob, alice):
        client.force_login(alice)
        client.post("/quiet-ones/songs/new", {"title": "Our Tune"})
        client.force_login(bob)
        assert client.get("/quiet-ones/our-tune/").status_code == 200

    def test_non_member_cannot_create_band_song(self, client, band, carol):
        client.force_login(carol)
        assert client.post("/quiet-ones/songs/new", {"title": "Nope"}).status_code == 404

    def test_non_member_gets_404_on_band_page(self, client, band, carol):
        client.force_login(carol)
        assert client.get("/quiet-ones/").status_code == 404

    def test_member_sees_band_on_dashboard(self, client, band, bob_member, bob):
        client.force_login(bob)
        response = client.get("/")
        assert b"The Quiet Ones" in response.content

    def test_member_cannot_manage(self, client, band, bob_member, bob):
        client.force_login(bob)
        assert client.post("/bands/quiet-ones/invites/new", {}).status_code == 404
        assert client.post("/bands/quiet-ones/rename", {"name": "X"}).status_code == 404

    def test_owner_can_rename(self, client, band, alice):
        client.force_login(alice)
        response = client.post("/bands/quiet-ones/rename", {"name": "The Loud Ones"})
        assert response.status_code == 302
        band.refresh_from_db()
        assert band.name == "The Loud Ones"

    def test_owner_can_remove_member(self, client, band, bob_member, alice):
        client.force_login(alice)
        response = client.post(f"/bands/quiet-ones/members/{bob_member.pk}/remove")
        assert response.status_code == 302
        assert not band.memberships.filter(user=bob_member.user).exists()

    def test_owner_cannot_be_removed(self, client, band, alice):
        owner_membership = band.memberships.get(user=alice)
        client.force_login(alice)
        client.post(f"/bands/quiet-ones/members/{owner_membership.pk}/remove")
        assert band.memberships.filter(pk=owner_membership.pk).exists()

    def test_member_can_leave(self, client, band, bob_member, bob):
        client.force_login(bob)
        response = client.post("/bands/quiet-ones/leave")
        assert response.status_code == 302
        assert not band.memberships.filter(user=bob).exists()


class TestInvites:
    def make_invite(self, band, **kwargs):
        return BandInvite.objects.create(band=band, **kwargs)

    def test_owner_creates_invite(self, client, band, alice):
        client.force_login(alice)
        response = client.post("/bands/quiet-ones/invites/new", {"expires_days": "7"})
        assert response.status_code == 302
        invite = band.invites.get()
        assert invite.is_active
        assert invite.expires_at is not None

    def test_logged_in_user_joins_via_invite(self, client, band, carol):
        invite = self.make_invite(band)
        client.force_login(carol)
        response = client.get(f"/join/{invite.token}/")
        assert b"Join The Quiet Ones" in response.content
        response = client.post(f"/join/{invite.token}/")
        assert response.status_code == 302
        assert band.memberships.filter(user=carol, role="member").exists()

    def test_joining_twice_is_idempotent(self, client, band, carol):
        invite = self.make_invite(band)
        client.force_login(carol)
        client.post(f"/join/{invite.token}/")
        client.post(f"/join/{invite.token}/")
        assert band.memberships.filter(user=carol).count() == 1

    def test_revoked_invite_rejected(self, client, band, carol):
        invite = self.make_invite(band, revoked_at=timezone.now())
        client.force_login(carol)
        assert client.get(f"/join/{invite.token}/").status_code == 410
        client.post(f"/join/{invite.token}/")
        assert not band.memberships.filter(user=carol).exists()

    def test_expired_invite_rejected(self, client, band, carol):
        invite = self.make_invite(band, expires_at=timezone.now() - timedelta(hours=1))
        client.force_login(carol)
        assert client.get(f"/join/{invite.token}/").status_code == 410
        client.post(f"/join/{invite.token}/")
        assert not band.memberships.filter(user=carol).exists()

    def test_unexpired_invite_active(self, band):
        invite = self.make_invite(band, expires_at=timezone.now() + timedelta(days=7))
        assert invite.is_active

    def test_revoke_endpoint(self, client, band, alice, carol):
        invite = self.make_invite(band)
        client.force_login(alice)
        response = client.post(f"/bands/quiet-ones/invites/{invite.pk}/revoke")
        assert response.status_code == 302
        invite.refresh_from_db()
        assert not invite.is_active
        # And the link now rejects joiners.
        client.force_login(carol)
        client.post(f"/join/{invite.token}/")
        assert not band.memberships.filter(user=carol).exists()

    def test_bad_token_is_410(self, client):
        assert client.get("/join/not-a-real-token/").status_code == 410

    def test_join_through_signup_flow(self, client, band):
        """Anonymous visitor opens the invite, signs up, lands back in the join
        flow via the pending-invite session stash, and joins."""
        import re

        from django.core import mail

        invite = self.make_invite(band)
        response = client.get(f"/join/{invite.token}/")
        assert b"Sign up to join" in response.content
        assert client.session["pending_invite"] == invite.token

        response = client.post(
            "/accounts/signup/",
            {"username": "newbie", "email": "n@example.com", "password1": "horse-battery-9"},
        )
        code = re.search(
            r"^([A-Z0-9]{3,8}(?:-[A-Z0-9]{3,8})?)$", mail.outbox[-1].body, re.MULTILINE
        )
        client.post("/accounts/confirm-email/", {"code": code.group(1)})

        # Landing on home redirects to the pending join page…
        response = client.get("/")
        assert response.status_code == 302
        assert response.headers["Location"] == f"/join/{invite.token}/"
        # …where the (now logged-in) user confirms.
        client.post(f"/join/{invite.token}/")
        assert band.memberships.filter(user__username="newbie", role="member").exists()
