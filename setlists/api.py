from django.db.models import Max
from django.shortcuts import get_object_or_404
from ninja import Router, Schema
from ninja.errors import HttpError
from ninja.responses import Status

from songs.api import SongOut, get_owner_for_edit
from songs.models import Song, Visibility

from .models import Set, SetSong

router = Router(tags=["sets"])


class SetOut(Schema):
    id: int
    owner: str
    name: str
    slug: str
    description: str
    visibility: str
    url: str

    @staticmethod
    def resolve_owner(obj: Set) -> str:
        return obj.owner.slug

    @staticmethod
    def resolve_url(obj: Set) -> str:
        return obj.get_absolute_url()


class SetEntryOut(Schema):
    position: int
    song: SongOut


class SetDetailOut(SetOut):
    songs: list[SetEntryOut]

    @staticmethod
    def resolve_songs(obj: Set):
        return [
            {"position": entry.position, "song": entry.song}
            for entry in obj.set_songs.select_related("song__owner")
        ]


class SetIn(Schema):
    name: str
    description: str = ""


class SetPatch(Schema):
    name: str | None = None
    description: str | None = None
    visibility: str | None = None


class AddSongIn(Schema):
    song_id: int


class ReorderIn(Schema):
    song_ids: list[int]


def get_set(request, owner_slug: str, set_slug: str) -> Set:
    # All API set access is owner/member-scoped (mirrors get_owner_for_edit).
    get_owner_for_edit(request, owner_slug)
    return get_object_or_404(
        Set.objects.select_related("owner"), owner__slug=owner_slug, slug=set_slug
    )


@router.get("/owners/{owner_slug}/sets", response=list[SetOut])
def list_sets(request, owner_slug: str):
    owner = get_owner_for_edit(request, owner_slug)
    return owner.sets.select_related("owner")


@router.post("/owners/{owner_slug}/sets", response={201: SetOut})
def create_set(request, owner_slug: str, payload: SetIn):
    from workspaces.slugs import generate_content_slug

    owner = get_owner_for_edit(request, owner_slug)
    name = payload.name.strip()
    if not name:
        raise HttpError(400, "Name is required.")
    setlist = Set.objects.create(
        owner=owner,
        name=name,
        slug=generate_content_slug(owner, name),
        description=payload.description,
        created_by=request.user,
    )
    return Status(201, setlist)


@router.get("/owners/{owner_slug}/sets/{set_slug}", response=SetDetailOut)
def get_set_detail(request, owner_slug: str, set_slug: str):
    return get_set(request, owner_slug, set_slug)


@router.patch("/owners/{owner_slug}/sets/{set_slug}", response=SetOut)
def update_set(request, owner_slug: str, set_slug: str, payload: SetPatch):
    setlist = get_set(request, owner_slug, set_slug)
    if payload.name is not None:
        name = payload.name.strip()
        if not name:
            raise HttpError(400, "Name cannot be empty.")
        setlist.name = name
    if payload.description is not None:
        setlist.description = payload.description
    if payload.visibility is not None:
        if payload.visibility not in Visibility.values:
            raise HttpError(400, f"visibility must be one of {Visibility.values}.")
        setlist.visibility = payload.visibility
    setlist.save()
    return setlist


@router.delete("/owners/{owner_slug}/sets/{set_slug}", response={204: None})
def delete_set(request, owner_slug: str, set_slug: str):
    setlist = get_set(request, owner_slug, set_slug)
    setlist.delete()
    return Status(204, None)


@router.post("/owners/{owner_slug}/sets/{set_slug}/songs", response=SetDetailOut)
def add_song(request, owner_slug: str, set_slug: str, payload: AddSongIn):
    setlist = get_set(request, owner_slug, set_slug)
    song = get_object_or_404(Song, pk=payload.song_id, owner=setlist.owner)
    position = (setlist.set_songs.aggregate(m=Max("position"))["m"] or 0) + 1
    SetSong.objects.get_or_create(set=setlist, song=song, defaults={"position": position})
    return setlist


@router.delete("/owners/{owner_slug}/sets/{set_slug}/songs/{song_id}", response={204: None})
def remove_song(request, owner_slug: str, set_slug: str, song_id: int):
    setlist = get_set(request, owner_slug, set_slug)
    entry = get_object_or_404(setlist.set_songs, song_id=song_id)
    entry.delete()
    return Status(204, None)


@router.post("/owners/{owner_slug}/sets/{set_slug}/reorder", response=SetDetailOut)
def reorder_set(request, owner_slug: str, set_slug: str, payload: ReorderIn):
    setlist = get_set(request, owner_slug, set_slug)
    entries = {entry.song_id: entry for entry in setlist.set_songs.all()}
    changed = []
    for position, song_id in enumerate(payload.song_ids, start=1):
        entry = entries.get(song_id)
        if entry is not None and entry.position != position:
            entry.position = position
            changed.append(entry)
    SetSong.objects.bulk_update(changed, ["position"])
    return setlist
