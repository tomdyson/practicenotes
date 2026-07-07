from django.core.validators import RegexValidator

# Usernames double as Owner slugs in the flat /<owner>/ namespace, so they
# follow slug rules. Case is not preserved (ACCOUNT_PRESERVE_USERNAME_CASING).
username_validators = [
    RegexValidator(
        r"^[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?$",
        "Usernames may only contain letters, numbers and hyphens (no leading/trailing hyphen).",
    ),
]
