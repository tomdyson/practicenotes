from workspaces.models import Owner
from workspaces.services import user_can_act_for
from workspaces.slugs import generate_content_slug

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
    # Imported lazily: songs is a dependency of setlists, not vice versa.
    from setlists.models import SetSong

    return SetSong.objects.filter(song=song, set__visibility="public").exists()


def generate_slug(owner: Owner, title: str) -> str:
    return generate_content_slug(owner, title)
