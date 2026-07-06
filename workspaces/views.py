from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Owner
from .services import owners_for_user, user_can_act_for


def home(request):
    if not request.user.is_authenticated:
        return render(request, "home.html")
    owners = owners_for_user(request.user)
    return render(request, "workspaces/dashboard.html", {"owners": owners})


def owner_page(request, owner_slug):
    owner = get_object_or_404(Owner, slug=owner_slug)
    # Owner pages are private in v1 (public profile pages are backlog #17):
    # strangers get a 404, not a 403, to avoid leaking namespace existence.
    if not user_can_act_for(request.user, owner):
        raise Http404
    return render(request, "workspaces/owner.html", {"owner": owner})
