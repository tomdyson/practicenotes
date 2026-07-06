from workspaces.models import Owner
from workspaces.services import user_can_act_for
from workspaces.slugs import unique_slug

from .models import Song


def can_view(user, song: Song) -> bool:
    """The single visibility rule: a song is viewable if it is public, or a
    public set contains it, or the viewer can act for its owner.

    Everything that exposes song content (pages, file URLs, the API) must
    route through here.
    """
    if song.is_public:
        return True
    if user_can_act_for(user, song.owner):
        return True
    if _in_public_set(song):
        return True
    return False


def _in_public_set(song: Song) -> bool:
    # Sets arrive in M4; import lazily so songs doesn't hard-depend on
    # setlists at module load.
    try:
        from setlists.models import SetSong
    except ImportError:
        return False
    return SetSong.objects.filter(song=song, set__visibility="public").exists()


def taken_slugs(owner: Owner) -> set[str]:
    """Slugs already used by this owner across songs and sets (flat space)."""
    taken = set(Song.objects.filter(owner=owner).values_list("slug", flat=True))
    try:
        from setlists.models import Set
    except ImportError:
        return taken
    taken |= set(Set.objects.filter(owner=owner).values_list("slug", flat=True))
    return taken


def generate_slug(owner: Owner, title: str) -> str:
    return unique_slug(title, taken_slugs(owner))
