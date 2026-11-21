# Scaffolding a new project

Read this when the user wants a new project. `SKILL.md` has the conventions and the tools check; the references each step names hold the details — read them before doing that step.

## Layout

```
<project>/
├── backend/            Django (uv), project package "config", apps in apps/, locale/de, scripts/ (CI checks)
├── frontend/           Vue 3 or React + Vite + TypeScript (pnpm)
├── docs/               VitePress, docs/de + docs/en (optional)
├── docker/             supervisord, nginx, start-nginx, healthcheck, worker, smoke-test, exit-on-fatal
├── scripts/           sync_env.py (.env up to date with .env.example), check_changed.py (checks before a commit)
├── justfile            every command: dev, checks (= CI), API types, migrations, Docker
├── Dockerfile          SPA (+ docs) → python image: supervisord with nginx + gunicorn; also runs the worker
├── compose.yml         db (Postgres) + app + worker (hardened, image from ghcr.io); works with .env alone
├── compose.dev.yml     optional Postgres for running natively like CI
├── .github/            workflows (build, release), dependabot, issue forms, PR template, CODEOWNERS
├── .vscode/ .claude/   tasks calling just, extensions, launch.json
├── adr/                architecture decision records, with ADRs: yes (template + the decisions from step 1)
├── AGENTS.md, CLAUDE.md, README.md, CONTRIBUTING.md, SECURITY.md, CODE_OF_CONDUCT.md, BACKLOG.md
├── LICENSE (unless proprietary); with release-please also release-please-config.json, .release-please-manifest.json
└── .env.example, .gitignore, .gitattributes, .dockerignore, .editorconfig
```

Two ways to run it, and both must work:
- **Native development**: `just dev-backend` + `just dev-frontend` (VS Code: `Dev: start all`) → Django on :8000 with SQLite in `backend/data/`, Vite on the project's own `<DEV_PORT>` proxying `/api`, `/django-admin`, `/django-static`. No job worker: jobs run in-process after the commit, periodic jobs (backups) don't run. Optionally `just db-up` + `DB_HOST=localhost` to run on PostgreSQL like CI. `just check` runs exactly what CI runs.
- **Docker = production-like**: `docker compose up` runs Postgres, the app container (nginx + gunicorn) and the worker container from the same image; compose sets `DB_HOST=db` (so PostgreSQL and the job queue) and `DEBUG=false`. The Django admin lives under `/django-admin` (so `/admin` stays free for the SPA) and signs in through the app's login.

## Workflow

### 1. Settle the open decisions

Ask before scaffolding (AskUserQuestion if available, otherwise one short message), because these change the generated code:

- **Project name**, GitHub **owner** and target directory, if not given.
- **API library: Django Ninja or DRF** — never default silently. Ninja for mostly custom endpoints, typed contracts and async; DRF for lots of plain model CRUD (ViewSets), object permissions or DRF-ecosystem packages.
- **Frontend: Vue 3 or React**, then the **UI library**: a Tailwind-based one (shadcn-vue / shadcn/ui) for custom-looking apps with few data-heavy screens, a component suite (Naive UI / Mantine) for admin-style apps with many tables and forms.
- **License**: AGPL-3.0-or-later for public self-hosted apps (recommended there), MIT or Apache-2.0 where adoption matters, proprietary for internal and customer projects (`references/repo-files.md` section 2).
- **Docs**: VitePress (German + English) for apps with end users or operators; a small internal tool may make do with README + CONTRIBUTING.
- **Dev port** for Vite: free and project-specific (not 5173), so several projects run side by side.
- **Does the backend speak German?** Only when users see its texts directly (emails, generated documents, messages shown as they come). Otherwise it stays English and the frontend translates (`references/i18n.md`). The frontend always ships English and German.
- **Releases: release-please or by hand?** and **Contributions: external or team only (in development, no outside pull requests yet)?** Most people haven't seen release-please, Conventional Commits, the DCO or a Code of Conduct — show the short examples from `references/repo-files.md` section 4 with the question. The answers decide which files and blocks are kept and are recorded in AGENTS.md (`- Releases: …`, `- Contributions: …`).
- **ADRs?** Short records of decisions that are expensive to undo or would surprise someone later (why Ninja, why SQLite natively, why no HSTS). Recommend *yes* when the project will live for years or more than one person works on it, *no* for a small or short-lived tool. Show the example from `references/repo-files.md` section 4. Recorded as `- ADRs: yes` / `no`; no line means no ADRs.
- **arm64 image?** Only when it will run on ARM hosts (Raspberry Pi, ARM servers); it doubles the CI time. Default no.
- **Initial domain** (optional): named entities become apps and models; otherwise only `core` and `accounts`.
- **Time zone** for `TIME_ZONE` and the backup time, if not evident.

Fixed, not asked: SQLite natively without a worker; PostgreSQL with the job queue (procrastinate) and nightly backups by the worker in Docker, CI and production; a frontend in English and German; just; GitHub Actions with SHA-pinned actions, an image with provenance, Dependabot.

Unattended (nobody to answer): the recommended API and UI library for what you know of the project, Vue unless the request says React, AGPL if the repo is public and proprietary otherwise, docs yes, an English-only backend, release-please and external contributions for a public repo (by hand and team only otherwise), no arm64, no ADRs, a dev port of your choice — say what you chose and why at the top of the report, and continue.

### 2. Research current versions — every run

Never take version numbers from this skill, from memory or from an older project. Look up the newest stable releases now: Python packages (`uv add` resolves, PyPI for supported Django/Python versions, procrastinate included), npm packages (`pnpm view <pkg> version` / `engines`, pnpm itself, VitePress), Docker images (`python` slim, Node LTS, Postgres major, `ghcr.io/astral-sh/uv`), tools in the image (supervisor, `postgresql-client-<major>`), CI (every action in the workflows with its newest release tag **and that tag's commit SHA**, `aquasec/trivy`, `rust-just`, `actionlint-py`, `zizmor`), and image digests for every pinned image (ci.md section 2).

Then reconcile: the newest Python that the newest Django and every backend dependency support (with wheels for psycopg and argon2-cffi); the Node LTS that satisfies Vite's `engines`; an API library release that supports the chosen Django. No pre-releases. If a key dependency lags behind the newest Django, take the newest Django it supports and say so. Put a version table (component → version → why, if not the newest) in the report.

Lower bounds in `pyproject.toml` / `package.json` as the tools write them, lock files committed, Docker images pinned to the researched major (or major.minor) — plus digest in the Dockerfile and for images the workflows run, plain tags in the compose files — actions to commit SHAs. Dependabot keeps it current; ci.md section 1 lists what it doesn't see.

### 3. Backend

Read `references/backend.md` and `references/settings.md`. Generate with the current tools (`uv init`, `uv add`, `django-admin startproject config .`), then copy `assets/backend/` and **patch, don't replace** the generated `settings.py` and `urls.py` as settings.md lists. The rules that shape everything else:
- Apps in `backend/apps/<name>/` with packages instead of single files (`models/`, `admin/`, `api/`, `schemas/` or `serializers/`, `services/`, `tests/`), split by cohesion, not by count. Dependencies point one way (`api` → `services` → `selectors` → `models`, `core` imports no app), enforced by import-linter.
- Every model inherits `UUIDModel` or `TimeStampedModel` (UUIDv7); the `core.E001` check enforces it. `accounts.User` exists before the first migration.
- Business rules in `services/`; side effects deferred through `apps.core.jobs.defer`, never `task.defer()` directly.
- Session auth with CSRF, `/api/auth/…` without trailing slashes, `/api/health` unauthenticated.
- English source strings, German in `locale/de` (`references/i18n.md`).

### 4. Frontend

Read `references/frontend.md` (shared: pnpm, dev port and proxy, API client and generated types, `allValues`, auth flow, translations, tests), then `references/frontend-vue.md` or `references/frontend-react.md` for scaffolding, UI library, layout, data loading, state, i18n wiring, tests and lint setup.

### 5. Docker and environment

Read `references/docker.md`; copy `assets/Dockerfile`, `compose.yml`, `compose.dev.yml`, `docker/*`, `.env.example`, `.dockerignore`, `.gitignore`, `.gitattributes`, `.editorconfig`, `scripts/` (sync_env.py, check_changed.py), and fill the placeholders (researched versions and digests, project name, `<TIMEZONE>`). Keep the hardening of both containers — read-only root filesystem, no capabilities, unprivileged user, no setuid binaries, only `/data`, `/backups` (worker) and `/tmp` writable — supervisord as PID 1 of the app stopping it when a program keeps failing, and every runtime check in `docker/smoke-test`. `cp .env.example .env` so native verification works.

### 6. justfile, CI, releases and Dependabot

Read `references/ci.md`; copy `assets/justfile`, `assets/.github/workflows/`, `assets/.github/dependabot.yml`, the release-please files (with release-please), `assets/backend/scripts/`, `assets/backend/deploy-check.env` and `assets/frontend/scripts/`. CI only calls justfile recipes, so `just check` is CI. Every project gets the full set of gates (ci.md sections 1, 3 and 4), so the tooling config is part of the scaffold and the scaffold's own code is typed and tested enough to pass them. Pin every action to its commit SHA and every image to its digest (ci.md section 2).

### 7. Docs (if decided)

Read `references/docs.md` and copy `assets/docs/`; `<PNPM>` in `docs/package.json` is the frontend's `packageManager` value.

### 8. Repository files and README

Read `references/repo-files.md`: VS Code tasks, AGENTS.md, license, CONTRIBUTING (with external contributors: Conventional Commits, DCO), SECURITY, Code of Conduct (with external contributors), issue and PR templates, CODEOWNERS, BACKLOG and what the README covers. Then `git init -b main` and a first commit, if git is available.

### 9. Verify before you report

Set `<PLUGIN_VERSION>` and `<DATE>` in AGENTS.md's `## House defaults` section to the version at the top of `references/checklist.md` and today, and `<RELEASES>` / `<CONTRIBUTIONS>` / `<ADRS>` to the answers from step 1; a new project starts with no deviations.

```bash
bash <skill-dir>/scripts/verify_scaffold.sh <repo>            # leftovers, syntax, checklist (check_repo.py --new), `just check` (= CI)
bash <skill-dir>/scripts/verify_scaffold.sh <repo> --docker   # plus image build and docker/smoke-test app + worker
```

Fix whatever it reports until it passes (zizmor findings included). It needs `just` (`uv tool install rust-just`). Without Docker, say explicitly that the image was not tested; the arm64 image is only tested by CI.

### 10. Report

In the user's language (the code, comments and AGENTS.md stay English). Short: what was created (top two levels), the version table, the decisions from step 1, how to start (point to the README), the GitHub setup the user must do (ci.md section 6, branch protection first), and anything that couldn't be verified.

## Template markers

Assets contain `<PLACEHOLDER>`s and variant blocks marked `[NINJA]` / `[DRF]`, `[VUE]` / `[REACT]`, `[TAILWIND]`, `[RELEASE_PLEASE]` / `[MANUAL_RELEASES]`, `[EXTERNAL]` / `[TEAM_ONLY]`, `[BACKEND_DE]` / `[BACKEND_EN]`, `[ADRS]`, `[ARM64]`, `[DOCS]` / `[NO_DOCS]` (in Markdown as `<!-- [VUE] -->` … `<!-- [/] -->`). Keep the blocks that apply, delete the others with their markers. The verify script fails on any leftover placeholder or marker.
