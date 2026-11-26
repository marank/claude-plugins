# syntax=docker/dockerfile:1

# Versions in one place. Images are pinned by tag and digest (of the multi-platform
# index, so amd64 and arm64 builds use the same pin); Dependabot updates both.
ARG PG_MAJOR=<PG_MAJOR>
ARG SUPERVISOR_VERSION=<SUPERVISOR>

# uv installs the backend's packages and is not part of the image. Its own stage, so Dependabot
# sees the pin (it does not read `RUN --mount=from=<image>`).
FROM ghcr.io/astral-sh/uv:<UV>@<DIGEST> AS uv

# --- 1. Build the SPA ------------------------------------------------------------
FROM node:<NODE_LTS>-alpine@<DIGEST> AS frontend
WORKDIR /frontend
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
# pnpm in the version of packageManager in package.json (the one place it is set).
RUN npm install -g "$(node -p "require('./package.json').packageManager.split('+')[0]")" \
 && pnpm install --frozen-lockfile
COPY frontend/ ./
RUN pnpm run build

# [DOCS] --- 2. Build the documentation -------------------------------------------
FROM node:<NODE_LTS>-alpine@<DIGEST> AS docs
WORKDIR /docs
COPY docs/package.json docs/pnpm-lock.yaml docs/pnpm-workspace.yaml ./
RUN npm install -g "$(node -p "require('./package.json').packageManager.split('+')[0]")" \
 && pnpm install --frozen-lockfile
COPY docs/ ./
RUN pnpm build

# Further build stages of the project (kept outside the template comparison, DOCKER-12).
# --- project: build stages ---
# --- end ---

# --- 3. Runtime: supervisord → nginx + gunicorn/Django; the same image runs the worker -
# Named "runtime": CI builds it without cache (--no-cache-filter runtime), so system
# package updates are never held back.
FROM python:<PYTHON>-slim-<DEBIAN>@<DIGEST> AS runtime
ARG PG_MAJOR
ARG SUPERVISOR_VERSION

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    PATH="/opt/venv/bin:$PATH" \
    HOME=/tmp \
    DATA_DIR=/data \
    BACKUP_DIR=/backups
# --- project: environment ---
# --- end ---

# nginx; gettext-base for envsubst (start-nginx), gettext for compilemessages ([BACKEND_DE]);
# postgresql-client from PostgreSQL's own repository in the server's major, so pg_dump
# (nightly backups) accepts the server. curl only for the key and removed again.
# supervisord lives outside the app's venv: it's infrastructure, not an app dependency.
# pip is not needed at runtime, so it goes afterwards (one package less for the scanner).
# setuid/setgid bits are removed; nothing in the container may gain privileges.
RUN apt-get update \
 && apt-get upgrade -y \
 && apt-get install -y --no-install-recommends nginx gettext-base gettext curl ca-certificates \
 && curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc -o /usr/share/keyrings/pgdg.asc \
 && echo "deb [signed-by=/usr/share/keyrings/pgdg.asc] https://apt.postgresql.org/pub/repos/apt <DEBIAN>-pgdg main" \
      > /etc/apt/sources.list.d/pgdg.list \
 && apt-get update \
 && apt-get install -y --no-install-recommends "postgresql-client-${PG_MAJOR}" \
 && apt-get purge -y curl && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled /etc/nginx/conf.d \
 && pip install --no-cache-dir --root-user-action=ignore "supervisor==${SUPERVISOR_VERSION}" \
 && pip uninstall -y --root-user-action=ignore pip \
 && groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --no-create-home --shell /usr/sbin/nologin app \
 && install -d -o app -g app -m 0700 /data /backups \
 && find / -xdev -perm /6000 -type f -exec chmod a-s {} +

# Further system packages of the project (kept outside the template comparison, DOCKER-12).
# --- project: system packages ---
# --- end ---

WORKDIR /app
COPY backend/pyproject.toml backend/uv.lock ./
RUN --mount=from=uv,source=/uv,target=/usr/local/bin/uv \
    --mount=type=cache,target=/tmp/.cache/uv \
    uv sync --frozen --no-dev --no-install-project
COPY backend/ ./
# The app's own modules too: the root filesystem is read-only at runtime, so Python could not
# cache them there. collectstatic needs settings to import; a throwaway key is enough at build time.
RUN python -m compileall -q config apps \
 && SECRET_KEY="build-only-$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')" DB_PASSWORD=unused \
    sh -c 'python manage.py collectstatic --noinput && python manage.py compilemessages --ignore=.venv'

COPY --from=frontend /frontend/dist /srv/spa
# [DOCS]
COPY --from=docs /docs/.vitepress/dist /srv/docs
# [/]
# Further files the project copies into the runtime stage (outside the comparison, DOCKER-12).
# --- project: copy into runtime ---
# --- end ---
COPY docker/nginx.conf docker/django_proxy.conf docker/security_headers.conf /etc/nginx/
COPY docker/app.conf.template /etc/nginx/app.conf.template
# [WSGI]
COPY docker/supervisord.conf docker/gunicorn.conf.py /etc/
# [/WSGI]
# [ASGI]
COPY docker/supervisord.conf /etc/supervisord.conf
# [/ASGI]
COPY docker/entrypoint.sh docker/start-nginx docker/exit-on-fatal docker/healthcheck docker/smoke-test docker/worker /usr/local/bin/

# Everything above is owned by root and read-only for "app"; only /data, /backups and /tmp are written.
USER app
EXPOSE 8080
VOLUME ["/data", "/backups"]
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s \
  CMD ["python", "/usr/local/bin/healthcheck"]
# entrypoint.sh: deploy checks, migrate, first admin, then supervisord. CMD, not ENTRYPOINT: the
# worker service replaces it with its own command.
CMD ["sh", "/usr/local/bin/entrypoint.sh"]
