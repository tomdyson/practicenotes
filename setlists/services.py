from workspaces.services import user_can_act_for

from .models import Set


def can_view_set(user, setlist: Set) -> bool:
    """A set is viewable if it is public or the viewer can act for its owner.

    Songs inside a public set become viewable through songs.services.can_view
    (the public-set clause); this function gates the set page itself.
    """
    return setlist.is_public or user_can_act_for(user, setlist.owner)
