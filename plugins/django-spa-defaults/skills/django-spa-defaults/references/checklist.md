# House defaults checklist

Version: 1.0.1 — the plugin's version (`django-spa-defaults`). A repo records the version it was last checked against in AGENTS.md.

The norm for **existing repositories**: a repo meets the house defaults when every item below either passes or is listed as an accepted deviation in the repo's `AGENTS.md`. Only these items produce findings. The other references describe *how* to build things for a new project; when reviewing they are a lookup for fixing an item, never a source of extra findings.

- **Level**: `must` — security, data integrity, or a check that keeps CI honest; `should` — the house way, worth aligning when cheap.
- **Scope**: `all` — checked in every repo; `new` — set up for new projects only, not reported for existing ones (retrofitting costs more than it brings).
- **How**: `auto` — `scripts/check_repo.py` decides, the same way on every run; `judge` — decided by reading the code against the stated criterion and nothing more. Items that depend on a project decision report `ask` until AGENTS.md records it.

Items name the goal, not one way to reach it: where equally good alternatives exist, each of them passes, and the item says which one fits when. **Tools** gives examples: the recommended one in bold (new projects get it), after `·` alternatives that pass as well. A repo that already reaches the goal with an alternative keeps it — switching tools is never a finding. A tool the script doesn't know fails the item once; recording `- ID: met with <tool>` in AGENTS.md settles it.

Each item is one decision, so accepting it can't hide an unrelated problem. Item IDs never change meaning. A rule that gets stricter or different gets a new ID; one that only widens (more ways to pass, nothing that passed fails now) keeps its ID and is named as widened in the changelog. A dropped rule is marked "retired". A changelog line lists new items first and retired ones after the word "retired".

## Repository

| ID | Level | Scope | How | Rule | Tools |
|---|---|---|---|---|---|
| REPO-01 | must | all | auto | `AGENTS.md` exists; `CLAUDE.md` exists and points to it. | — |
| REPO-02 | should | all | auto | `README.md` and `CONTRIBUTING.md` exist; `LICENSE` exists unless the project is proprietary (`"UNLICENSED"` in `frontend/package.json`). | — |
| REPO-03 | must | all | auto | A task runner with a `check` target holds the check commands, and the CI workflows run checks only through it. | **just** · make, Task, mise tasks |
| REPO-10 | must | all | auto | The `check` targets cover lint, formatting, types, the migrations check, Django's system checks, API schema drift and the backend tests (`check-backend`), and lint, formatting, types, tests, API types drift and the build (`check-frontend`). Decided by the script for a justfile; with another task runner `judge`. | **ruff, mypy, pytest; ESLint, Prettier, vue-tsc/tsc, Vitest** · the alternatives named at BE-07, BE-08, FE-04 |
| REPO-11 | should | all | auto | The checks also catch unused or missing dependencies, copyleft licenses in production dependencies and a growing frontend bundle (with whatever tools fit; the defaults are deptry, the license scripts and size-limit). | **deptry, the license scripts from the template, size-limit** · fawltydeps; pip-licenses, license-checker; bundlewatch |
| REPO-05 | must | all | auto | Every environment variable the app reads at runtime (settings, apps) has an entry in `.env.example`. Variables of CI and tooling scripts (`CI`, `GITHUB_*`) don't belong there. | — |
| REPO-06 | must | all | auto | Lock files are committed, one package manager per part (backend, frontend): exactly one lock file in each. | **uv; pnpm** · poetry, pdm; npm, yarn, bun |
| REPO-07 | should | all | auto | `.editorconfig` exists; `.gitignore` ignores `.env`. | — |
| REPO-13 | should | all | auto | Releases as recorded in AGENTS.md (`- Releases: release-please` or `by hand`): with release-please, its config, manifest and workflow exist. Not recorded yet → recorded from what the repo shows, asked only otherwise (`repo-files.md` section 4). | **release-please** · by hand (tag + GitHub release) |
| REPO-14 | should | all | auto | Contributions as recorded in AGENTS.md (`- Contributions: external` or `team only`): with external contributors, `CODE_OF_CONDUCT.md` exists and CONTRIBUTING.md asks for the DCO sign-off. Not recorded yet → recorded from what the repo shows, asked only otherwise. | **DCO GitHub App** for the sign-off check |
| REPO-15 | should | all | auto | CONTRIBUTING.md follows the template: sections Issues, Pull requests, License with the template's wording, in the mode recorded in AGENTS.md — external (pull requests welcome) or team only (in active development: an IMPORTANT note that pull requests are not accepted for now). | — |
| REPO-16 | should | all | auto | The README has a `## Contributing` section in the template's words for the recorded mode (team only: pull requests are not accepted yet; external: pull requests are welcome) that points to CONTRIBUTING.md. | — |
| REPO-17 | should | all | auto | With release-please and no release yet (manifest at `0.0.0`), the first release is `0.1.0` (`"initial-version": "0.1.0"`); release-please would otherwise open it as `1.0.0`. | **release-please** |
| REPO-18 | should | all | auto | ADRs as recorded in AGENTS.md (`- ADRs: yes` or `no`); no line means no ADRs and nothing to check. With yes, `adr/` exists with its template. An `adr/` folder without the line is recorded as yes, without asking. | **the skill's template (Nygard/MADR style)** · adr-tools, MADR |
| REPO-12 | should | all | auto | `SECURITY.md` says how to report a vulnerability privately. | **GitHub private vulnerability reporting** · a security mail address |

## Backend

| ID | Level | Scope | How | Rule | Tools |
|---|---|---|---|---|---|
| BE-01 | should | all | auto | Apps live in `backend/apps/<name>/`; an app with models has a `models/` package, not `models.py`. | — |
| BE-02 | must | all | auto | A custom user model (`AUTH_USER_MODEL`) exists. | — |
| BE-03 | must | all | auto | Primary keys are UUIDs, enforced by a system check (`E001` in `apps/core/checks.py`). | — |
| BE-04 | must | all | auto | Usernames are case-insensitive: a `Lower("username")` unique constraint, and no exact `username=` lookups outside tests. | — |
| BE-05 | must | all | auto | Settings read the environment only through one module, whose boolean parser rejects invalid values. | **`config/env.py` from the template** (no dependency) · pydantic-settings (django-environ does not pass: it reads invalid booleans as false) |
| BE-06 | should | all | auto | Import boundaries between layers and apps are configured, and every app is in them. | **import-linter** · tach |
| BE-07 | should | all | auto | A linter selects at least ruff's `E F I UP B DJ SIM C90 DTZ T20 ERA S` (or the same checks elsewhere); no length rules (`PLR0915`) are selected. | **ruff** · flake8 with plugins (then judged by hand) |
| BE-08 | must | all | auto | A type checker runs in strict mode with Django types. | **mypy + django-stubs** · pyright or basedpyright in strict mode + django-types |
| BE-09 | should | all | auto | Backend coverage `fail_under` is at least 90. | **coverage.py via pytest-cov** |
| BE-10 | should | all | auto | SQLite without `DB_HOST`, PostgreSQL with it. | — |
| BE-11 | must | all | judge | `DEBUG` is off unless set to true explicitly, and the app refuses to start without `SECRET_KEY` when `DEBUG` is off. | — |
| BE-13 | should | all | judge | Mails and other slow side effects are deferred as jobs, not sent inside the request. The script lists candidate lines; a line is a finding only if it runs inside a request. | **procrastinate** (PostgreSQL) · Django's `django.tasks` once a backend matches procrastinate; Celery, Dramatiq, django-q2, RQ, Huey |
| BE-14 | should | all | judge | Writes with business rules or side effects (other models, notifications, events, audit entries) go through `services/`; a plain save of the endpoint's own object with no further effect may stay in the API module. The script lists candidate lines; a line is a finding only if it writes and something else should happen with it. | — |
| BE-15 | should | all | auto | If the backend speaks German (`backend/locale/de` exists), the translation check runs in `check-backend`; otherwise the backend is English only. | **Django's makemessages/compilemessages + the template's check** |
| BE-16 | should | all | auto | The type checker reports checks against cases the types rule out (unreachable branches, `is None` on a value that can't be None, always-true operands). | **mypy with `warn_unreachable`, `strict_equality_for_none`, `redundant-expr`** · pyright or basedpyright in strict mode |
| BE-17 | should | all | auto | The checks limit cognitive complexity (how hard a function is to follow) to at most 15 per function. | **complexipy** |
| BE-18 | should | all | auto | The linter reports swallowed errors: blind `except Exception`, `except: pass` and the like. | **ruff `BLE` and `TRY`** |
| BE-19 | should | all | auto | The type checker also reports truthiness checks on always-true objects, variables set only in some branches, a `match` that misses a case, and `type: ignore` without an error code. | **mypy error codes `truthy-bool`, `possibly-undefined`, `exhaustive-match`, `ignore-without-code`** · pyright or basedpyright in strict mode |
| BE-20 | should | all | auto | The linter reports slow patterns and longer spellings of what the standard library does directly. | **ruff `PERF` and `FURB`** |

## Security

| ID | Level | Scope | How | Rule | Tools |
|---|---|---|---|---|---|
| SEC-01 | must | all | auto | No side effects beyond our responses: no HSTS and no http → https redirect from Django or nginx; no cookie domain set. | — |
| SEC-02 | must | all | auto | Every response, the SPA included, carries a CSP and `X-Content-Type-Options`, `Referrer-Policy`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`. | **nginx** (covers the SPA too) · Django's `SECURE_CSP` (Django 6) or django-csp plus django-permissions-policy, when Django also serves the SPA |
| SEC-04 | should | all | auto | A memory-hard hasher is the first password hasher. | **Argon2** (argon2-cffi) · scrypt (built into Django) |
| SEC-05 | should | all | auto | The container runs `check --deploy` before it serves. | — |
| SEC-07 | should | all | auto | Login attempts are rate-limited — in nginx (`limit_req`, the default) or by the backend's own throttle (stricter per account, and the better choice when users share an office IP). | **nginx `limit_req`** · django-axes, the Ninja or DRF throttles |
| SEC-06 | should | all | auto | Framing is denied. | **CSP `frame-ancestors 'none'`** · `X-Frame-Options: DENY` |

## Docker

| ID | Level | Scope | How | Rule | Tools |
|---|---|---|---|---|---|
| DOCKER-01 | must | all | auto | The app runs as a non-root user; compose sets `read_only`, `cap_drop: [ALL]` and `no-new-privileges`. | — |
| DOCKER-03 | must | all | auto | A smoke test runs the built image in CI and checks: no process runs as root, the root filesystem is read-only, health, SPA and static routes, the unauthenticated status of `/api/auth/me`, every program running. | **`docker/smoke-test` from the template** |
| DOCKER-04 | should | all | auto | `supervisorctl` works in the container (`[unix_http_server]` and `[supervisorctl]`), if supervisord is used. | **supervisord** · s6-overlay (then the item is n/a) |
| DOCKER-08 | should | all | auto | The job worker runs supervised on its own: as a separate compose service from the same image (the default; better when jobs are heavy or long, need their own restarts, logs or scaling) or as its own supervisord program in the app container (fine for small single-host installs that want one container). | — |
| DOCKER-06 | should | all | auto | The Dockerfile's base images are pinned by digest. Compose files keep plain tags; that is not a finding. | **Dependabot** keeps the digests current |

## CI and dependencies

| ID | Level | Scope | How | Rule | Tools |
|---|---|---|---|---|---|
| CI-01 | must | all | auto | Every `uses:` is pinned to a full commit SHA. | **pinact** · ratchet; Dependabot keeps the SHAs current |
| CI-02 | must | all | auto | Workflows set `permissions` at the top; every checkout sets `persist-credentials: false`. | zizmor reports it |
| CI-03 | must | all | auto | No `${{ … }}` expressions inside `run:` scripts; values come in through `env:`. | zizmor reports it |
| CI-04 | should | all | auto | The workflows are linted for errors and security problems in the `check` targets. | **actionlint + zizmor** · poutine instead of zizmor |
| CI-05 | should | all | auto | The image is scanned for vulnerabilities and rebuilt on a weekly schedule. | **Trivy** (pinned by SHA) · Grype, Docker Scout |
| CI-06 | must | all | auto | Dependabot covers the Python, npm, Docker and GitHub Actions dependencies. | **Dependabot** (fixed choice) |
| CI-08 | should | all | auto | Every Dependabot entry sets a cooldown. | — |
| CI-09 | should | all | auto | The JavaScript package manager's version is set in one place (`packageManager` in `package.json`), and the Docker build and CI install that version without the corepack that Node bundled until version 24 (Node 25 and newer ship without it). | **`npm install -g` with the `packageManager` version in the Dockerfile, `pnpm/action-setup` in CI** · corepack installed explicitly (`npm install -g corepack`) |

## Frontend

| ID | Level | Scope | How | Rule | Tools |
|---|---|---|---|---|---|
| FE-01 | must | all | auto | The API types are generated: the OpenAPI schema and the generated types are committed, and the checks fail when they drift. | **openapi-typescript** · orval, @hey-api/openapi-ts |
| FE-02 | should | all | auto | API enums are listed with `allValues` (`src/utils/enums.ts`). | — (the template's helper) |
| FE-03 | should | all | auto | The frontend ships English and German (at least), with the same files per locale. | **vue-i18n; react-i18next** · Lingui, FormatJS |
| FE-04 | should | all | auto | The linter limits complexity and nesting and sets import boundaries; it sets no length limits (`max-lines`, `max-statements`). | **ESLint** · oxlint (same rule names), Biome (`noExcessiveCognitiveComplexity`, `noRestrictedImports`) |
| FE-05 | should | all | auto | Frontend coverage thresholds are at least 90/90/85/85 (lines/statements/functions/branches). | **Vitest** · Jest |
| FE-06 | should | new | auto | `noUncheckedIndexedAccess` is on. | — |
| FE-07 | should | new | auto | The API client is typed from the generated schema. | **openapi-fetch** (with React: openapi-react-query) · orval or @hey-api clients |
| FE-08 | should | all | auto | The linter reports conditions the types make unnecessary. | **`@typescript-eslint/no-unnecessary-condition`** (type-aware) · oxlint with type-aware rules |
| FE-09 | should | all | auto | The linter limits cognitive complexity to at most 15 per function. | **`sonarjs/cognitive-complexity`** · Biome `noExcessiveCognitiveComplexity` |
| FE-10 | should | all | auto | The linter reports promises nobody awaits or catches. | **`@typescript-eslint/no-floating-promises` and `no-misused-promises`** (both in `recommendedTypeChecked`) |
| FE-11 | should | all | auto | A `switch` over a union type must handle every member. | **`@typescript-eslint/switch-exhaustiveness-check`** |
| FE-12 | should | all | auto | Defaults use `??` rather than the or-operator, so `0` and `""` are kept. | **`@typescript-eslint/prefer-nullish-coalescing`** (in `stylisticTypeChecked`) |

## Changelog

Only versions that change items are listed; a plugin release without an entry leaves the checklist as it was.

- **1.0.0** (2026-11-21): first published version, all items.
