"""Slugs that can never be claimed as an owner, song, or set slug.

The flat GitHub-style namespace at /<owner>/<slug> shares URL space with
application routes, so every top-level path prefix must be reserved here.
"""

RESERVED_SLUGS = [
    # Application routes
    "accounts",
    "admin",
    "api",
    "bands",
    "health",
    "invites",
    "join",
    "media",
    "sets",
    "songs",
    "static",
    # Common/likely future routes
    "about",
    "assets",
    "blog",
    "contact",
    "dashboard",
    "docs",
    "help",
    "login",
    "logout",
    "new",
    "notes",
    "practicenotes",
    "pricing",
    "privacy",
    "search",
    "settings",
    "signup",
    "support",
    "terms",
    "www",
]
