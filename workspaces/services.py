"""Owner access helpers. Band membership arrives in M5; keeping these as
the single choke point means views/templates don't re-implement the rules.
"""

from __future__ import annotations

from django.db.models import Q, QuerySet

from .models import Owner


def owners_for_user(user) -> QuerySet[Owner]:
    """All owners the user can act for: their personal owner (+ bands later)."""
    if not user.is_authenticated:
        return Owner.objects.none()
    return Owner.objects.filter(Q(user=user)).order_by("kind", "slug")


def user_can_act_for(user, owner: Owner) -> bool:
    """Can the user create/edit content owned by this owner?"""
    if not user.is_authenticated:
        return False
    return owner.kind == Owner.Kind.USER and owner.user_id == user.id
