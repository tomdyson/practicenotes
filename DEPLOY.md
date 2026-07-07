# Deploying practicenotes

Production runs on a self-hosted [Coolify](https://coolify.io) instance
(`admin.co.tomd.org`), deployed from GitHub via Coolify's GitHub App
integration. Every push to `main` triggers a rebuild and deploy — there is
no deploy step in CI.

- **App**: `practicenotes` (project "Practice Notes", environment
  `production`, build pack `dockerfile`)
- **Domains**: <https://practice.tomd.org> (an A record in the
  Cloudflare-managed `tomd.org` zone, grey-clouded, pointing at the Coolify
  host) with `practicenotes.co.tomd.org` as a wildcard-DNS fallback. TLS via
  Traefik + Let's Encrypt.
- **Persistence**: one named Docker volume (`practicenotes-data`) mounted at
  `/data`, holding both the SQLite database (`/data/db.sqlite3`, WAL mode)
  and uploaded media (`/data/media`). Media is served through Django's
  `item_file` view, so every file request passes the `can_view` visibility
  check — no S3 needed. (The django-storages S3 branch still exists; set
  `AWS_STORAGE_BUCKET_NAME` etc. to switch.)
- **Migrations** run at container boot (`scripts/start.sh`), before gunicorn
  starts. Single container, single volume — no release-phase machinery.
- **Health**: `GET /health` touches the database, so it catches a broken
  volume mount as well as a dead app.

## Environment variables (set in Coolify)

| Variable | Production value | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `false` | Required in production |
| `SECRET_KEY` | (generated) | Required when `DJANGO_DEBUG=false` |
| `ALLOWED_HOSTS` | `practice.tomd.org,practicenotes.co.tomd.org` | Comma-separated |
| `CSRF_TRUSTED_ORIGINS` | `https://practice.tomd.org,https://practicenotes.co.tomd.org` | Comma-separated |
| `DATABASE_PATH` | `/data/db.sqlite3` | SQLite on the persistent volume |
| `MEDIA_ROOT` | `/data/media` | Uploads on the persistent volume |
| `PASSKEY_SIGNUP_ENABLED` | `true` | Signup verifies email by code |
| `EMAIL_HOST` | `smtp.resend.com` | Resend SMTP |
| `EMAIL_HOST_USER` | `resend` | Literal, per Resend's SMTP docs |
| `EMAIL_HOST_PASSWORD` | (Resend API key) | |
| `DEFAULT_FROM_EMAIL` | `Practice Notes <practice@go.naive.co.uk>` | Domain verified in Resend |

Other knobs the app understands (defaults are fine in production):
`PRESIGNED_URL_EXPIRY`, `MAX_UPLOAD_BYTES`, `GUNICORN_WORKERS`,
`GUNICORN_THREADS`, and the `AWS_*` set for S3-compatible media storage.

## Email

Transactional email (signup verification codes) goes out through Resend
SMTP from `practice@go.naive.co.uk` (domain verified in Resend, eu-west-1).
Delivery can be checked in the Resend dashboard or via its API. If SMTP is
ever removed, set `PASSKEY_SIGNUP_ENABLED=false` so password signup keeps
working without email verification.

## Day-to-day operations

Use the `coolify` CLI (context already configured):

```sh
coolify app logs s13zfmkttk2xpb8bbspcaayq -n 100   # runtime logs
coolify app restart s13zfmkttk2xpb8bbspcaayq        # restart (data survives)
coolify deploy uuid s13zfmkttk2xpb8bbspcaayq        # manual redeploy
coolify app env list s13zfmkttk2xpb8bbspcaayq       # inspect env keys
```

Or the Coolify UI: <https://admin.co.tomd.org>.

## Backups

Not yet configured. The SQLite database and media live in the
`practicenotes-data` volume on the Coolify host. Litestream (issue #13) or a
scheduled `sqlite3 .backup` + rsync off the host are the obvious options.

## Production smoke test

Automated on first deploy (2026-07-07), all passing:

1. `curl https://practice.tomd.org/health` → `{"status": "ok"}`
2. Sign up, create a song, paste ChordPro → chords align (monospace,
   `white-space: pre`, `[C]` above the right lyric column).
3. Upload audio → lands in `/data/media`, streams back through the
   `can_view`-gated file view.
4. Public set visible logged-out; private songs/sets/owner pages 404.
5. Container restart → database and uploads survive (volume + WAL).
6. Passkey signup with a real emailed verification code (Resend SMTP),
   then passkey login — via a CDP virtual authenticator against production.

Still outstanding: passkey login on a real phone (needs a real device).
