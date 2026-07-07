#!/bin/sh
# Production entrypoint: migrate against the volume-mounted database, then
# serve. Migrations run at boot so they always see the persistent volume
# (/data), whatever platform runs the container.
set -e

python manage.py migrate --noinput

exec gunicorn config.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers "${GUNICORN_WORKERS:-2}" \
    --threads "${GUNICORN_THREADS:-4}" \
    --timeout 120
