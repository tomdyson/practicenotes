from django.utils.text import slugify

from .reserved import RESERVED_SLUGS


def unique_slug(base: str, taken: set[str], max_length: int = 80) -> str:
    """Slugify `base`, avoiding reserved words and anything in `taken`."""
    slug = slugify(base)[:max_length].strip("-") or "untitled"
    candidate = slug
    counter = 2
    while candidate in RESERVED_SLUGS or candidate in taken:
        suffix = f"-{counter}"
        candidate = slug[: max_length - len(suffix)] + suffix
        counter += 1
    return candidate
