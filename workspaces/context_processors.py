from .services import owners_for_user


def nav_owners(request):
    if not request.user.is_authenticated:
        return {}
    return {"nav_owners": owners_for_user(request.user)}
