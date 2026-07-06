import uuid

from django.conf import settings
from django.db import models

from workspaces.models import Owner
from workspaces.validators import validate_lowercase_slug, validate_not_reserved


class Visibility(models.TextChoices):
    PRIVATE = "private", "Private"
    PUBLIC = "public", "Public"


class Song(models.Model):
    owner = models.ForeignKey(Owner, on_delete=models.CASCADE, related_name="songs")
    title = models.CharField(max_length=200)
    slug = models.SlugField(
        max_length=80,
        validators=[validate_lowercase_slug, validate_not_reserved],
    )
    visibility = models.CharField(
        max_length=7, choices=Visibility.choices, default=Visibility.PRIVATE
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name="+"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["title"]
        constraints = [
            models.UniqueConstraint(fields=["owner", "slug"], name="song_slug_unique_per_owner"),
        ]

    def __str__(self):
        return self.title

    def get_absolute_url(self) -> str:
        return f"/{self.owner.slug}/{self.slug}/"

    @property
    def is_public(self) -> bool:
        return self.visibility == Visibility.PUBLIC


def item_upload_path(instance, filename: str) -> str:
    # Keys are unguessable (uuid) and never reused; the original filename
    # lives on the model, not in the key, to dodge encoding/length issues.
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else "bin"
    return f"items/{uuid.uuid4().hex}.{ext}"


class Item(models.Model):
    """One piece of practice material for a song: a text or a file.

    A single table gives one mixed ordering of text and files per song.
    """

    class Kind(models.TextChoices):
        TEXT = "text", "Text"
        AUDIO = "audio", "Audio"
        IMAGE = "image", "Image"
        PDF = "pdf", "PDF"

    class TextFormat(models.TextChoices):
        PLAIN = "plain", "Plain text"
        CHORDPRO = "chordpro", "ChordPro"
        MONOSPACE = "monospace", "Monospace"

    song = models.ForeignKey(Song, on_delete=models.CASCADE, related_name="items")
    position = models.PositiveIntegerField(default=0)
    kind = models.CharField(max_length=5, choices=Kind.choices)
    title = models.CharField(max_length=200, blank=True)

    # Text items
    body = models.TextField(blank=True)
    format = models.CharField(
        max_length=9, choices=TextFormat.choices, default=TextFormat.PLAIN, blank=True
    )

    # File items (uploads land in M3)
    file = models.FileField(upload_to=item_upload_path, blank=True, max_length=255)
    original_filename = models.CharField(max_length=255, blank=True)
    content_type = models.CharField(max_length=100, blank=True)
    size = models.PositiveBigIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "id"]

    def __str__(self):
        return self.title or f"{self.get_kind_display()} item"
