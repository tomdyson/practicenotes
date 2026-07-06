# Practice Notes

One place for a band's practice material. Collect lyrics, chord charts (ChordPro or freeform monospace), audio recordings, images, and PDFs per song; group songs into ordered sets; collaborate in band workspaces; share songs and sets at clean URLs like `/<owner>/<slug>`.

Django 5 + django-ninja (`/api/v1`), HTMX/Alpine/SortableJS, Tailwind v4 (standalone CLI, no Node), django-allauth with passkeys, SQLite (WAL), S3-compatible storage via django-storages, deployable on Fly.io + Tigris.

## Local development

```sh
uv sync
uv run python manage.py migrate
uv run python manage.py tailwind runserver   # dev server + CSS watcher
```

Configuration is environment-driven with optional `.env` support (see
`config/settings.py`); the defaults just work for development, with media
on the filesystem and emails printed to the console.

## Tests & linting

```sh
uv run pytest                # unit + integration
uv run pytest -m e2e         # Playwright end-to-end (needs: uv run playwright install chromium)
uv run ruff check . && uv run ruff format --check .
```

## Deploying

See [DEPLOY.md](DEPLOY.md). CI (GitHub Actions) lints, tests, runs the
browser suite, and deploys `main` to Fly once a `FLY_API_TOKEN` secret is
configured.

See [PLAN.md](PLAN.md) for the v1 plan and the [issues](../../issues) for the backlog.
