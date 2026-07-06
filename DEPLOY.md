# Deploying practicenotes to Fly.io

Everything deploy-shaped is already in the repo: `Dockerfile`,
`fly.toml` (app `practicenotes`, region `lhr`, volume at `/data`,
health check on `/health`), boot-time migrations (`scripts/start.sh`),
and a CI deploy job that activates once the `FLY_API_TOKEN` repo secret
exists. What's left needs your Fly account:

## One-time launch

```sh
# 1. Install flyctl and log in
curl -L https://fly.io/install.sh | sh
fly auth login

# 2. Create the app in your personal org (uses the committed fly.toml;
#    don't let it overwrite the config)
fly launch --copy-config --no-deploy --org personal

# 3. Volume for SQLite (single machine; fly launch may offer to create
#    one — if it didn't:)
fly volumes create practicenotes_data --region lhr --size 3

# 4. Tigris bucket for uploads (private). This injects AWS_* secrets
#    (endpoint, key, secret, bucket name) into the app automatically.
fly storage create --name practicenotes-media

# 5. App secrets
fly secrets set \
  SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(50))')"

# 6. First deploy
fly deploy
```

## Email (required for passkey signup)

Passkey signup uses email verification codes, so production needs SMTP:

```sh
fly secrets set EMAIL_HOST=smtp.example.com EMAIL_HOST_USER=... \
  EMAIL_HOST_PASSWORD=... DEFAULT_FROM_EMAIL="Practice Notes <hello@yourdomain>"
```

No SMTP provider yet? Disable passkey signup (password signup then works
without verification; passkey *login* still works for keys added later
under Security):

```sh
fly secrets set PASSKEY_SIGNUP_ENABLED=false
```

## CI deploys

Give GitHub Actions a deploy-scoped token; every push to `main` then
deploys automatically (the job is skipped while the secret is absent):

```sh
fly tokens create deploy --expiry 8760h | tr -d '\n' | gh secret set FLY_API_TOKEN
```

## Production smoke test

1. `curl https://practicenotes.fly.dev/health` → `{"status": "ok"}`
2. Sign up with username/password (check the verification code arrives),
   create a song, paste ChordPro, upload an mp3, play it back.
3. Uploads land in Tigris: `fly storage dashboard` — and playback URLs are
   presigned (querystring auth, ~5 min expiry).
4. Toggle a set public; open `https://practicenotes.fly.dev/<you>/<set>/`
   in a private window.
5. Data survives restarts: `fly machine restart` then confirm the song is
   still there.
6. Passkeys on a real device: sign up / log in with a passkey on a phone.

## Environment variables the app understands

| Variable | Default | Purpose |
|---|---|---|
| `DJANGO_DEBUG` | `true` | Set `false` in production (fly.toml does) |
| `SECRET_KEY` | — | Required when `DJANGO_DEBUG=false` |
| `ALLOWED_HOSTS` / `CSRF_TRUSTED_ORIGINS` | dev defaults | Comma-separated |
| `DATABASE_PATH` | `./db.sqlite3` | `/data/db.sqlite3` in production |
| `AWS_STORAGE_BUCKET_NAME` + `AWS_*` | unset → filesystem | Set by `fly storage create` |
| `PRESIGNED_URL_EXPIRY` | `300` | Seconds presigned URLs stay valid |
| `MAX_UPLOAD_BYTES` | `104857600` | Per-file upload cap |
| `PASSKEY_SIGNUP_ENABLED` | `true` | `false` relaxes email verification |
| `EMAIL_HOST` etc. | console backend | SMTP settings |
| `GUNICORN_WORKERS` / `GUNICORN_THREADS` | `2` / `4` | Serving concurrency |
