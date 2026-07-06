import secrets

from django.conf import settings
from django.db import models
from django.utils import timezone

from .validators import validate_lowercase_slug, validate_not_reserved


class Band(models.Model):
    name = models.CharField(max_length=100)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    @property
    def owner(self) -> "Owner":
        return self.owner_profile


class Owner(models.Model):
    """A namespace slot in the flat /<owner>/ namespace: a user or a band."""

    class Kind(models.TextChoices):
        USER = "user", "User"
        BAND = "band", "Band"

    slug = models.SlugField(
        max_length=50,
        unique=True,
        validators=[validate_lowercase_slug, validate_not_reserved],
    )
    kind = models.CharField(max_length=4, choices=Kind.choices)
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="owner_profile",
    )
    band = models.OneToOneField(
        Band,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="owner_profile",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="user", user__isnull=False, band__isnull=True)
                    | models.Q(kind="band", band__isnull=False, user__isnull=True)
                ),
                name="owner_kind_matches_link",
            ),
        ]

    def __str__(self):
        return self.slug

    def get_absolute_url(self) -> str:
        return f"/{self.slug}/"

    @property
    def display_name(self) -> str:
        if self.kind == self.Kind.USER and self.user:
            return self.user.username
        if self.kind == self.Kind.BAND and self.band:
            return self.band.name
        return self.slug


class Membership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        MEMBER = "member", "Member"

    band = models.ForeignKey(Band, on_delete=models.CASCADE, related_name="memberships")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="band_memberships"
    )
    role = models.CharField(max_length=6, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["band", "user"], name="one_membership_per_user"),
        ]

    def __str__(self):
        return f"{self.user} in {self.band} ({self.role})"


def make_invite_token() -> str:
    return secrets.token_urlsafe(16)


class BandInvite(models.Model):
    """A revocable, optionally-expiring invite link (/join/<token>/)."""

    band = models.ForeignKey(Band, on_delete=models.CASCADE, related_name="invites")
    token = models.CharField(max_length=32, unique=True, default=make_invite_token)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True)
    revoked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"Invite to {self.band}"

    def get_absolute_url(self) -> str:
        return f"/join/{self.token}/"

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None and self.expires_at <= timezone.now():
            return False
        return True
