"""Song and item endpoints. Thin wrappers over the same service layer the
views use (generate_slug, can_view, user_can_act_for, validate_upload).
"""

from django.db.models import Max
from django.http import Http404
from django.shortcuts import get_object_or_404
from ninja import File, Router, Schema
from ninja.errors import HttpError
from ninja.files import UploadedFile
from ninja.responses import Status

from workspaces.models import Owner
from workspaces.services import user_can_act_for

from .models import Item, Song, Visibility
from .services import can_view, generate_slug
from .uploads import FALLBACK_CONTENT_TYPES, validate_upload

router = Router(tags=["songs"])


class SongOut(Schema):
    id: int
    owner: str
    title: str
    slug: str
    visibility: str
    url: str

    @staticmethod
    def resolve_owner(obj: Song) -> str:
        return obj.owner.slug

    @staticmethod
    def resolve_url(obj: Song) -> str:
        return obj.get_absolute_url()


class SongIn(Schema):
    title: str


class SongPatch(Schema):
    title: str | None = None
    visibility: str | None = None


class ItemOut(Schema):
    id: int
    kind: str
    position: int
    title: str
    body: str
    format: str
    original_filename: str
    content_type: str
    size: int
    file_url: str | None

    @staticmethod
    def resolve_file_url(obj: Item) -> str | None:
        if not obj.file:
            return None
        return f"/{obj.song.owner.slug}/{obj.song.slug}/items/{obj.pk}/file"


class TextItemIn(Schema):
    body: str
    format: str = Item.TextFormat.PLAIN
    title: str = ""


class TextItemPatch(Schema):
    body: str | None = None
    format: str | None = None
    title: str | None = None


class ReorderIn(Schema):
    ids: list[int]


def get_owner_for_edit(request, owner_slug: str) -> Owner:
    owner = get_object_or_404(Owner, slug=owner_slug)
    if not user_can_act_for(request.user, owner):
        raise Http404
    return owner


def get_song(request, owner_slug: str, song_slug: str, for_edit: bool = False) -> Song:
    song = get_object_or_404(
        Song.objects.select_related("owner"), owner__slug=owner_slug, slug=song_slug
    )
    if for_edit:
        if not user_can_act_for(request.user, song.owner):
            raise Http404
    elif not can_view(request.user, song):
        raise Http404
    return song


def next_position(song: Song) -> int:
    return (song.items.aggregate(m=Max("position"))["m"] or 0) + 1


@router.get("/owners/{owner_slug}/songs", response=list[SongOut])
def list_songs(request, owner_slug: str):
    owner = get_owner_for_edit(request, owner_slug)
    return owner.songs.select_related("owner")


@router.post("/owners/{owner_slug}/songs", response={201: SongOut})
def create_song(request, owner_slug: str, payload: SongIn):
    owner = get_owner_for_edit(request, owner_slug)
    title = payload.title.strip()
    if not title:
        raise HttpError(400, "Title is required.")
    song = Song.objects.create(
        owner=owner, title=title, slug=generate_slug(owner, title), created_by=request.user
    )
    return Status(201, song)


@router.get("/owners/{owner_slug}/songs/{song_slug}", response=SongOut)
def get_song_detail(request, owner_slug: str, song_slug: str):
    return get_song(request, owner_slug, song_slug)


@router.patch("/owners/{owner_slug}/songs/{song_slug}", response=SongOut)
def update_song(request, owner_slug: str, song_slug: str, payload: SongPatch):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    if payload.title is not None:
        title = payload.title.strip()
        if not title:
            raise HttpError(400, "Title cannot be empty.")
        song.title = title
    if payload.visibility is not None:
        if payload.visibility not in Visibility.values:
            raise HttpError(400, f"visibility must be one of {Visibility.values}.")
        song.visibility = payload.visibility
    song.save()
    return song


@router.delete("/owners/{owner_slug}/songs/{song_slug}", response={204: None})
def delete_song(request, owner_slug: str, song_slug: str):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    song.delete()
    return Status(204, None)


@router.get("/owners/{owner_slug}/songs/{song_slug}/items", response=list[ItemOut])
def list_items(request, owner_slug: str, song_slug: str):
    song = get_song(request, owner_slug, song_slug)
    return song.items.select_related("song__owner")


@router.post("/owners/{owner_slug}/songs/{song_slug}/items", response={201: ItemOut})
def create_text_item(request, owner_slug: str, song_slug: str, payload: TextItemIn):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    if not payload.body.strip():
        raise HttpError(400, "body is required.")
    if payload.format not in Item.TextFormat.values:
        raise HttpError(400, f"format must be one of {Item.TextFormat.values}.")
    item = Item.objects.create(
        song=song,
        kind=Item.Kind.TEXT,
        title=payload.title,
        body=payload.body,
        format=payload.format,
        position=next_position(song),
    )
    return Status(201, item)


@router.post("/owners/{owner_slug}/songs/{song_slug}/items/upload", response={201: ItemOut})
def upload_item(request, owner_slug: str, song_slug: str, file: File[UploadedFile]):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    kind, error = validate_upload(file)
    if error:
        raise HttpError(400, error)
    item = Item.objects.create(
        song=song,
        kind=kind,
        position=next_position(song),
        file=file,
        original_filename=file.name[:255],
        content_type=file.content_type or FALLBACK_CONTENT_TYPES[kind],
        size=file.size,
    )
    return Status(201, item)


@router.post("/owners/{owner_slug}/songs/{song_slug}/items/reorder", response=list[ItemOut])
def reorder_items(request, owner_slug: str, song_slug: str, payload: ReorderIn):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    items = {item.pk: item for item in song.items.all()}
    changed = []
    for position, item_id in enumerate(payload.ids, start=1):
        item = items.get(item_id)
        if item is not None and item.position != position:
            item.position = position
            changed.append(item)
    Item.objects.bulk_update(changed, ["position"])
    return song.items.select_related("song__owner")


@router.patch("/owners/{owner_slug}/songs/{song_slug}/items/{item_id}", response=ItemOut)
def update_text_item(
    request, owner_slug: str, song_slug: str, item_id: int, payload: TextItemPatch
):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    item = get_object_or_404(song.items, pk=item_id, kind=Item.Kind.TEXT)
    if payload.body is not None:
        if not payload.body.strip():
            raise HttpError(400, "body cannot be empty.")
        item.body = payload.body
    if payload.format is not None:
        if payload.format not in Item.TextFormat.values:
            raise HttpError(400, f"format must be one of {Item.TextFormat.values}.")
        item.format = payload.format
    if payload.title is not None:
        item.title = payload.title
    item.save()
    return item


@router.delete("/owners/{owner_slug}/songs/{song_slug}/items/{item_id}", response={204: None})
def delete_item(request, owner_slug: str, song_slug: str, item_id: int):
    song = get_song(request, owner_slug, song_slug, for_edit=True)
    item = get_object_or_404(song.items, pk=item_id)
    item.file.delete(save=False)
    item.delete()
    return Status(204, None)
