"""Owner access helpers — the single choke point for "who can act for whom",
so views/templates don't re-implement the rules.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import Band, Membership, Owner


def owners_for_user(user) -> QuerySet[Owner]:
    """All owners the user can act for: their personal owner + their bands."""
    if not user.is_authenticated:
        return Owner.objects.none()
    return (
        Owner.objects.filter(Q(user=user) | Q(band__memberships__user=user))
        .select_related("user", "band")
        .distinct()
        .order_by("kind", "slug")
    )


def user_can_act_for(user, owner: Owner) -> bool:
    """Can the user create/edit content owned by this owner?"""
    if not user.is_authenticated:
        return False
    if owner.kind == Owner.Kind.USER:
        return owner.user_id == user.id
    return Membership.objects.filter(band_id=owner.band_id, user=user).exists()


def user_is_band_owner(user, band: Band) -> bool:
    """Band owners manage membership, invites and band settings."""
    if not user.is_authenticated:
        return False
    return Membership.objects.filter(band=band, user=user, role=Membership.Role.OWNER).exists()
