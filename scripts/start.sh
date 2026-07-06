#!/bin/sh
# Production entrypoint: migrate against the volume-mounted database, then
# serve. Migrations run here rather than in a Fly release_command because
# release machines don't mount volumes (see fly.toml).
set -e

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 120
