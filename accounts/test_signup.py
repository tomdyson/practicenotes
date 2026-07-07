import re

import pytest
from django.contrib.auth.models import User
from django.core import mail

from workspaces.models import Owner

pytestmark = pytest.mark.django_db

SIGNUP_URL = "/accounts/signup/"


def signup(client, username="frida", email="frida@example.com", password="horse-battery-9"):
    return client.post(
        SIGNUP_URL,
        {"username": username, "email": email, "password1": password},
    )


def verify_email_code(client):
    """Complete the email-verification-by-code stage using the emailed code."""
    body = mail.outbox[-1].body
    match = re.search(r"^([A-Z0-9]{3,8}(?:-[A-Z0-9]{3,8})?)$", body, re.MULTILINE)
    assert match, f"No verification code found in email:\n{body}"
    return client.post("/accounts/confirm-email/", {"code": match.group(1)})


def test_signup_creates_user_and_owner(client):
    response = signup(client)
    assert response.status_code == 302
    user = User.objects.get(username="frida")
    assert Owner.objects.filter(user=user, slug="frida", kind="user").exists()


def test_signup_then_email_verification_logs_in(client):
    signup(client)
    assert len(mail.outbox) == 1
    response = verify_email_code(client)
    assert response.status_code == 302
    response = client.get("/")
    assert response.wsgi_request.user.is_authenticated


def test_reserved_username_rejected(client):
    response = signup(client, username="admin", email="a@example.com")
    assert response.status_code == 200
    assert not User.objects.filter(username="admin").exists()


def test_invalid_username_rejected(client):
    response = signup(client, username="has spaces", email="h@example.com")
    assert response.status_code == 200
    assert not User.objects.filter(username="has spaces").exists()


def test_username_colliding_with_owner_slug_rejected(client):
    # A band has claimed the slug: the namespace check must consult Owner,
    # not just the User table.
    from workspaces.models import Band

    band = Band.objects.create(name="Quiet Ones")
    Owner.objects.create(slug="quiet-ones", kind=Owner.Kind.BAND, band=band)
    response = signup(client, username="quiet-ones", email="q@example.com")
    assert response.status_code == 200
    assert not User.objects.filter(username="quiet-ones").exists()


def test_password_login(client):
    User.objects.create_user("gigi", "g@example.com", "horse-battery-9")
    response = client.post("/accounts/login/", {"login": "gigi", "password": "horse-battery-9"})
    assert response.status_code == 302


def test_owner_page_requires_owner(client):
    User.objects.create_user("private-p", "p@example.com", "pw")
    # Stranger (anonymous) gets a 404, not a redirect or 200.
    assert client.get("/private-p/").status_code == 404


def test_owner_page_visible_to_self(client):
    User.objects.create_user("selfie", "s@example.com", "horse-battery-9")
    client.login(username="selfie", password="horse-battery-9")
    assert client.get("/selfie/").status_code == 200
