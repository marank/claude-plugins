---
name: "django-spa-defaults"
description: Scaffold a new Django project with a Vue or React SPA using the house defaults, or check an existing repo against them and bring it in line - Django (UUIDv7 keys, split apps, Ninja or DRF, SQLite natively, PostgreSQL + job queue in Docker), Vue 3 or React with TypeScript, pnpm and OpenAPI-generated types, English + German, one hardened multi-platform Docker image, justfile, GitHub Actions CI with pinned actions, Dependabot, optional release-please, license per project, optional VitePress docs. Researches current versions on every run and explains its tools and checklist items on request. Use it whenever the user wants to start, set up, bootstrap or scaffold a web app, repo or project with Django, Vue or React, asks for "my project defaults", "our standard" or "our stack", or wants such a repo checked against these conventions - even if they only mention one part (just the Django API, the SPA, the Docker or the CI setup).
---

# Django + Vue/React project defaults

How every project of this stack looks: new ones are scaffolded this way, existing ones are brought in line. The goal is a repo that runs on the first try — natively, in Docker and in its own CI — whose rules are enforced by checks rather than only written down: no monolithic files, UUIDs everywhere, one `.env` that drives everything, hardened by default, bilingual from the start, no database server needed for everyday development.

## What to read

This file holds what applies everywhere. Load only what the request needs:
- **New project** → `references/scaffold.md` (layout, the ten steps, template markers); it names the further references per step.
- **Existing repo** → `references/review.md` (the checklist review); never scaffold over an existing repo.
- **A question about a tool or checklist item** → `references/tools.md` and the item's row in `references/checklist.md`.

**Explaining.** When the user asks what a tool or checklist item is or why it is used ("what is zizmor?", "why just?", "explain CI-09"), answer from `references/tools.md` and the item's row in `references/checklist.md`: what it does, what it does for us, when an alternative fits better. No mode or argument needed. In every report and question, a tool gets a half-sentence of explanation the first time it is named, e.g. "zizmor (finds security problems in the GitHub workflows)".

**Tools first, in both modes.** Before anything else run `uv --version` (scaffolding also needs `node`, `pnpm`, `just`, `git`; Docker only for the image) and name what's missing in one line. Python always comes from uv: run the skill's scripts with `uv run --no-project --python ">=3.11" <skill-dir>/scripts/<script>.py …` — never `python3`, `python` or `py`, which are missing or too old on many machines (Windows, macOS) and differ between them. Without uv, give the install command (`curl -LsSf https://astral.sh/uv/install.sh | sh`; Windows: `powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"`; or `brew install uv`) and wait until it's there — the checklist can't be evaluated by reading alone.

## Where these defaults fit — and where they don't

They are made for **web apps with a Django backend and an SPA that someone hosts themselves**. Say so when a request falls outside, and adapt only with the user's agreement:

- **Session auth on the same origin.** Right for a browser SPA served with the API. Not for mobile apps or third-party API clients — they need token auth (and then CORS), which this skill doesn't set up.
- **One image, app + worker on one host with `docker compose`.** Ideal for a single server. For Kubernetes or horizontal scaling, nginx and gunicorn would be split as well and the manifests are a project of their own.
- **SQLite natively, PostgreSQL in production.** Code must work on both, so no PostgreSQL-only fields or lookups (`ArrayField`, `distinct(<fields>)`, …). A project that needs them gives up native SQLite — record that in AGENTS.md.
- **Backend plus SPA.** A pure API without a frontend, a frontend without Django, a library or a CLI tool get only the repo-level parts (AGENTS.md, CONTRIBUTING, tasks = CI, Dependabot, license gate, `.editorconfig`); the rest doesn't apply.
- **Frontend in English and German, backend English unless users see its texts.** Further languages on request.

## Conventions everywhere

- **Templates only for our own conventions.** What a framework or scaffolder generates is generated fresh and patched; our own files come from `assets/`, with their tool flags checked against the installed versions.
- **No monolithic files, no artificial fragments.** Split by responsibility and cohesion, never to meet a size. Limits apply to tangle — cyclomatic complexity ≤ 15, nesting ≤ 4, import boundaries — never to length (no `max-lines`, no statement limits). `settings.py` stays one file; env parsing lives in `config/env.py`.
- **Readable by intent.** Comments say why; no commented-out code; one word per domain concept (AGENTS.md glossary); with `- ADRs: yes` in AGENTS.md, a decision someone might question gets an ADR — propose one when such a decision comes up; without that line the project keeps none, so don't bring ADRs up.
- **`.env` is the single source of configuration**; every new variable gets a commented entry in `.env.example` (and a row in the docs' configuration page).
- **Same origin** for SPA and API (nginx in Docker, Vite proxy natively): no CORS, session cookies and CSRF just work.
- **No side effects beyond our own responses.** The app never changes how clients or other services treat the host or domain: no HSTS, no http → https redirect, no cookies for a parent domain, no service worker unless the project decides so explicitly. TLS, redirects and HSTS are the reverse proxy's job. When reviewing an existing repo, flag such settings as deviations rather than recommending them.
- **Checks over prose.** When a rule matters, make a check, test or lint rule enforce it, as a justfile recipe that `just check` and CI run.
- **Pinned supply chain.** Actions by commit SHA, the Dockerfile's base images by digest (compose files keep plain tags, as operators expect), lock files committed, Dependabot to move them; least-privilege workflow permissions.
- **Community standards** scaled to the project: README, LICENSE, CONTRIBUTING, SECURITY, issue and PR templates always; Conventional Commits with release-please, and Code of Conduct with DCO, as the project decides (asked once, recorded in AGENTS.md).
- **The checklist stays out of the project's history.** Its version, item IDs and this skill appear only in AGENTS.md's `## House defaults` section — never in commit messages, PR titles or descriptions, changelogs, code comments or ADRs. Those describe the change itself.
- **No names from other projects.** Everything project-specific comes from this project's name and decisions.
- English for code, comments, `.env.example`, AGENTS.md and CONTRIBUTING.md; the README may follow the user's language. Reports and questions to the user are in the user's language.

