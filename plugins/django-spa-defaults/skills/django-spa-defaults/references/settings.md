# Patching the generated settings.py and urls.py

`django-admin startproject config .` writes `settings.py` and `urls.py` for the Django version that was just installed. Keep those files and change only what is listed here. Everything else Django generated stays: new defaults, new middleware or new settings of a future release are exactly what we'd lose with a template.

Before patching, skim the release notes of the installed Django version for removed or renamed settings that the snippets below use (in particular the CSP middleware/setting names and the default `PASSWORD_HASHERS` list — copy the fallbacks from the installed version's docs). If one of them changed, follow the release notes and keep the intent described here.

The helpers come from `assets/backend/config/env.py` (copy it to `config/env.py` first).

## Contents
1. Imports and .env loading
2. Security block (replaces SECRET_KEY / DEBUG / ALLOWED_HOSTS)
3. Apps and user model
4. Database (replaces DATABASES; PostgreSQL with DB_HOST, SQLite natively)
4a. Job queue and backups
4b. Test settings
5. I18N values (English + German)
6. Static, media and data directory
7. Logging
8. API-library additions
9. urls.py

## 1. Imports and .env loading

At the top, after the generated `from pathlib import Path` and `BASE_DIR`:

```python
from .env import env_bool, env_int, env_list, env_str, load_dotenv, parse_app_urls, secret_key

load_dotenv(BASE_DIR.parent / ".env", BASE_DIR / ".env")  # native dev; real env vars win
```

## 2. Security block

Delete the generated `SECRET_KEY`, `DEBUG` and `ALLOWED_HOSTS` lines (including the generated insecure key — it must not end up in git) and put this in their place:

```python
DEBUG = env_bool("DEBUG", False)
SECRET_KEY = secret_key(DEBUG)  # >= 40 chars, else refuse to start (DEBUG: fixed dev key)

APP_URLS = parse_app_urls(env_list("APP_URLS", ["http://localhost:8080"]))
if DEBUG:
    # Vite dev server and runserver, so native development needs no extra config.
    APP_URLS += parse_app_urls(["http://localhost:<DEV_PORT>", "http://127.0.0.1:<DEV_PORT>", "http://localhost:8000"])

ALLOWED_HOSTS = sorted({url.hostname for url in APP_URLS})
CSRF_TRUSTED_ORIGINS = sorted({url.origin for url in APP_URLS})

# Secure cookies only once every public URL is https (i.e. a TLS proxy is in front).
_ALL_HTTPS = not DEBUG and all(url.scheme == "https" for url in APP_URLS)
SESSION_COOKIE_SECURE = _ALL_HTTPS
CSRF_COOKIE_SECURE = _ALL_HTTPS
if _ALL_HTTPS:
    # nginx always sets X-Forwarded-Proto itself and takes it over only from
    # TRUSTED_PROXIES; Django is reachable only through nginx.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# No side effects beyond our own responses: TLS, the http -> https redirect and HSTS belong
# to the reverse proxy in front. HSTS changes how browsers treat the whole host (for a year,
# for every app on it) and a permanent redirect is cached by them, so the app sets neither;
# the deploy check's warnings about them are silenced on purpose.
SECURE_SSL_REDIRECT = False
SECURE_HSTS_SECONDS = 0
SILENCED_SYSTEM_CHECKS = ["security.W004", "security.W008"]  # HSTS, SSL redirect: the proxy's job
# Cookies stay host-only: never set SESSION_COOKIE_DOMAIN / CSRF_COOKIE_DOMAIN to a parent domain.

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False  # the SPA reads csrftoken to send X-CSRFToken
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"

# Content Security Policy for Django's own responses (admin, API). The SPA's CSP is
# set by nginx (docker/security_headers.conf). Built into Django since 6.0; add
# "django.middleware.csp.ContentSecurityPolicyMiddleware" to MIDDLEWARE right after
# SecurityMiddleware. (Put `from django.utils.csp import CSP` with the other imports.)

SECURE_CSP = {
    "default-src": [CSP.SELF],
    "img-src": [CSP.SELF, "data:"],
    "object-src": [CSP.NONE],
    "base-uri": [CSP.SELF],
    "frame-ancestors": [CSP.NONE],
}

# Argon2 first (Django's recommendation; needs the "argon2" extra: uv add "django[argon2]"),
# the generated defaults stay as fallbacks so existing hashes keep working.
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
    "django.contrib.auth.hashers.ScryptPasswordHasher",
]

```

Same origin everywhere (nginx / Vite proxy), so no CORS settings or package.

With https `APP_URLS` this block makes `manage.py check --deploy --fail-level WARNING` pass, which CI requires. The health endpoint must be exactly `/api/health` (no trailing slash) to match the redirect exemption and the `healthcheck` script.

## 3. Apps and user model

Append to the generated `INSTALLED_APPS` (keep Django's contrib apps as generated):

```python
    "apps.core",
    "apps.accounts",
    # "apps.<feature>", ...
```

Add below it:

```python
AUTH_USER_MODEL = "accounts.User"
```

Leave `DEFAULT_AUTO_FIELD` as generated — it only affects third-party models; ours set a UUID pk explicitly and the `core.E001` check enforces it.

## 4. Database

Replace the generated `DATABASES`:

PostgreSQL when `DB_HOST` is set — in Docker (compose sets it), in CI and in production. Natively, without `DB_HOST`, a SQLite file in `DATA_DIR`: no database server to start, and no job worker (section 4a). This needs `DATA_DIR` from section 6, so put the database block after it or move the `DATA_DIR` lines up.

```python
if env_str("DB_HOST", ""):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env_str("DB_NAME", "<project>"),
            "USER": env_str("DB_USER", "<project>"),
            "PASSWORD": env_str("DB_PASSWORD"),  # required with PostgreSQL: no default
            "HOST": env_str("DB_HOST"),
            "PORT": env_str("DB_PORT", "5432"),
            "CONN_MAX_AGE": env_int("DB_CONN_MAX_AGE", 60),
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    # Native development and the local tests. Only the dev settings may end up here:
    # production always runs with DB_HOST (compose.yml sets it).
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATABASES = {"default": {"ENGINE": "django.db.backends.sqlite3", "NAME": DATA_DIR / "db.sqlite3"}}
```

Write code that works on both: no PostgreSQL-only lookups or fields (`ArrayField`, `JSONField` key transforms beyond what SQLite supports, `distinct(<fields>)`) unless the project decides to give up SQLite — then say so in AGENTS.md. CI runs the tests against PostgreSQL, so a difference shows up there at the latest.

## 4a. Job queue and backups

The queue (procrastinate) lives in PostgreSQL, so it only exists there. Django 6 has its own tasks API (`django.tasks`, with an in-process backend for development); switch to it once a production backend matches what procrastinate gives us here (retries, periodic jobs, queueing locks, a worker) — `apps.core.jobs.defer` is the one place that would change.



```python
# Background jobs (apps/core/tasks.py, deferred through apps.core.jobs.defer): with
# PostgreSQL a procrastinate queue in the database, worked off by the worker. SQLite has
# no queue: jobs then run in-process right after the transaction commits.
JOB_QUEUE = DATABASES["default"]["ENGINE"] == "django.db.backends.postgresql"
if JOB_QUEUE:
    INSTALLED_APPS.append("procrastinate.contrib.django")
```

The tasks live in `apps/core/tasks.py` (asset; procrastinate discovers every app's `tasks.py`), and services defer them only through `apps.core.jobs.defer(task, **kwargs)` (asset), never with `task.defer()` directly — `defer` picks the queue or the in-process run. In Docker the worker is its own compose service from the same image (`docker/worker`). Natively there is no worker; periodic jobs (the nightly backup, cleanup) simply don't run there. Whoever runs natively against PostgreSQL (`compose.dev.yml`) starts `uv run python manage.py procrastinate worker` by hand if they need jobs.

```python
# Nightly pg_dump and an archive of the uploads (MEDIA_ROOT) by the worker container
# (apps/core/services/backups.py) into BACKUP_DIR, the "backups" volume in the image
# (/backups). Empty switches the nightly backup off.
BACKUP_DIR = env_str("BACKUP_DIR", "")
# Time of day in TIME_ZONE. Not between 02:00 and 03:00: daylight saving time skips
# that hour once a year (no backup) and repeats it once (two backups).
BACKUP_TIME = time.fromisoformat(env_str("BACKUP_TIME", "01:30"))
BACKUP_KEEP_DAYS = env_int("BACKUP_KEEP_DAYS", 14)
```

(`from datetime import time` with the other imports.) Side effects of a request — mails, webhooks, anything slow — are deferred as jobs inside the transaction that causes them, never run in the request.

## 4b. Test settings

`config/settings_test.py`, used by pytest (`DJANGO_SETTINGS_MODULE` in `pyproject.toml`) and django-stubs, so tests don't depend on what is in a developer's `.env`:

```python
"""Settings for the tests: the development settings with a fast password hasher."""

import os

os.environ.setdefault("DEBUG", "true")  # set before .env is read, so .env cannot turn it off

from .settings import *  # noqa: E402, F403  (SQLite natively, PostgreSQL via DB_HOST in CI)

# Argon2 is deliberately slow; the tests hash many passwords.
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
BACKUP_DIR = ""
```

## 5. I18N values

Replace only the values of the generated `LANGUAGE_CODE` and `TIME_ZONE`:

```python
LANGUAGE_CODE = env_str("LANGUAGE_CODE", "en-us")
TIME_ZONE = env_str("TIME_ZONE", "UTC")
```

Only if the backend speaks German (step 1, `i18n.md`): set the default `LANGUAGE_CODE` to the project's main language, add `LANGUAGES` with the offered languages, `LOCALE_PATHS = [BASE_DIR / "locale"]`, and `django.middleware.locale.LocaleMiddleware` after `SessionMiddleware`. An English-only backend keeps `LANGUAGE_CODE = "en-us"` and nothing else.

## 6. Static, media and data directory

Replace the generated `STATIC_URL` and add the rest:

```python
# Admin assets only; the SPA is served by nginx / Vite. Not "/static/" so it can't
# collide with SPA paths.
STATIC_URL = "/django-static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# The only writable location in the container (read_only rootfs). Natively: backend/data.
DATA_DIR = Path(env_str("DATA_DIR", str(BASE_DIR / "data")))
MEDIA_ROOT = DATA_DIR / "media"
MEDIA_URL = "/media/"
```

Add `backend/data/` to `.gitignore`. Anything the app writes at runtime (uploads, exports, caches on disk) goes below `DATA_DIR` — the container's root filesystem is read-only.

## 7. Logging

Append:

```python
LOG_LEVEL = env_str("LOG_LEVEL", "INFO").upper()
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"default": {"format": "{asctime} {levelname} {name}: {message}", "style": "{"}},
    "handlers": {"console": {"class": "logging.StreamHandler", "formatter": "default"}},
    "root": {"handlers": ["console"], "level": LOG_LEVEL},
    "loggers": {"django": {"handlers": ["console"], "level": LOG_LEVEL, "propagate": False}},
}
```

## 8. API-library additions

- **Ninja**: nothing in settings.
- **DRF**: add `"rest_framework"` and `"drf_spectacular"` to `INSTALLED_APPS` and the `REST_FRAMEWORK` / `SPECTACULAR_SETTINGS` blocks from backend.md section 6.

## 9. urls.py

First the switch in `settings.py` (next to `DEBUG`): the Django admin is off unless an operator turns it on, so a stock install exposes no extra login surface (SEC-08).

```python
# The Django admin at /django-admin (staff users). Off by default.
ADMIN_ENABLED = env_bool("ADMIN_ENABLED", False)
```

Then replace the generated `urlpatterns` (keep the generated docstring if you like):

```python
from django.conf import settings
from django.contrib import admin
from django.urls import path

from .api import urlpatterns as api_urlpatterns  # everything under /api/

urlpatterns = [*api_urlpatterns]
if settings.ADMIN_ENABLED:
    # The Django admin lives under /django-admin, so /admin stays free for the SPA's own administration.
    urlpatterns.insert(0, path("django-admin/", admin.site.urls))
```

Without `ADMIN_ENABLED` `/django-admin/…` answers 404 (nginx forwards it, Django has no such route); `django.contrib.admin` stays in `INSTALLED_APPS`, so the models' `admin/` modules and the static files keep working. The admin keeps Django's own login page; a project that adds a second factor or single sign-on makes the admin use it through that package's own admin integration (django-allauth, django-otp, …).


After patching, `uv run python manage.py check` must pass, with `ADMIN_ENABLED=true` the admin login redirect must work and the admin pages must render without CSP violations (check in a browser once if possible; otherwise switch `SECURE_CSP` to `SECURE_CSP_REPORT_ONLY` and say so) and `grep -n "django-insecure" config/settings.py` must find nothing.
