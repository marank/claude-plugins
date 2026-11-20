# <Project> — conventions for contributors and coding agents

<One sentence: what the app does.> Django backend (`backend/`, API via <API_LIBRARY>), <FRONTEND> +
TypeScript SPA (`frontend/`, <UI_LIBRARY>), one hardened Docker image. Read this before changing
structure; `README.md` has setup and commands, `BACKLOG.md` what's planned.

## Commands

All commands live in the `justfile` (`just` lists them); CI and the VS Code tasks call the same recipes.
- `just dev-backend` + `just dev-frontend` (VS Code: **Dev: start all**): Django :8000 on SQLite
  (`backend/data/`), Vite :<DEV_PORT> → http://localhost:<DEV_PORT>. No job worker natively: jobs run
  in-process after the commit, periodic jobs (backups) don't run. `just db-up` + `DB_HOST=localhost`
  for PostgreSQL like CI.
- `just check` runs everything CI runs and must pass before a push. A check is added or changed in
  the justfile only — never as an extra command in a workflow.
- `just api-types` after any API change (schema → `frontend/openapi.json` →
  `frontend/src/api/schema.d.ts`); commit both. CI fails when they drift.
- `just migrations` after model changes; commit the migrations (CI fails on missing ones).
- `just messages` after new backend texts; translate `backend/locale/de/…/django.po`.
- Frontend: **pnpm** only. Backend: `uv add` / `uv add --dev`.
<!-- [RELEASE_PLEASE] -->
- Commits on `main` are Conventional Commits (squash-merged PR titles); release-please builds
  CHANGELOG.md and the releases from them (CONTRIBUTING.md).
<!-- [/] -->
- Dependabot proposes updates weekly, including the pinned commit SHAs of actions and the image
  digests. Not covered: `TRIVY_IMAGE`/`POSTGRES_IMAGE` in `build.yaml`, `SUPERVISOR_VERSION`/`PG_MAJOR`
  in the Dockerfile, the actionlint/zizmor versions in the justfile, `rust-just` in the workflows,
  pre-commit hooks (by hand: `uv tool run pre-commit autoupdate`). Version updates wait 7 days
  (cooldown); security updates don't.
- GitHub Actions: every `uses:` pinned to a full commit SHA with the version as comment, jobs ask
  only for the permissions they need, checkouts without persisted credentials; `just check-workflows`
  (actionlint, zizmor) enforces it.

## Backend rules

- Apps live in `backend/apps/<name>/` (`name = "apps.<name>"`, `label = "<name>"`).
- **No monolithic modules, no artificial fragments.** `models/`, `admin/`, `api/`, `<SCHEMA_DIR>/`,
  `services/`, `tests/` are packages; split them by cohesion, not by count — a file per model together
  with the helpers only it uses, per resource, per workflow. A domain that grows gets its own app
  before an app gets huge. `__init__.py` re-exports explicitly. Relations use string references
  (`"app.Model"`).
- **Dependencies point one way**, checked by `lint-imports` (import-linter, `pyproject.toml`): inside an
  app `api` → `services` → `selectors` → `models`; `core` imports no other app. A new app goes into both
  contracts (a test fails otherwise).
- **Limits on tangle, not on length.** ruff fails at a cyclomatic complexity above 15; there is no
  line or statement limit. Split a function when it does two things, not when it is long.
- **Every model inherits `apps.core.models.UUIDModel` or `TimeStampedModel`** (UUIDv7 primary key);
  `manage.py check` fails (`core.E001`) otherwise. URLs and payloads carry these UUIDs. Order queries explicitly.
- Business rules go in `services/`, not in API modules, a model's `save()` or signals (signals hide the
  flow; only for cross-cutting concerns). Views stay thin. A write with rules or side effects (other
  models, notifications, events, audit entries) goes through a service, so no endpoint can forget one;
  a plain save of the endpoint's own object with no further effect may stay in the API module — no
  pass-through services. A query used in two places moves to
  `selectors/`; before that it stays where it is used. Permissions are checked in the backend, never
  only in the frontend.
- Usernames are case-insensitive (unique on `Lower("username")`): look users up with
  `get_by_natural_key` or `username__iexact`, never with an exact `username=` filter.
- Rules that must always hold are database constraints (`UniqueConstraint`, `CheckConstraint`), not only
  validation. Choices are `TextChoices`; every relation has a `related_name`.
- API: under `/api/`, no trailing slashes, session auth + CSRF, UUIDs in paths. `/api/health` stays
  unauthenticated and exactly at that path (container health check, CI smoke test).
  PATCH: left out means unchanged; `null` only where a field may really be empty.
- Side effects (emails, anything slow) run as jobs (procrastinate, `apps/*/tasks.py`), deferred
  through `apps.core.jobs.defer(...)` inside the transaction that causes them — never in the request,
  never with `task.defer()` directly (natively there is no queue; `defer` handles both).
- Code runs on SQLite (native) and PostgreSQL (Docker, CI, production): no PostgreSQL-only fields or
  lookups.
- Configuration only via environment variables read through `config/env.py`; every new variable
  the app reads gets a commented entry in `.env.example`. `.env.example` is for operators: variables
  only CI or tooling scripts read (`CI`, `GITHUB_*`) stay out of it. No secrets with placeholder values in production.
<!-- [BACKEND_DE] -->
- User-facing texts in English, wrapped in `gettext`; German goes into `backend/locale/de`.
<!-- [BACKEND_EN] -->
- The backend speaks English only; texts users see are translated in the frontend (error codes, enum
  labels). Before adding emails or documents in German, set up backend translations (`i18n.md` in the skill).
<!-- [/] -->
- mypy runs in strict mode (django-stubs), tests included (without annotation duty);
  `# type: ignore[code]` only with the reason next to it.
- Test data from `factory_boy` factories (`tests/factories.py` per app), not hand-built objects. Every
  list endpoint has a test that its query count is the same for 1 and for 10 rows, so an N+1 query fails
  (no hard-coded counts: they break with every harmless optimisation).
- Coverage stays ≥ 90 %. Tests run in parallel (`-n auto`) with `config.settings_test`: natively on
  SQLite, in CI on PostgreSQL. Tests that need PostgreSQL (e.g. a real `pg_dump`) are skipped on SQLite.
- No GPL/AGPL/SSPL dependencies (CI license check), whatever <Project>'s own license: it stays a free choice.

## Frontend rules

- API calls only through `src/api/` (typed client from the generated `schema.d.ts`; it sends the
  CSRF header). Payload types are `Schemas['XyzOut']` from `src/api/types.ts`, never hand-written
  copies; never edit `schema.d.ts`.
- A list of every value of an API enum is written with `allValues<Schemas['Status']>({ … })`
  (`src/utils/enums.ts`), so a value added in the backend fails the type check until it is listed.
<!-- [VUE] -->
- Views per area in `src/views/`, shared pieces in `src/components/` (by area), `src/composables/`,
  `src/stores/` (Pinia, client state only). Keep components to one job; logic goes into composables
  or `src/utils/` (pure, tested on its own).
- Every visible text through vue-i18n, in `src/i18n/locales/en/` **and** `de/` (one file per area;
  a test checks both have the same keys).
<!-- [REACT] -->
- Pages per area in `src/pages/`, shared pieces in `src/components/` (by area). Server data only through
  the TanStack Query hooks in `src/queries/<area>.ts` — no `useEffect` + fetch; mutations invalidate
  their query keys. Client state in components and context. Keep components to one job; logic goes
  into hooks or `src/utils/` (pure, tested on its own). The hooks lint rules are errors.
- Every visible text through react-i18next (`t('…')`, keys type-checked), in
  `src/i18n/locales/en/` **and** `de/` (one file per area; a test checks both have the same keys).
<!-- [/] -->
- No inline `<script>`, no remote scripts, styles or fonts: the CSP only allows our origin.
- Expose state semantically (`aria-pressed`, `aria-current`, `aria-expanded`, `data-*`) rather than only
  through classes; tests check those.
- Limits on tangle, not on length (ESLint): complexity ≤ 15, nesting ≤ 4, no line limit for files or
  components — split a component when it has two jobs, not when it is long. Import boundaries: only
  `src/api/` uses the client; shared code (components, composables/hooks, utils) never imports a
  page or view; `src/utils/` stays pure (no components, no API). `noUncheckedIndexedAccess` is on.

## Tests

- Test behaviour, not implementation: click and type, then check what is shown and which requests go
  out. Fixtures look like what the backend really sends (typed by the generated API types).
- A bug fix comes with a test that fails without it.
- Frontend coverage gate: 90/90/85/85 (lines/statements/functions/branches).

## Readability

- Comments explain why — decisions, constraints, edge cases — not what the code does. No
  commented-out code (ruff `ERA`); git keeps the history.
- One word per domain concept, the same in code, UI texts and docs (glossary below).
<!-- [ADRS] -->
- A decision someone might question later (a library, an architecture trade-off, a deliberate
  exception to these rules) gets an ADR in `adr/` (copy `adr/0000-template.md`); routine choices don't.
<!-- [/] -->

## Glossary

<!-- One line per domain term once the first ones exist: term — meaning — UI label (en / de). -->

## Documentation

<!-- [DOCS] keep this section only with docs/; otherwise: user-visible changes update README.md. -->
- `docs/` holds the documentation (VitePress), served at `/docs/`. A change users or operators notice
  (new feature, changed rule, new setting or variable) updates the matching page.
- **Every page exists in German and English** under the same path in `docs/de/` and `docs/en/`; change
  both in the same commit (the build fails when a counterpart is missing).
- Professional and direct: no filler. Use the exact UI labels from `frontend/src/i18n/locales/`.
- `just check-docs` must pass: dead links, anchors and missing translations fail it.

## Docker / runtime

- One image, two containers: `app` (supervisord runs nginx and gunicorn; if one keeps failing, the
  container stops) and `worker` (the job queue, `docker/worker`). Both run read-only, without
  capabilities, as the unprivileged user `app`. Only `/data` (`DATA_DIR`), `/backups` (worker) and
  `/tmp` are writable; new features write there instead of loosening `compose.yml`.
- The worker dumps the database nightly into `/backups` (`BACKUP_TIME`, `BACKUP_KEEP_DAYS`);
  `docker compose exec worker python manage.py backup_database` dumps right away.
- The image is smoke-tested on every platform it is built for (`docker/smoke-test`); new runtime
  behaviour gets a probe there.
- nginx believes `X-Forwarded-*` only from `TRUSTED_PROXIES`.
- **No side effects beyond our own responses.** Nothing the app or its nginx sends may change how
  clients or other services treat the host or domain: no HSTS, no http → https redirect (TLS, redirects
  and HSTS belong to the reverse proxy in front), no cookies for a parent domain, no service worker or
  other persistent client install unless the project decides so explicitly. A test checks that responses carry no
  `Strict-Transport-Security` and that http requests are not redirected. The Django admin lives under `/django-admin` (so `/admin` stays free for the SPA) and signs in
  through the app's login only.
- `compose.yml` must work with `.env` alone, without any other file from the repository.

## House defaults

Checked against checklist <CHECKLIST_VERSION> (<DATE>). Accepted deviations and settled judgements,
one line each as `- ID: decision and reason`, or `- ID [path, …]: …` for exceptions in some places only
(IDs from the project-defaults checklist); the review does not report these again:

Project decisions (asked once; the review checks against them and asks again only if a line is missing):
- Releases: <RELEASES>
- Contributions: <CONTRIBUTIONS>
- ADRs: <ADRS>

<!-- Examples:
- SEC-06: framing allowed for same-origin pages, the print preview embeds them.
- BE-14 [backend/apps/core/api/crud.py]: the generic CRUD layer writes by design.
- FE-05: floor 88/86/79/82 (today), raised with every feature; delete this line at 90/90/85/85. -->
