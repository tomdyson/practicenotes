import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from workspaces.models import Owner

pytestmark = pytest.mark.django_db


def test_owner_created_on_user_creation():
    user = User.objects.create_user("tom", "tom@example.com", "pw")
    owner = user.owner_profile
    assert owner.slug == "tom"
    assert owner.kind == Owner.Kind.USER


def test_owner_slug_lowercased_from_username():
    user = User.objects.create_user("MixedCase", "mc@example.com", "pw")
    assert user.owner_profile.slug == "mixedcase"


def test_reserved_username_creates_no_owner():
    user = User.objects.create_user("admin", "admin@example.com", "pw")
    assert not Owner.objects.filter(user=user).exists()


@pytest.mark.parametrize("slug", ["admin", "api", "accounts", "static", "media", "health"])
def test_reserved_slugs_fail_validation(slug):
    user = User.objects.create_user(f"u{slug}", "u@example.com", "pw")
    owner = Owner(slug=slug, kind=Owner.Kind.USER, user=user)
    with pytest.raises(ValidationError) as exc:
        owner.full_clean()
    assert "slug" in exc.value.error_dict


@pytest.mark.parametrize("slug", ["-leading", "trailing-", "has_underscore", "Has-Upper", "a b"])
def test_malformed_slugs_fail_validation(slug):
    user = User.objects.create_user("someone", "s@example.com", "pw")
    owner = Owner(slug=slug, kind=Owner.Kind.USER, user=user)
    with pytest.raises(ValidationError):
        owner.full_clean()


def test_owner_slug_unique():
    User.objects.create_user("dupe", "d1@example.com", "pw")
    with pytest.raises(IntegrityError):
        user2 = User.objects.create_user("other", "d2@example.com", "pw")
        Owner.objects.create(slug="dupe", kind=Owner.Kind.USER, user=user2)
