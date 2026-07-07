# Handoff: build practicenotes v1 (cloud session)

> **Historical note (2026-07-07):** this brief is complete — v1 was built,
> merged, and deployed (to Coolify rather than the Fly.io setup described
> below; see [DEPLOY.md](DEPLOY.md)). Kept for the record.

You are picking up a fully planned greenfield project, running in a cloud sandbox with a fresh clone of this repo. Your job is to build all of v1 autonomously, milestone by milestone, as far as the environment allows. Everything has already been decided with Tom — do not re-litigate decisions; build.

## Context

- You are in a cloud environment. There is no local machine state: everything you need is this repo (https://github.com/tomdyson/practicenotes, public), its GitHub issues, and this file. Everything you produce must end up pushed to the repo — it is your only durable state, and the session may end at any time.
- **Read `PLAN.md` first.** It is the source of truth: product decisions, stack, data model, ChordPro approach, milestones M0–M8, and verification requirements. This handoff tells you *how to work*; PLAN.md tells you *what to build*.
- The backlog is GitHub issues: **#1–#9 are milestones M0–M8** (label `milestone`), **#10–#19 are post-v1** (label `backlog`). Do **not** build backlog items.

## What you're building

A web app where musicians gather all practice material for a song in one place — lyrics/guides, chord charts (ChordPro or freeform monospace), audio recordings, images, PDFs — group songs into ordered **sets**, collaborate in **band workspaces**, and share songs/sets at `https://host/<owner>/<slug>` where an owner is a user or a band (GitHub-style flat namespace).

## Preflight (do this before M0)

1. Check what the sandbox gives you: Python version, `git`, `gh auth status`, network egress. Install what's missing as you need it — `uv` (`curl -LsSf https://astral.sh/uv/install.sh | sh`), Playwright + headless Chromium for e2e, flyctl only when you reach M8.
2. Confirm you can push: make M0's first commit early and push it before building further.
3. Check whether `FLY_API_TOKEN` is set in the environment — it decides which M8 end state you can reach (see M8).
4. Test the PR flow once: if `gh` can't create PRs with the credentials available, fall back to committing directly to main with `Closes #<issue>` in the commit message (this closes issues on push to the default branch). Note the fallback in your final report.

## How to work

1. **One milestone at a time, in order M0 → M8.** Preferred flow per milestone: branch `m<N>-<short-slug>`, implement, test, open a PR whose body includes `Closes #<issue>`, wait for CI green (`gh pr checks --watch`), squash-merge, pull main, continue. M0 (which creates the CI workflow) can go directly to main. **Push after every green milestone at minimum** — never hold hours of unpushed work in the sandbox.
2. **Quality bar per milestone:** `ruff check` and `ruff format --check` clean; `pytest` green locally and in CI. Write the tests PLAN.md's Verification section names: ChordPro parser golden tests, `can_view` permission matrix, slug collision + reserved-word validation, invite link flows (expiry/revocation), set ordering.
3. **End-to-end browser verification after M3 and M6**, headless Playwright against the dev server (there is no real browser or human in this environment): sign up, create a song, paste ChordPro and check chord/lyric alignment in the render, upload an mp3 and an image, play audio at 0.75×, reorder items, build a set, toggle public, open `/<owner>/<slug>` in a logged-out context, confirm private content 404s for strangers. Use **username/password auth** for automated flows. Optionally exercise passkey signup/login with Playwright's WebAuthn virtual authenticator (CDP); real-device passkey testing stays with Tom either way — say so in your final report.
4. **Never commit secrets** — the repo is public. Env-driven settings; `.env` is gitignored. Don't echo tokens from the environment into files, logs, or CI config.
5. If something in PLAN.md proves wrong or infeasible, make the smallest sensible deviation, record it in the PR description, and keep moving. If the sandbox blocks something (no egress to a host, missing capability), work around it, stub it cleanly, or defer it with a note — don't stall the whole build.

## Key constraints (condensed — PLAN.md has the detail)

- Django 5.x + django-ninja (`/api/v1`); server-rendered templates + HTMX + Alpine (SortableJS for drag-reorder); Tailwind v4 via `django-tailwind-cli` (standalone binary, no Node — it downloads the binary on first run); uv for deps; ruff + pytest.
- Apps: `accounts`, `workspaces`, `songs`, `setlists`; project config in `config/`. Data model (Owner/Band/Membership/BandInvite/Song/Item/Set/SetSong) is specified in PLAN.md — follow it.
- Auth: django-allauth, passkey signup + login primary, username/password fallback. **Check current allauth docs (WebFetch) for the exact WebAuthn/passkey settings** — don't trust memory, the flag names have churned.
- Storage: django-storages S3 backend, private bucket, short-lived presigned URLs for playback/view; uploads go through Django (cap ~100 MB). Dev/tests: filesystem storage backend (keep the code backend-agnostic).
- SQLite with WAL mode; prod DB at `/data/db.sqlite3`.
- Fonts self-hosted as woff2 in static (download from Fontsource or google-webfonts-helper): **Karla** body, **Gowun Batang** H1/H2 only, **JetBrains Mono** for code/chords. If font downloads are blocked from the sandbox, ship a system-font fallback stack and file an issue to swap in the real fonts.
- Styling — Tom's signature look, described here because his local skill isn't available in the cloud: warm beige background with subtle diagonal stripes, indigo as the primary colour, soft rounded cards on the beige ground, generous whitespace, Gowun Batang serif headings. Body font is **Karla** (his signature look normally uses Inter — use Karla for this project).
- Monetisation-safe: no one-band-per-user assumptions; per-owner counts must stay derivable by query.

## M8 specifics (deploy — degrade gracefully)

Check for `FLY_API_TOKEN` in the environment. flyctl reads it automatically once installed (`curl -L https://fly.io/install.sh | sh`).

**With the token:** Fly app `practicenotes`, Tom's personal org, region `lhr` (Tom is UK-based). Volume mounted at `/data`. `fly storage create` for the Tigris bucket (injects AWS-style env vars as secrets). Django `SECRET_KEY`, `ALLOWED_HOSTS`/CSRF origins etc. via `fly secrets`. Gunicorn + whitenoise; a `/health` endpoint for Fly checks; run migrations on release/boot. For CI deploys, try `gh secret set FLY_API_TOKEN` (a deploy-scoped token from `fly tokens create deploy`); if the GitHub credentials can't set repo secrets, add the workflow anyway and tell Tom to set the secret himself.

**Without the token:** build everything deploy-shaped into the repo — Dockerfile, `fly.toml`, health endpoint, release-phase migrations, the CI deploy job (gated on the `FLY_API_TOKEN` secret existing) — and end with the exact commands Tom must run (`fly launch` / volume / `fly storage create` / secrets / `gh secret set`). Do not guess or invent credentials.

## Definition of done

Two acceptable end states:

- **Deployed** (token available): issues #1–#9 closed, CI green on main, app live at `https://practicenotes.fly.dev`, production smoke test passed — password signup, create song with ChordPro item, upload an mp3 (lands in Tigris, plays back via presigned URL), public share link works logged out, SQLite data survives `fly machine restart`.
- **Deploy-ready** (no token): issues #1–#8 closed, CI green, all M8 configuration in-repo, and a precise runbook for Tom in the final report.

Either way, finish with a report to Tom: production URL or deploy runbook, what he must test manually (passkey signup/login on a real device), any deviations from PLAN.md and why, which environment fallbacks you used (PR flow, fonts, e2e), and suggested next backlog picks.
