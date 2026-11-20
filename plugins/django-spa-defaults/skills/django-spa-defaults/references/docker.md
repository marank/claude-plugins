# Docker reference

## Files (copy from `assets/`)

| File | Purpose |
|------|---------|
| `Dockerfile` | Stage `frontend` builds the SPA with Node + pnpm; stage `docs` (only with docs) builds VitePress; stage `runtime` is `python:<ver>-slim-<debian>` + nginx + supervisord + `postgresql-client-<PG_MAJOR>` (PGDG), backend deps via `uv sync --frozen`, runs as user `app` (uid 10001), setuid bits stripped. Every `FROM` and the uv image are pinned by tag + digest of the multi-platform index, so the amd64 and arm64 builds use the same pin |
| `compose.yml` | `db` (Postgres, healthcheck, volume), `app` (image from ghcr.io, hardened via the `x-hardened` anchor, volume on `/data`, port `APP_BIND`, default 8080) and `worker` (same image, `docker/worker`, hardened, `init: true`, volumes on `/data` and `/backups`, health check `procrastinate healthchecks`). Works with `.env` alone — no other file from the repo is mounted |
| `compose.dev.yml` | optional Postgres, port bound to 127.0.0.1, to run natively against the same database as CI (`just db-up` + `DB_HOST=localhost`); natively the default is SQLite |
| `docker/healthcheck` | probe with the right Host header (Docker `HEALTHCHECK`, smoke test); no curl in the image |
| `docker/smoke-test` | the one smoke test, run inside the containers by CI (both platforms) and by `verify_scaffold.sh --docker`: `app` — SPA, static files, API, admin redirecting to the app login, supervisord programs running; `worker` — worker running, a backup; both — nothing as root, read-only rootfs, writable `/data`. New probes go here, nowhere else |
| `docker/worker` | the worker container's command: waits until the app has migrated, then `exec procrastinate worker` (`WORKER_CONCURRENCY`, default 4) |
| `docker/security_headers.conf` | CSP, nosniff, frame, referrer, permissions and COOP headers for what nginx serves itself |
| `docker/supervisord.conf` | PID 1 of the app container; runs gunicorn (after `check --deploy`, `migrate`, `ensure_admin`) and nginx; `exit-on-fatal` listener |
| `docker/exit-on-fatal` | stops supervisord when a program goes FATAL → container exits → restart policy |
| `docker/start-nginx` | renders `app.conf.template` into `/tmp/nginx/` from env, `nginx -t`, then `exec nginx` |
| `docker/nginx.conf` | main config for an unprivileged nginx: pid/temp paths in `/tmp/nginx`, logs to stdout/stderr |
| `docker/django_proxy.conf` | proxy headers shared by `/api/`, `/api/auth/login` and `/django-admin` |
| `docker/app.conf.template` | `/api/` → Django, `/django-admin` → Django, `/django-static/`, `/docs/` (with docs), SPA with `index.html` fallback |
| `.env.example`, `.dockerignore`, `.gitignore`, `.editorconfig` | as named |
| `.gitattributes` | LF for every text file on every platform; without it a Windows clone with `core.autocrlf` builds CRLF scripts into the image and `sh` fails on them |

These files are our own conventions, so they're templates. They still depend on tools whose options drift (gunicorn flags, supervisord sections, nginx directives, procrastinate's worker and healthchecks commands). After filling them in, check each flag against the current docs of the version the image installs, and fix the template in the generated repo if something was renamed or removed.

## Placeholders to fill with researched values

- `<PG_MAJOR>` — newest Postgres major (alpine variant); also the `postgresql-client-<PG_MAJOR>` in the image, so `pg_dump` accepts the server.
- `<NODE_LTS>` — newest Node LTS that satisfies Vite's `engines`.
- `<PYTHON>` — the Python version chosen for the backend (major.minor); `<DEBIAN>` — the Debian codename of the `python:<ver>-slim-*` images (also used for the PGDG apt line).
- `<UV>` — newest `ghcr.io/astral-sh/uv` tag; `<SUPERVISOR>` — newest supervisor release on PyPI.
- `@<DIGEST>` after each image — the digest of that tag's multi-platform index (`docker buildx imagetools inspect <image>:<tag>`). Dependabot bumps tag and digest together; the weekly CI rebuild still applies Debian's package updates in the runtime stage (`apt-get upgrade`).
- `<project>` / `<Project>` — project name (compose `name`, DB defaults, `.env.example` text); `<owner>` — the GitHub owner, for the image `ghcr.io/<owner>/<project>`. The container user stays `app` in every project.

pnpm is installed in the version of `packageManager` in `frontend/package.json` (read with `node -p`), so that field is the only place the pnpm version lives. Not through corepack: Node 25 and newer no longer ship it (CI-09). Commit `frontend/pnpm-workspace.yaml` (pnpm keeps settings like allowed build scripts there); the Dockerfile copies it.

Postgres data directory: from 18 on, the official image stores data in `/var/lib/postgresql/<major>/docker` and expects the volume on `/var/lib/postgresql` (what the template does). On 17 or older it's `/var/lib/postgresql/data`. Verify against the image docs for the major you picked.

## How the pieces fit

```
browser ──► [TLS proxy] ──► app:8080 nginx ──┬─ /api/*, /django-admin* ──► 127.0.0.1:8000 gunicorn (Django)
                                             ├─ /django-static/ ─► /app/staticfiles
                                             ├─ /docs/          ─► /srv/docs (VitePress, optional)
                                             └─ everything else ─► /srv/spa (index.html fallback)
app, worker ──► db:5432 Postgres (data + job queue)
worker: procrastinate worker (jobs, nightly pg_dump → /backups)
writable: /data (volume, DATA_DIR, both), /backups (volume, BACKUP_DIR, worker), /tmp (tmpfs)
```

- **Hardening.** Root filesystem read-only, no capabilities, no privilege escalation, unprivileged user, no setuid binaries. Consequences that every change must respect: nginx listens on 8080 (no `CAP_NET_BIND_SERVICE`), all runtime files (pid, sockets, nginx temp, rendered config, gunicorn heartbeat) live in `/tmp`, app data goes to `DATA_DIR=/data`, dumps to `/backups`, bytecode is compiled at build time (`UV_COMPILE_BYTECODE`), static files and `.mo` files are built at build time. If a new feature needs to write somewhere else, point it at `/data` or `/tmp` instead of loosening the compose settings.
- **One image, two containers.** In `app`, supervisord runs gunicorn and nginx — they belong together (nginx only fronts this gunicorn); a program that keeps failing stops the container (exit-on-fatal), so the restart policy brings up a fresh one instead of a half-working app. The job worker is its own `worker` service from the same image: own logs, own restarts, own health check, scalable on its own — Docker's "one concern per container".
- **TRUSTED_PROXIES.** nginx's realip module rewrites the client address from `X-Forwarded-For` only when the peer is listed; `X-Forwarded-Proto` is taken over only from listed peers too (`geo` + `map`). nginx always sets `X-Forwarded-Proto` and `X-Real-IP` towards Django, so clients can't spoof them, which is what makes `SECURE_PROXY_SSL_HEADER` safe and the gunicorn access log trustworthy. Neither nginx nor Django sends HSTS or redirects http to https: TLS, redirects and HSTS change how clients treat the whole host and belong to the reverse proxy in front (settings.md section 2 silences the deploy check's warnings about them).
- **APP_URLS with https** switches on secure cookies in Django, so it needs a TLS proxy in front (and TRUSTED_PROXIES).
- **Login rate limit.** `limit_req` on exactly `/api/auth/login`, 10 requests/minute per client IP with a burst of 5, answered with 429. The key is the real client address after the realip evaluation, so behind a TLS proxy TRUSTED_PROXIES must be set or every user shares one bucket.
- **Security headers.** nginx sets CSP and friends for the SPA, docs, assets and static files (`security_headers.conf`, included per location because `add_header` isn't inherited once a location has its own). Django sets its own CSP for `/api` and `/django-admin` (settings.md). If the app needs a third-party origin (fonts, analytics, maps), extend the CSP there deliberately instead of loosening `default-src`; better, bundle the asset (e.g. fonts via `@fontsource`).
- **Backups.** The worker container runs `pg_dump --format=custom` every night at `BACKUP_TIME` (in `TIME_ZONE`) into the `backups` volume and deletes dumps older than `BACKUP_KEEP_DAYS` (`apps/core/services/backups.py`, `apps/core/tasks.py`). `docker compose exec worker python manage.py backup_database` dumps right away (before an update). Dumps on the same host are not a backup against losing the host — the README tells the user to copy them off (`docker compose cp worker:/backups ./backups`, or point their host backup at the volume) and how to restore (`pg_restore --clean --if-exists` into the `db` container).
- **Django admin** lives under `/django-admin` so that `/admin` belongs to the SPA (the app's own administration pages). It has no login page of its own: it redirects to the app's login, so there is one sign-in for everything (including a second factor if the app adds one), and only staff users get in.

## Extending

- Uploaded media: `MEDIA_ROOT` is already under `/data`. Serve public media with a `location /media/ { alias /data/media/; }`, protected files through Django with `X-Accel-Redirect` and an `internal` location.
- More background work: another task in `apps/<app>/tasks.py`, deferred from a service. Periodic jobs with `@app.periodic(cron=…)` — procrastinate's cron is UTC, so for local times run hourly and check the hour like the backup task does.
- Live updates (SSE/WebSockets): an ASGI server (uvicorn) as a third supervisord program in `app`, nginx routes the endpoint to it. Add a probe to `docker/smoke-test`.

## Verification

`scripts/verify_scaffold.sh <repo> --docker` (in the skill) builds the image locally, starts the stack with a throwaway SECRET_KEY/passwords, runs `docker/smoke-test app` and `worker` inside the two containers (the same script as CI; only the local platform), then `docker compose down -v`. Without a daemon, `docker compose config -q` (also part of the script) is the most that can be checked — say so in the report.

## Where the job worker runs

Two ways, both fine (checklist DOCKER-08):
- **Its own compose service from the same image** (`worker`, the default in the assets): own logs, restarts, health check and resources; can be scaled or moved on its own. Better when jobs are heavy or long-running, when there are several kinds of workers, or when an orchestrator runs the containers. NetBox, for instance, runs web and worker from one image with the role chosen by the command.
- **Its own supervisord program in the app container**: one container to run and update. Fine for small single-host installs with light jobs; Weblate and Paperless-ngx ship this way. Then `[program:worker]` in `supervisord.conf` runs `docker/worker`'s command (wait for migrations, `exec` the worker), the `worker` service and its `backups` volume move into `app`, and the smoke test checks the program instead of a second container.

Side note: a reverse proxy that runs as a container on the same host is best attached through a shared Docker network instead of the published port.
