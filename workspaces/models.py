from django.conf import settings
from django.db import models

from .validators import validate_lowercase_slug, validate_not_reserved


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
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(kind="user", user__isnull=False)
                    | models.Q(kind="band", user__isnull=True)
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
        return self.slug
