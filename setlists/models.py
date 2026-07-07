from django.conf import settings
from django.db import models

from songs.models import Song, Visibility
from workspaces.models import Owner
from workspaces.validators import validate_lowercase_slug, validate_not_reserved


class Set(models.Model):
    """An ordered, named group of songs (a gig set, a practice list, …)."""

    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="sets")
    name = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=80,
        validators=[validate_lowercase_slug, validate_not_reserved],
    )
    description = models.TextField(blank=True)
    visibility = models.CharField(
        max_length=7, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="set_slug_unique_per_owner"),
        ]

    def __str__(self):
        return self.name

    def get_absolute_url(self) -> str:
        return f"/{self.owner.slug}/{self.slug}/"

    @property
    def is_public(self) -> bool:
        return self.visibility == Visibility.PUBLIC


class SetSong(models.Model):
    """Ordered membership of a song in a set; a song can be in many sets."""

    set = models.ForeignKey(Set, on_delete=models.CASCADE, related_name="set_songs")
    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="set_songs")
    position = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["position", "id"]
        constraints = [
            models.UniqueConstraint(fields=["set", "song"], name="song_once_per_set"),
        ]

    def __str__(self):
        return f"{self.song} in {self.set}"
