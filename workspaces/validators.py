from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from .reserved import RESERVED_SLUGS

validate_lowercase_slug = RegexValidator(
    r"^[a-z0-9](?:[a-z0-9-]*[a-z0-9])?$",
    "Use lowercase letters, numbers and hyphens (no leading/trailing hyphen).",
)


def validate_not_reserved(value: str):
    if value in RESERVED_SLUGS:
        raise ValidationError("This name is reserved.", code="reserved")
