# Handoff: build practicenotes v1

You are picking up a fully planned greenfield project. Your job is to build all of v1 autonomously, milestone by milestone, until the app is live in production. Everything has already been decided with Tom — do not re-litigate decisions; build.

## Context

- Working directory: `~/Documents/code/python/practicenotes` — a git repo tracking https://github.com/tomdyson/practicenotes (public), currently containing only planning docs.
- **Read `PLAN.md` first.** It is the source of truth: product decisions, stack, data model, ChordPro approach, milestones M0–M8, and verification requirements. This handoff tells you *how to work*; PLAN.md tells you *what to build*.
- The backlog is GitHub issues: **#1–#9 are milestones M0–M8** (label `milestone`), **#10–#19 are post-v1** (label `backlog`). Do **not** build backlog items.

## What you're building

A web app where musicians gather all practice material for a song in one place — lyrics/guides, chord charts (ChordPro or freeform monospace), audio recordings, images, PDFs — group songs into ordered **sets**, collaborate in **band workspaces**, and share songs/sets at `https://host/<owner>/<slug>` where an owner is a user or a band (GitHub-style flat namespace).

## How to work

1. **One milestone at a time, in order M0 → M8.** For each: branch `m<N>-<short-slug>`, implement, test, open a PR whose body includes `Closes #<issue>`, wait for CI green (`gh pr checks --watch`), squash-merge, pull main, continue. M0 (which creates the CI workflow) can be committed directly to main.
2. **Quality bar per milestone:** `ruff check` and `ruff format --check` clean; `pytest` green locally and in CI. Write the tests PLAN.md's Verification section names: ChordPro parser golden tests, `can_view` permission matrix, slug collision + reserved-word validation, invite link flows (expiry/revocation), set ordering.
3. **End-to-end browser verification after M3 and M6** (use the playwright skill against the dev server): sign up, create a song, paste ChordPro and check chord/lyric alignment in the render, upload an mp3 and an image, play audio at 0.75×, reorder items, build a set, toggle public, open `/<owner>/<slug>` in a logged-out context, confirm private content 404s for strangers. Use **username/password auth** for automated flows — passkeys need a human; leave passkey signup/login for Tom to test manually and say so in your final report.
4. **Never commit secrets** — the repo is public. Env-driven settings; `.env` is gitignored.
5. If something in PLAN.md proves wrong or infeasible, make the smallest sensible deviation, record it in the PR description, and keep moving. Only stop for genuine blockers requiring Tom (billing/account actions, destructive operations).

## Key constraints (condensed — PLAN.md has the detail)

- Django 5.x + django-ninja (`/api/v1`); server-rendered templates + HTMX + Alpine (SortableJS for drag-reorder); Tailwind v4 via `django-tailwind-cli` (no Node); uv for deps; ruff + pytest.
- Apps: `accounts`, `workspaces`, `songs`, `setlists`; project config in `config/`. Data model (Owner/Band/Membership/BandInvite/Song/Item/Set/SetSong) is specified in PLAN.md — follow it.
- Auth: django-allauth, passkey signup + login primary, username/password fallback. **Check current allauth docs (WebFetch) for the exact WebAuthn/passkey settings** — don't trust memory, the flag names have churned.
- Storage: django-storages S3 backend, private bucket, short-lived presigned URLs for playback/view; uploads go through Django (cap ~100 MB). Local dev: filesystem storage backend (keep the code backend-agnostic).
- SQLite with WAL mode; prod DB at `/data/db.sqlite3`.
- Fonts self-hosted as woff2 in static (download via google-webfonts-helper or Fontsource): **Karla** body, **Gowun Batang** H1/H2 only, **JetBrains Mono** for code/chords.
- Styling: apply the `signature-look` skill (warm beige stripes, indigo primary, soft rounded cards, Gowun Batang headings) **but with Karla as the body font instead of Inter**.
- Monetisation-safe: no one-band-per-user assumptions; per-owner counts must stay derivable by query.

## Environment

- `gh` is authenticated as `tomdyson`. `uv` is installed. Verify `fly auth whoami` before M8; if flyctl is missing or logged out, flag it to Tom rather than guessing credentials.
- Relevant skills: `deploy-to-fly` (use it for M8), `signature-look` (styling), `playwright-skill` (e2e), `verify` (before committing nontrivial changes).

## M8 specifics

- Fly app `practicenotes`, Tom's personal org, region `lhr` (Tom is UK-based). Volume mounted at `/data`. `fly storage create` for the Tigris bucket (injects AWS-style env vars). Django `SECRET_KEY`, `ALLOWED_HOSTS`/CSRF origins etc. via `fly secrets`.
- CI deploy: `fly tokens create deploy` → `gh secret set FLY_API_TOKEN`; deploy job runs on pushes to main only, after lint+test pass.
- Gunicorn + whitenoise; a `/health` endpoint for Fly checks; run migrations on release/boot.

## Definition of done

- Issues #1–#9 closed via merged PRs; CI green on main.
- App live at `https://practicenotes.fly.dev`; production smoke test passed: password signup, create song with ChordPro item, upload an mp3 (lands in Tigris, plays back via presigned URL), public share link works logged out, SQLite data survives `fly machine restart`.
- Final report to Tom: production URL, what he must test manually (passkey signup/login on the real domain), any deviations from PLAN.md and why, and suggested next backlog picks.
