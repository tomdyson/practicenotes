from allauth.account.adapter import DefaultAccountAdapter
from django.core.exceptions import ValidationError

from workspaces.models import Owner


class AccountAdapter(DefaultAccountAdapter):
    def clean_username(self, username, shallow=False):
        username = super().clean_username(username, shallow=shallow)
        # The username claims a slot in the flat owner namespace, which is
        # shared with band names — the User table alone can't see those.
        if Owner.objects.filter(slug=username.lower()).exists():
            raise ValidationError("This username is already taken.")
        return username
