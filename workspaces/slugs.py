from django.utils.text import slugify

from .reserved import RESERVED_SLUGS


def taken_content_slugs(owner) -> set[str]:
    """Slugs already used by this owner across songs AND sets — /<owner>/<slug>
    is one flat namespace, so the two models may not collide."""
    from setlists.models import Set
    from songs.models import Song

    taken = set(Song.objects.filter(owner=owner).values_list("slug", flat=True))
    taken |= set(Set.objects.filter(owner=owner).values_list("slug", flat=True))
    return taken


def generate_content_slug(owner, title: str) -> str:
    return unique_slug(title, taken_content_slugs(owner))


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
