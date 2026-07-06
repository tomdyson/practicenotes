from ninja import Router, Schema

from .models import Owner
from .services import owners_for_user

router = Router(tags=["owners"])


class OwnerOut(Schema):
    slug: str
    kind: str
    display_name: str

    @staticmethod
    def resolve_display_name(obj: Owner) -> str:
        return obj.display_name


@router.get("/owners", response=list[OwnerOut])
def list_owners(request):
    return owners_for_user(request.user)
