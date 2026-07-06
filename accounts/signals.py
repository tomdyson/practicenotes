import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db.models.signals import post_save
from django.dispatch import receiver

from workspaces.models import Owner

logger = logging.getLogger(__name__)


@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_owner_for_user(sender, instance, created, **kwargs):
    if not created:
        return
    owner = Owner(slug=instance.username.lower(), kind=Owner.Kind.USER, user=instance)
    try:
        owner.full_clean()
    except ValidationError:
        # e.g. a superuser created with a reserved or non-slug username;
        # the account works but owns no namespace.
        logger.warning("No owner namespace created for username %r", instance.username)
    else:
        owner.save()
