from django.contrib.auth.decorators import login_required
from django.db.models import Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from songs.models import Song
from songs.views import get_owner_or_404
from workspaces.services import user_can_act_for
from workspaces.slugs import generate_content_slug

from .forms import SetForm
from .models import Set, SetSong
from .services import can_view_set


def get_set_or_404(request, owner_slug: str, set_slug: str, for_edit: bool = False) -> Set:
    setlist = get_object_or_404(
        Set.objects.select_related("owner"), owner__slug=owner_slug, slug=set_slug
    )
    if for_edit:
        if not user_can_act_for(request.user, setlist.owner):
            raise Http404
    elif not can_view_set(request.user, setlist):
        raise Http404
    return setlist


def set_detail(request, setlist: Set):
    can_edit = user_can_act_for(request.user, setlist.owner)
    entries = setlist.set_songs.select_related("song__owner").prefetch_related("song__items")
    context = {
        "setlist": setlist,
        "entries": entries,
        "can_edit": can_edit,
    }
    if can_edit:
        in_set = [entry.song_id for entry in entries]
        context["addable_songs"] = setlist.owner.songs.exclude(pk__in=in_set)
    return render(request, "setlists/set_detail.html", context)


@login_required
def set_create(request, owner_slug):
    owner = get_owner_or_404(request, owner_slug)
    form = SetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        setlist = form.save(commit=False)
        setlist.owner = owner
        setlist.slug = generate_content_slug(owner, setlist.name)
        setlist.created_by = request.user
        setlist.save()
        return redirect(setlist.get_absolute_url())
    return render(request, "setlists/set_form.html", {"form": form, "owner": owner})


@login_required
def set_edit(request, owner_slug, set_slug):
    setlist = get_set_or_404(request, owner_slug, set_slug, for_edit=True)
    form = SetForm(request.POST or None, instance=setlist)
    if request.method == "POST" and form.is_valid():
        form.save()
        return redirect(setlist.get_absolute_url())
    return render(
        request,
        "setlists/set_form.html",
        {"form": form, "owner": setlist.owner, "setlist": setlist},
    )


@login_required
@require_POST
def set_delete(request, owner_slug, set_slug):
    setlist = get_set_or_404(request, owner_slug, set_slug, for_edit=True)
    setlist.delete()
    return redirect(setlist.owner.get_absolute_url())


@login_required
@require_POST
def set_add_song(request, owner_slug, set_slug):
    setlist = get_set_or_404(request, owner_slug, set_slug, for_edit=True)
    song = get_object_or_404(Song, pk=request.POST.get("song"), owner=setlist.owner)
    position = (setlist.set_songs.aggregate(m=Max("position"))["m"] or 0) + 1
    SetSong.objects.get_or_create(set=setlist, song=song, defaults={"position": position})
    return redirect(setlist.get_absolute_url())


@login_required
@require_POST
def set_remove_song(request, owner_slug, set_slug, entry_id):
    setlist = get_set_or_404(request, owner_slug, set_slug, for_edit=True)
    entry = get_object_or_404(setlist.set_songs, pk=entry_id)
    entry.delete()
    return redirect(setlist.get_absolute_url())


@login_required
@require_POST
def set_reorder(request, owner_slug, set_slug):
    setlist = get_set_or_404(request, owner_slug, set_slug, for_edit=True)
    ids = request.POST.getlist("entry")
    entries = {str(entry.pk): entry for entry in setlist.set_songs.all()}
    changed = []
    for position, entry_id in enumerate(ids, start=1):
        entry = entries.get(entry_id)
        if entry is not None and entry.position != position:
            entry.position = position
            changed.append(entry)
    SetSong.objects.bulk_update(changed, ["position"])
    return HttpResponse(status=204)
