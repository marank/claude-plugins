# django-spa-defaults

One skill with one set of house defaults for web apps with a Django backend and a Vue 3 or React SPA that someone hosts themselves. It works in two modes:

- **New project** — asks the decisions that change the code (Ninja or DRF, Vue or React and a UI library, license, docs, releases, contributions, ADRs, …), researches the current versions of everything, scaffolds the repo and verifies that it passes its own checks.
- **Existing repo** — checks it against a versioned checklist with a deterministic script, so an unchanged repo gives the same result every time and "nothing to do" is a normal outcome. Deviations the project accepts are recorded in its `AGENTS.md` and not reported again.

It also explains its tools and checklist items on request ("what is zizmor?", "explain CI-09").

## What the defaults are

- **Django**: apps as packages split by cohesion, UUIDv7 primary keys, a custom case-insensitive user model, import boundaries, ruff and strict type checking, SQLite natively and PostgreSQL with a job queue in Docker.
- **Frontend**: Vue 3 or React with TypeScript, pnpm, API types generated from the OpenAPI schema, English and German.
- **Docker**: one hardened image (non-root, read-only, no capabilities) with nginx and gunicorn, a worker, a smoke test; no side effects beyond the app's own responses (no HSTS, no redirects — that is the reverse proxy's job).
- **CI**: GitHub Actions that only call `just` recipes, actions pinned by commit SHA, image scan, provenance, Dependabot with a cooldown; release-please if the project wants it.

Every checklist item names a goal; tools are examples with a recommendation, and a repo that reaches the goal with another tool passes. The full list is in [`references/checklist.md`](skills/django-spa-defaults/references/checklist.md).

## Requirements

[uv](https://docs.astral.sh/uv/) for the skill's scripts (it runs them with `uv run`). Scaffolding also needs Node, pnpm, [just](https://just.systems) and git; Docker only to test the image.

## Layout

```
skills/django-spa-defaults/
├── SKILL.md            what applies everywhere and which file to read for which task
├── references/         scaffold.md, review.md, checklist.md, tools.md and one file per area
├── assets/             the project's own template files
└── scripts/            check_repo.py (the checklist review), verify_scaffold.sh
```
