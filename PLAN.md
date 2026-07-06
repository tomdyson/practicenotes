# Practice Notes — v1 Implementation Plan

## Context

Collaborators send practice/session material as a mess of voice notes, WhatsApps, photos of chord sheets, Drive links, and Google Docs. **practicenotes** (working title) is a web app that gathers everything for a song in one place — text (lyrics/guides), chord charts, audio, images, PDFs — groups songs into ordered, named **sets**, and shares them at clean URLs.

### Decisions

| Area | Decision |
|---|---|
| Chords | Both formats: **ChordPro** (parsed, chords rendered above lyrics, transposable later) and **freeform monospace** (pasted charts rendered as-is), per-item format flag |
| Collaboration | **Band workspaces** — bands own content alongside personal content |
| Namespaces | **GitHub-style owners**: one flat namespace where an owner is a user *or* a band → `host/tom/wichita-lineman`, `host/quiet-ones/june-gigs` |
| Roles | Owner + members (members add/edit content; owner manages membership and band) |
| Invites | Revocable, optionally-expiring **invite links** |
| File types | Audio (mp3/m4a/wav/ogg) + images (inline) + PDFs (in-browser) |
| Auth | **WebAuthn passkeys primary**, username/password fallback |
| Deploy | **Fly.io** (SQLite on a volume) + **Tigris** (S3-compatible) via django-storages |
| Process | Public GitHub repo; GitHub Actions CI (lint + test on push/PR, deploy to Fly on main); backlog as GitHub issues |
| Monetisation | Free for all initially; keep per-owner counts queryable and avoid design choices that block plan limits later |

## Stack

- **Django 5.x** + **django-ninja** (`/api/v1`, session auth for now, OpenAPI docs for free)
- Server-rendered templates + **HTMX** (inline edits, reordering) + **Alpine** (audio player, small interactions); **SortableJS** for drag-reorder
- **Tailwind v4** via `django-tailwind-cli` (standalone binary — no Node in dev or Docker)
- **django-allauth** with WebAuthn: passkey signup + login, username/password fallback
- **django-storages[s3]** → Tigris; private bucket; playback/downloads via short-lived presigned URLs; uploads through Django in v1 (direct-to-S3 presigned uploads → backlog)
- **SQLite** (WAL mode) on a Fly volume
- **uv** for dependency management; **ruff** (lint + format); **pytest** + pytest-django
- Fonts self-hosted as woff2 in static: **Karla** (body), **Gowun Batang** (H1/H2 only), **JetBrains Mono** (code/chords)
- Dockerfile (python-slim + uv), gunicorn, whitenoise for static

## Data model

Apps: `accounts`, `workspaces`, `songs`, `setlists` (project config in `config/`).

```
Owner            slug (unique, validated vs reserved-word list), kind: user|band
                 one-to-one → User (personal) XOR Band. Created on signup /
                 band creation; enforces the flat username↔band namespace.

Band             name, created_by; Owner row created alongside
Membership       band FK, user FK, role: owner|member, unique(band, user)
BandInvite       band FK, token (random slug), created_by, expires_at?, revoked_at?

Song             owner FK, title, slug (unique per owner), visibility: private|public,
                 created_by, timestamps
Item             song FK, position, kind: text|audio|image|pdf, optional title,
                 — text: body + format: plain|chordpro|monospace
                 — file: FileField, original filename, content_type, size
                 (single table → one mixed ordering of text and files per song)

Set              owner FK, name, slug (unique per owner), description?, visibility
SetSong          set FK, song FK, position (M2M through — a song can be in many sets)
```

- **URL scheme**: `/<owner>/<slug>` resolves song first, then set (slug uniqueness across both models per owner enforced at validation time). Catch-all route registered last; reserved slugs (`admin`, `api`, `accounts`, `static`, `media`, `bands`, `health`, …) blocked at Owner/Song/Set validation.
- **Visibility rule**: an item's files/text are viewable if its song is public, **or** any public set contains the song, **or** the viewer is the owner / a band member. Presigned URL issuance gates on the same check (single `can_view(user, song)` service function).
- **Monetisation-safe**: no one-band-per-user assumptions; counts (songs per owner, sets per owner, storage bytes) derivable by query; entitlements can later hang off Owner.

## ChordPro rendering

Small custom parser module `songs/chordpro.py` (~100 lines + tests), no dependency:

- Chord tokens `[Am7]`, common directives (`{title}`, `{artist}`, `{comment}`, `{start_of_chorus}`/`{end_of_chorus}`), tolerant of unknown directives
- Renders paired chord-line/lyric-line HTML in JetBrains Mono; transposition is a backlog issue (parser keeps chords structured to enable it)
- `monospace` format items render escaped in `<pre>`-style mono; `plain` renders as prose

## Milestones (each = a GitHub issue; PRs reference them)

**M0 — Scaffold & repo.** uv project; Django + config split (env-driven settings); ruff, pytest wired; Tailwind + base template with fonts; Dockerfile; CI workflow (lint + test); labels + milestone/backlog issues.

**M1 — Auth & owners.** allauth with passkey signup/login + password fallback; username registers Owner slug; login/signup pages styled; owner home page listing songs/sets.

**M2 — Songs & text items.** Song CRUD; text items (plain/ChordPro/monospace) authored or pasted in-app; ChordPro parser + renderer; item ordering (SortableJS + HTMX endpoint); optional titles.

**M3 — Files & storage.** Upload audio/images/PDFs (multiple per song) through Django to Tigris (local: MinIO or filesystem backend); presigned playback/view URLs; audio player (HTML5 + Alpine speed control 0.5–1.5×); inline images; PDF embed. Per-file size cap (~100 MB) enforced.

**M4 — Sets.** Set CRUD; add/remove/reorder songs (drag); set page rendering songs in order with their materials.

**M5 — Bands.** Create band (claims Owner slug); invite links (create/revoke/expire, join flow through signup); membership list; owner-vs-member permissions; band-owned songs/sets; band switcher in nav.

**M6 — Sharing.** Visibility toggles on songs and sets; public pages at `/<owner>/<slug>` for logged-out visitors; `can_view` gating everywhere incl. presigned URLs; copy-link UI.

**M7 — API.** django-ninja `/api/v1`: auth'd CRUD for songs/sets/items/uploads mirroring the service layer the views already use; OpenAPI docs at `/api/v1/docs`.

**M8 — Deploy.** `fly launch` config: volume for `/data/db.sqlite3` (WAL), Tigris bucket + secrets, health check; CI deploy job on main with `FLY_API_TOKEN`; smoke-test production.

## Backlog (filed as issues, not v1)

Chord transposition; waveform + A-B loop practice player (wavesurfer.js); direct-to-S3 presigned uploads; Litestream SQLite backup to Tigris; API tokens for mobile app; plan limits / billing; admin role tier + email invites; public owner profile pages; full-text search; audio derived formats (normalise/transcode).

## Verification

- **Per-milestone**: pytest suite (models, permissions/`can_view`, ChordPro parser golden tests, slug collision/reserved-word validation, invite flows) + ruff, locally and in CI.
- **End-to-end after M3 and M6**: sign up, create song, paste ChordPro and verify rendered chord alignment, upload an mp3 and an image, play audio at 0.75×, reorder items, build a set, toggle public, open `/<owner>/<slug>` logged out, confirm private content 404s for strangers.
- **M8**: deploy, then repeat the logged-out share-link check against the Fly URL; confirm SQLite persists across machine restarts and files land in Tigris.
