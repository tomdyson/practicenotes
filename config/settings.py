"""
Django settings for practicenotes.

All deployment-specific configuration is environment-driven. Defaults suit
local development; production (Fly.io) sets DJANGO_DEBUG=false, SECRET_KEY,
ALLOWED_HOSTS, DATABASE_PATH and the S3/Tigris variables.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Minimal .env support: KEY=VALUE lines from BASE_DIR/.env become process
# environment defaults (real environment variables win). The file is
# gitignored; never commit secrets.
_env_file = BASE_DIR / ".env"
if _env_file.exists():
    for _line in _env_file.read_text().splitlines():
        _line = _line.strip()
        if not _line or _line.startswith("#") or "=" not in _line:
            continue
        _key, _, _value = _line.partition("=")
        os.environ.setdefault(_key.strip(), _value.strip().strip("'\""))


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    value = os.environ.get(name, default)
    return [item.strip() for item in value.split(",") if item.strip()]


DEBUG = env_bool("DJANGO_DEBUG", default=True)

SECRET_KEY = os.environ.get("SECRET_KEY", "")
if not SECRET_KEY:
    if DEBUG:
        SECRET_KEY = "dev-only-insecure-secret-key"
    else:
        raise RuntimeError("SECRET_KEY must be set when DJANGO_DEBUG is false")

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1" if DEBUG else "")
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS")

# Application definition

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "django_tailwind_cli",
    "accounts",
    "workspaces",
    "songs",
    "setlists",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Database: SQLite with WAL mode. Production mounts a volume at /data and
# sets DATABASE_PATH=/data/db.sqlite3.

DATABASE_PATH = os.environ.get("DATABASE_PATH", str(BASE_DIR / "db.sqlite3"))

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {
            "init_command": (
                "PRAGMA journal_mode=WAL;PRAGMA synchronous=NORMAL;PRAGMA busy_timeout=5000;"
            ),
            "transaction_mode": "IMMEDIATE",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

# Static files (whitenoise) and media (filesystem in dev, S3/Tigris in prod)

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "assets"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = Path(os.environ.get("MEDIA_ROOT", str(BASE_DIR / "media")))

# Set AWS_STORAGE_BUCKET_NAME (plus credentials/endpoint) to switch media
# storage to an S3-compatible bucket (Tigris in production). The bucket is
# private; files are served via short-lived presigned URLs.
AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "")

if AWS_STORAGE_BUCKET_NAME:
    _default_storage = {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "endpoint_url": os.environ.get("AWS_ENDPOINT_URL_S3", ""),
            "region_name": os.environ.get("AWS_REGION", "auto"),
            "default_acl": "private",
            "querystring_auth": True,
            "querystring_expire": int(os.environ.get("PRESIGNED_URL_EXPIRY", "300")),
            "file_overwrite": False,
        },
    }
else:
    _default_storage = {"BACKEND": "django.core.files.storage.FileSystemStorage"}

STORAGES = {
    "default": _default_storage,
    "staticfiles": {
        "BACKEND": (
            "whitenoise.storage.CompressedManifestStaticFilesStorage"
            if not DEBUG
            else "django.contrib.staticfiles.storage.StaticFilesStorage"
        ),
    },
}

# Uploads go through Django in v1; cap file size (bytes).
MAX_UPLOAD_BYTES = int(os.environ.get("MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# Tailwind CSS (django-tailwind-cli). Version pinned so builds are
# reproducible and no GitHub API call is needed to resolve "latest".
TAILWIND_CLI_VERSION = "4.1.11"
TAILWIND_CLI_SRC_CSS = BASE_DIR / "assets" / "css" / "source.css"
TAILWIND_CLI_DIST_CSS = "css/tailwind.css"
# Escape hatches for environments that cannot download the standalone
# binary from GitHub releases (e.g. sandboxes): point TAILWIND_CLI_PATH at
# an existing binary and disable the automatic download.
if os.environ.get("TAILWIND_CLI_PATH"):
    TAILWIND_CLI_PATH = os.environ["TAILWIND_CLI_PATH"]
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = env_bool("TAILWIND_CLI_AUTOMATIC_DOWNLOAD", default=True)

# Security hardening outside DEBUG.
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
