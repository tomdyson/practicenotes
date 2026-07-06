from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import BandForm, BandRenameForm
from .models import Band, BandInvite, Membership, Owner
from .services import owners_for_user, user_can_act_for, user_is_band_owner


def home(request):
    if not request.user.is_authenticated:
        return render(request, "home.html")
    # Finish a join that started while logged out (invite link → signup).
    pending = request.session.pop("pending_invite", None)
    if pending:
        return redirect("band-join", token=pending)
    owners = owners_for_user(request.user)
    return render(request, "workspaces/dashboard.html", {"owners": owners})


def owner_page(request, owner_slug):
    owner = get_object_or_404(Owner, slug=owner_slug)
    # Owner pages are private in v1 (public profile pages are backlog #17):
    # strangers get a 404, not a 403, to avoid leaking namespace existence.
    if not user_can_act_for(request.user, owner):
        raise Http404
    return render(
        request,
        "workspaces/owner.html",
        {"owner": owner, "songs": owner.songs.all(), "sets": owner.sets.all()},
    )


# --- Bands ---


def get_band_or_404(request, band_slug: str, manage: bool = False) -> Band:
    owner = get_object_or_404(
        Owner.objects.select_related("band"), slug=band_slug, kind=Owner.Kind.BAND
    )
    band = owner.band
    if not user_can_act_for(request.user, owner):
        raise Http404
    if manage and not user_is_band_owner(request.user, band):
        raise Http404
    return band


@login_required
def band_create(request):
    form = BandForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        band = form.save()
        band.created_by = request.user
        band.save(update_fields=["created_by"])
        Owner.objects.create(slug=form.cleaned_data["slug"], kind=Owner.Kind.BAND, band=band)
        Membership.objects.create(band=band, user=request.user, role=Membership.Role.OWNER)
        messages.success(request, f"{band.name} is ready — invite your bandmates below.")
        return redirect("band-manage", band_slug=form.cleaned_data["slug"])
    return render(request, "workspaces/band_form.html", {"form": form})


def band_manage(request, band_slug):
    band = get_band_or_404(request, band_slug)
    is_owner = user_is_band_owner(request.user, band)
    context = {
        "band": band,
        "owner": band.owner,
        "is_owner": is_owner,
        "memberships": band.memberships.select_related("user").order_by("created_at"),
        "my_membership": band.memberships.filter(user=request.user).first(),
        "rename_form": BandRenameForm(instance=band) if is_owner else None,
    }
    if is_owner:
        context["invites"] = band.invites.filter(revoked_at=None).order_by("-created_at")
    return render(request, "workspaces/band_manage.html", context)


@login_required
@require_POST
def band_rename(request, band_slug):
    band = get_band_or_404(request, band_slug, manage=True)
    form = BandRenameForm(request.POST, instance=band)
    if form.is_valid():
        form.save()
        messages.success(request, "Band renamed.")
    return redirect("band-manage", band_slug=band_slug)


@login_required
@require_POST
def invite_create(request, band_slug):
    band = get_band_or_404(request, band_slug, manage=True)
    expires_at = None
    days = request.POST.get("expires_days")
    if days and days.isdigit() and int(days) > 0:
        expires_at = timezone.now() + timedelta(days=int(days))
    BandInvite.objects.create(band=band, created_by=request.user, expires_at=expires_at)
    return redirect("band-manage", band_slug=band_slug)


@login_required
@require_POST
def invite_revoke(request, band_slug, invite_id):
    band = get_band_or_404(request, band_slug, manage=True)
    invite = get_object_or_404(band.invites, pk=invite_id)
    if invite.revoked_at is None:
        invite.revoked_at = timezone.now()
        invite.save(update_fields=["revoked_at"])
    return redirect("band-manage", band_slug=band_slug)


@login_required
@require_POST
def member_remove(request, band_slug, membership_id):
    band = get_band_or_404(request, band_slug, manage=True)
    membership = get_object_or_404(band.memberships, pk=membership_id)
    if membership.role == Membership.Role.OWNER:
        messages.error(request, "Band owners can't be removed.")
    else:
        membership.delete()
        messages.success(request, f"Removed {membership.user.username}.")
    return redirect("band-manage", band_slug=band_slug)


@login_required
@require_POST
def band_leave(request, band_slug):
    band = get_band_or_404(request, band_slug)
    membership = get_object_or_404(band.memberships, user=request.user)
    if membership.role == Membership.Role.OWNER:
        messages.error(request, "Owners can't leave their own band in v1.")
        return redirect("band-manage", band_slug=band_slug)
    membership.delete()
    messages.success(request, f"You left {band.name}.")
    return redirect("home")


def band_join(request, token):
    invite = BandInvite.objects.filter(token=token).select_related("band").first()
    valid = invite is not None and invite.is_active
    if request.method == "POST":
        if not request.user.is_authenticated:
            return redirect(f"/accounts/login/?next=/join/{token}/")
        if not valid:
            return render(request, "workspaces/join.html", {"invalid": True}, status=410)
        Membership.objects.get_or_create(
            band=invite.band, user=request.user, defaults={"role": Membership.Role.MEMBER}
        )
        request.session.pop("pending_invite", None)
        messages.success(request, f"Welcome to {invite.band.name}!")
        return redirect(invite.band.owner.get_absolute_url())
    if not valid:
        return render(request, "workspaces/join.html", {"invalid": True}, status=410)
    if not request.user.is_authenticated:
        # Survive the signup/login round-trip even if ?next gets dropped.
        request.session["pending_invite"] = token
    already_member = (
        request.user.is_authenticated
        and Membership.objects.filter(band=invite.band, user=request.user).exists()
    )
    return render(
        request,
        "workspaces/join.html",
        {"invite": invite, "already_member": already_member},
    )


def content_page(request, owner_slug, content_slug):
    """Resolve /<owner>/<slug>/ — a song first, then a set."""
    from setlists.models import Set
    from setlists.services import can_view_set
    from setlists.views import set_detail
    from songs.models import Song
    from songs.services import can_view
    from songs.views import song_detail

    song = (
        Song.objects.select_related("owner")
        .filter(owner__slug=owner_slug, slug=content_slug)
        .first()
    )
    if song is not None:
        if not can_view(request.user, song):
            raise Http404
        return song_detail(request, song)
    setlist = (
        Set.objects.select_related("owner")
        .filter(owner__slug=owner_slug, slug=content_slug)
        .first()
    )
    if setlist is not None:
        if not can_view_set(request.user, setlist):
            raise Http404
        return set_detail(request, setlist)
    raise Http404
