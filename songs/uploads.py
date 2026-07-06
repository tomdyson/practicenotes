"""Upload classification and validation.

Kind is derived from the file extension (browser MIME types are unreliable,
especially for audio); the content type is stored for serving but not
trusted for classification.
"""

from django.conf import settings

from .models import Item

EXTENSION_KINDS = {
    "mp3": Item.Kind.AUDIO,
    "m4a": Item.Kind.AUDIO,
    "wav": Item.Kind.AUDIO,
    "ogg": Item.Kind.AUDIO,
    "opus": Item.Kind.AUDIO,
    "jpg": Item.Kind.IMAGE,
    "jpeg": Item.Kind.IMAGE,
    "png": Item.Kind.IMAGE,
    "gif": Item.Kind.IMAGE,
    "webp": Item.Kind.IMAGE,
    "pdf": Item.Kind.PDF,
}

FALLBACK_CONTENT_TYPES = {
    Item.Kind.AUDIO: "audio/mpeg",
    Item.Kind.IMAGE: "application/octet-stream",
    Item.Kind.PDF: "application/pdf",
}

ACCEPT_ATTRIBUTE = ",".join("." + ext for ext in EXTENSION_KINDS)


def classify(filename: str) -> Item.Kind | None:
    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    return EXTENSION_KINDS.get(ext)


def validate_upload(uploaded_file) -> tuple[Item.Kind | None, str | None]:
    """Return (kind, None) for an acceptable file or (None, error_message)."""
    kind = classify(uploaded_file.name)
    if kind is None:
        return None, (
            f"“{uploaded_file.name}” isn't a supported type. "
            "Upload audio (mp3, m4a, wav, ogg), images (jpg, png, gif, webp) or PDFs."
        )
    if uploaded_file.size > settings.MAX_UPLOAD_BYTES:
        cap_mb = settings.MAX_UPLOAD_BYTES // (1024 * 1024)
        return None, f"“{uploaded_file.name}” is too large (limit {cap_mb} MB)."
    return kind, None
