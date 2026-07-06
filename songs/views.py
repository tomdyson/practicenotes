from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.files.storage import FileSystemStorage
from django.db.models import Max
from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils.encoding import iri_to_uri
from django.views.decorators.http import require_POST

from workspaces.models import Owner
from workspaces.services import user_can_act_for

from .forms import SongForm, TextItemForm
from .models import Item, Song
from .services import can_view, generate_slug
from .uploads import FALLBACK_CONTENT_TYPES, validate_upload


def get_owner_or_404(request, owner_slug: str, for_edit: bool = True) -> Owner:
    owner = get_object_or_404(Owner, slug=owner_slug)
    if for_edit and not user_can_act_for(request.user, owner):
        raise Http404
    return owner


def get_song_or_404(request, owner_slug: str, song_slug: str, for_edit: bool = False) -> Song:
    song = get_object_or_404(
        Song.objects.select_related("owner"), owner__slug=owner_slug, slug=song_slug
    )
    if for_edit:
        if not user_can_act_for(request.user, song.owner):
            raise Http404
    elif not can_view(request.user, song):
        raise Http404
    return song


def song_detail(request, song: Song):
    from .uploads import ACCEPT_ATTRIBUTE

    can_edit = user_can_act_for(request.user, song.owner)
    return render(
        request,
        "songs/song_detail.html",
        {
            "song": song,
            "items": song.items.all(),
            "can_edit": can_edit,
            "upload_accept": ACCEPT_ATTRIBUTE,
        },
    )


@login_required
def song_create(request, owner_slug):
    owner = get_owner_or_404(request, owner_slug)
    form = SongForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        song = form.save(commit=False)
        song.owner = owner
        song.slug = generate_slug(owner, song.title)
        song.created_by = request.user
        song.save()
        return redirect(song.get_absolute_url())
    return render(request, "songs/song_form.html", {"form": form, "owner": owner})


@login_required
def song_edit(request, owner_slug, song_slug):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    form = SongForm(request.POST or None, instance=song)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(song.get_absolute_url())
    return render(
        request, "songs/song_form.html", {"form": form, "owner": song.owner, "song": song}
    )


@login_required
@require_POST
def song_delete(request, owner_slug, song_slug):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    song.delete()
    return redirect(song.owner.get_absolute_url())


@login_required
def item_create(request, owner_slug, song_slug):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    form = TextItemForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        item = form.save(commit=False)
        item.song = song
        item.kind = Item.Kind.TEXT
        item.position = (song.items.aggregate(m=Max("position"))["m"] or 0) + 1
        item.save()
        return redirect(song.get_absolute_url())
    return render(request, "songs/item_form.html", {"form": form, "song": song})


@login_required
def item_edit(request, owner_slug, song_slug, item_id):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    item = get_object_or_404(song.items, pk=item_id, kind=Item.Kind.TEXT)
    form = TextItemForm(request.POST or None, instance=item)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(song.get_absolute_url())
    return render(request, "songs/item_form.html", {"form": form, "song": song, "item": item})


@login_required
@require_POST
def item_delete(request, owner_slug, song_slug, item_id):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    item = get_object_or_404(song.items, pk=item_id)
    item.file.delete(save=False)
    item.delete()
    return redirect(song.get_absolute_url())


@login_required
@require_POST
def item_upload(request, owner_slug, song_slug):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    files = request.FILES.getlist("files")
    if not files:
        messages.error(request, "Choose one or more files to upload.")
        return redirect(song.get_absolute_url())
    position = song.items.aggregate(m=Max("position"))["m"] or 0
    uploaded = 0
    for uploaded_file in files:
        kind, error = validate_upload(uploaded_file)
        if error:
            messages.error(request, error)
            continue
        position += 1
        Item.objects.create(
            song=song,
            kind=kind,
            position=position,
            file=uploaded_file,
            original_filename=uploaded_file.name[:255],
            content_type=uploaded_file.content_type or FALLBACK_CONTENT_TYPES[kind],
            size=uploaded_file.size,
        )
        uploaded += 1
    if uploaded:
        messages.success(request, f"Uploaded {uploaded} file{'s' if uploaded != 1 else ''}.")
    return redirect(song.get_absolute_url())


def item_file(request, owner_slug, song_slug, item_id):
    """Hand out file content, gated on can_view.

    S3-compatible storage: redirect to a short-lived presigned URL.
    Filesystem storage (dev/tests): stream the file through Django —
    media files are deliberately not URL-routed anywhere else.
    """
    song = get_song_or_404(request, owner_slug, song_slug)
    item = get_object_or_404(song.items, pk=item_id)
    if not item.file:
        raise Http404
    storage = item.file.storage
    if isinstance(storage, FileSystemStorage):
        response = FileResponse(
            item.file.open("rb"),
            content_type=item.content_type or "application/octet-stream",
        )
        filename = iri_to_uri(item.original_filename or item.file.name)
        response["Content-Disposition"] = f"inline; filename*=UTF-8''{filename}"
        return response
    return redirect(item.file.url)


@login_required
@require_POST
def item_reorder(request, owner_slug, song_slug):
    song = get_song_or_404(request, owner_slug, song_slug, for_edit=True)
    ids = request.POST.getlist("item")
    items = {str(item.pk): item for item in song.items.all()}
    changed = []
    for position, item_id in enumerate(ids, start=1):
        item = items.get(item_id)
        if item is not None and item.position != position:
            item.position = position
            changed.append(item)
    Item.objects.bulk_update(changed, ["position"])
    return HttpResponse(status=204)
