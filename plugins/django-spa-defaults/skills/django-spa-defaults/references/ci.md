# CI and dependency updates (GitHub)

## Contents
1. Files
2. Placeholders
3. Backend quality gates: setup
4. Frontend quality gates: setup
5. Making a fresh scaffold pass CI
6. What the user has to set up on GitHub

## 1. Files (copy from `assets/`)

| File | Purpose |
|------|---------|
| `justfile` | every check command; CI jobs and the VS Code tasks only call its recipes (`check-backend`, `check-deploy`, `check-frontend`, `check-docs`, `check-workflows`, `check` for all) |
| `.github/workflows/build.yaml` | jobs backend, frontend, (docs), workflows, repository, dependency-review (PRs) → image per platform on native runners (amd64, arm64: build, smoke test, Trivy scan, push by digest) → merge (multi-platform image with all tags, provenance attestation); weekly rebuild of main; callable by release.yaml |
| `.github/workflows/pr-title.yaml`, `scripts/check_pr_title.py` | (with `- Releases: release-please`) job `pr-title`: the pull request title must be a Conventional Commit (`just check-pr-title`), re-run when the title is edited; its own workflow so an edit doesn't re-run the build. The title reaches the script through `env:` only (CI-03) |
| `.github/workflows/release.yaml` | (with `- Releases: release-please`) release-please: keeps a release PR (CHANGELOG.md, next version) up to date; merging it tags `vX.Y.Z` and calls build.yaml with the version |
| `release-please-config.json`, `.release-please-manifest.json` | release type `simple`; `changelog-sections` with "Dependencies" for `deps:` and the internal types hidden; the first release is `0.1.0` (`initial-version`, release-please would otherwise start at `1.0.0` whatever the manifest says), versions before 1.0 bump minor for breaking changes; manifest starts at `0.0.0` |
| `.github/dependabot.yml` | weekly updates: uv, npm (frontend, docs), Dockerfile (tags + digests), compose, GitHub Actions (SHAs); minor/patch grouped per area, majors one by one, Postgres majors and non-LTS Node majors ignored; commit titles `deps:` for what reaches the image or operators and `chore(deps):` for development tools, so release-please lists them under "Dependencies" or leaves them out, and real `fix:` entries stay readable; a 7-day cooldown on every ecosystem (security updates are not delayed). No automerge: updates are merged by a person after green CI |
| `backend/scripts/check_licenses.py` | license gate for Python prod deps, following the project's own license (repo-files.md section 2), in its own throwaway venv |
| `backend/scripts/check_eol.py` | asks endoflife.date when the Python, Debian, Node.js, PostgreSQL and Django versions in the Dockerfile, compose.yml and uv.lock lose security support; `just check-eol` fails 180 days before. Only in the weekly run (job `eol`), never in `check` (network, date-dependent) and never a required status check |
| `backend/scripts/check_openapi.py` | exports the schema into a temp file and compares it with `frontend/openapi.json`; keep the `[NINJA]` or `[DRF]` command |
| `backend/deploy-check.env` | production-like settings for `just check-deploy` |
| `frontend/scripts/check-licenses.mjs` | the same gate for npm prod deps |

**Supply chain.** Every `uses:` is pinned to the full commit SHA of a release, with the tag as comment (`actions/checkout@<40-hex> # v5.0.0`); images started by the workflow and the Dockerfile's `FROM`s are pinned by tag and digest. The compose files keep plain tags (`postgres:18-alpine`): pinning digests there is unusual and would hold back the patch releases operators get with `docker compose pull`. A moved tag can't change what runs — in March 2026 nearly every tag of `aquasecurity/trivy-action` was force-pushed to credential-stealing code, and only SHA-pinned users were safe. Dependabot updates SHAs and digests together with the comment/tag. Workflow-level `permissions: {}`, each job asks for what it needs, checkouts don't persist credentials. `just check-workflows` runs actionlint (syntax, expressions) and zizmor (template injection, excessive permissions, unpinned actions, cache poisoning, …); fix its findings rather than silencing them — e.g. if it flags caches in the publishing jobs, turn caching off for tag and release runs.

**Images.** `docker/build-push-action` builds each platform on its own runner (`ubuntu-24.04`; `ubuntu-24.04-arm` only with the `[ARM64]` entry) with the GitHub Actions cache; the runtime stage is always rebuilt (`no-cache-filters: runtime`), so system package updates aren't held back. The tested image is loaded locally, smoke-tested (`docker/smoke-test app` and `worker`) and scanned; then the same build is pushed by digest from the cache, with SBOM and provenance. The merge job combines the digests with `docker buildx imagetools create` into one multi-platform image, tags it via `docker/metadata-action` (`latest` from main, `sha-<commit>`, `1.2.3` / `1.2` / `1` from a version — pre-releases only their full version) and attests it (`actions/attest-build-provenance`; verify with `gh attestation verify oci://ghcr.io/<owner>/<repo>:<tag> --owner <owner>`). The image goes to `ghcr.io/<owner>/<repository>` with the workflow's `GITHUB_TOKEN`; no secrets to create.

**Security tab.** Trivy writes SARIF for the repository and each image, uploaded to code scanning; `actions/dependency-review-action` blocks pull requests that add dependencies with known high vulnerabilities. Both, like the attestation, need a public repository (or GitHub Advanced Security) and are skipped on private ones.

**What Dependabot does not cover** — say so in `AGENTS.md` and the development docs:
- `TRIVY_IMAGE` (tag + digest) and `POSTGRES_IMAGE` in `build.yaml`, started with `docker run`; Postgres together with `compose.yml`.
- `ARG SUPERVISOR_VERSION` and `ARG PG_MAJOR` in the Dockerfile (PG_MAJOR follows compose's Postgres major).
- `<ACTIONLINT>` and `<ZIZMOR>` in the justfile, `rust-just==<JUST>` in the workflows.
- pnpm's `packageManager` field: check after the first weeks whether Dependabot opens PRs for it; if not, `pnpm self-update` and commit.

## 2. Placeholders

Research these like every other version (scaffold.md step 2):

| Placeholder | Value |
|---|---|
| `@<SHA> # <VERSION>` (every `uses:`) | newest release tag of that action as `<VERSION>` and its full commit SHA: `git ls-remote https://github.com/<action-repo> refs/tags/<tag>` (for an annotated tag take the `^{}` line). For `github/codeql-action/upload-sarif` the repo is `github/codeql-action` |
| `@<DIGEST>` (images) | digest of that tag's multi-platform index: `docker buildx imagetools inspect <image>:<tag>` → `Digest`, so amd64 and arm64 use the same pin |
| `<PYTHON>`, `<NODE_LTS>`, `<DEBIAN>`, `<PG_MAJOR>`, `<UV>`, `<SUPERVISOR>` | as in the Dockerfile (docker.md) |
| `<TRIVY>` | newest `aquasec/trivy` tag |
| `<JUST>` | newest `rust-just` release on PyPI (≥ 1.38) |
| `<ACTIONLINT>` | newest `actionlint-py` release on PyPI |
| `<ZIZMOR>` | newest `zizmor` release on PyPI |
| `<UNAUTHENTICATED_STATUS>` (in `docker/smoke-test`) | what `/api/auth/me` returns without a session: Ninja `django_auth` → 401, DRF `SessionAuthentication` + `IsAuthenticated` → 403. Check it in the backend tests and use that number |

Blocks marked `[DOCS]` in `build.yaml`, `dependabot.yml` and the justfile (and `[NINJA]` / `[DRF]` in `check_openapi.py`): keep the ones that apply, delete the others with their markers. Without docs also drop `docs` from the image job's `needs` and `setup-docs` / `check-docs` from the `setup` and `check` recipes; the smoke test probes `/docs/` only if the image has it. Delete the "Template notes" comment at the top of `build.yaml`.

## 3. Backend quality gates: setup

Dev dependencies and the full `pyproject.toml` tool configuration (ruff with the readability rules, import-linter contracts, pytest with xdist, coverage with `fail_under = 90`, mypy strict, django-stubs, deptry) are in backend.md sections 1 and 8. DRF also needs `djangorestframework-stubs`; Ninja is typed natively.

Coverage ≥ 90 % has to hold for the scaffold itself: write tests for `config/env.py` (bool/list parsing, APP_URLS parsing, SECRET_KEY guard), the UUID check (`core.E001` fires for an int-pk model), `ensure_admin` (creates once, skips when existing — also with `ADMIN_USERNAME=Admin` next to an existing `admin` —, refuses placeholder password without DEBUG, defaults admin / admin@example.com / administrator when unset, `ADMIN_USERNAME=` empty skips), case-insensitive usernames (a second `Admin` next to `admin` is refused, login works with either case), `set_password --stdin`, `backup_database` (pg_dump mocked with `subprocess.run` and `backups.available` patched to true, so these tests also run on SQLite: writes the file, failure leaves no `.partial`, old dumps are removed; refuses on SQLite), the backup task's hour logic, the side-effect rule (with `APP_URLS` on https and `X-Forwarded-Proto: https`, responses carry no `Strict-Transport-Security`; a plain-http request is answered, not redirected), `jobs.defer` (in-process after commit without a queue, queued with one), and the auth endpoints. The coverage minimum must hold natively (SQLite) and in CI (PostgreSQL). Domain models from step 1 get at least create/list API tests, with factories and a test per list endpoint that the query count doesn't grow with the rows. `apps/core/tests/test_architecture.py` (asset) fails when an app is missing from the import-linter contracts.

## 4. Frontend quality gates: setup

Dev dependencies: the shared ones (`frontend.md` section 1) plus the variant's (`frontend-vue.md` / `frontend-react.md` section 1). Runtime: `openapi-fetch`.

`package.json`: `"license": "<LICENSE_ID>"` (proprietary: `"UNLICENSED"`), `packageManager` with the researched pnpm version, the variant's `dev`, `build`, `build-only`, `type-check`, `test:unit` (section 5 of the variant file), and these scripts:

```json
"preinstall": "node -e \"if (!process.env.npm_config_user_agent?.startsWith('pnpm/')) { console.error('Use pnpm to install the frontend packages.'); process.exit(1) }\"",
"format": "prettier --write src/",
"format:check": "prettier --check src/",
"lint": "oxlint && eslint . && knip",
"lint:fix": "oxlint --fix && eslint . --fix",
"test:coverage": "vitest run --coverage",
"check": "pnpm format:check && pnpm lint && pnpm type-check && pnpm test:coverage && pnpm check:duplication",
"check:duplication": "jscpd --config .jscpd.json",
"size": "size-limit",
"check:licenses": "node scripts/check-licenses.mjs",
"api:types": "openapi-typescript openapi.json -o src/api/schema.d.ts && prettier --write src/api/schema.d.ts"
```

`pnpm check` is the one entry point CI and the VS Code task share. The `lint` script must not use `--fix` (some scaffolder defaults do).

Size budget in `package.json` — start from the scaffold's actual build output plus headroom, so the gate is meaningful but green:

```json
"size-limit": [
  { "name": "JS", "path": "dist/assets/*.js", "limit": "<measured + ~30%> kB" },
  { "name": "CSS", "path": "dist/assets/*.css", "limit": "<measured + ~30%> kB" }
]
```

Coverage thresholds in the Vitest config: `test.coverage = { provider: 'v8', thresholds: { lines: 90, statements: 90, functions: 85, branches: 85 }, include: ['src/**'], exclude: [the variant's list] }`. Vendored UI components and bootstrapping are excluded; everything else is tested through behaviour (`frontend.md` section 6) so the thresholds hold.

`knip.json`: entry and project from the variant file (section 5); ignore `src/components/ui/**` (vendored) and `src/api/schema.d.ts`; add `ignoreDependencies` only for packages knip can't see being used (e.g. Tailwind via CSS import) after confirming they are used.

## 5. Making a fresh scaffold pass CI

CI runs nothing but justfile recipes, so `just check` (what `scripts/verify_scaffold.sh` in the skill runs) is exactly what the check jobs run — natively on SQLite, in CI on PostgreSQL. A new check goes into a recipe, never as an extra command into a workflow. The repository scan, dependency review and the image jobs need GitHub or Docker; the verify script's `--docker` mode covers the image part (build and `docker/smoke-test`).

## 6. What the user has to set up on GitHub

1. **Ruleset for `main`**: pull requests required, **squash merge only** with the PR title as commit message (with release-please: the Conventional Commit it reads), required status checks `backend`, `frontend`, (`docs`), `workflows`, `repository`, both `image` matrix jobs, with release-please `pr-title`, and, on public repos, `dependency-review`. Without it Dependabot PRs can be merged with red CI.
2. **Actions → General**: workflow permissions may stay read-only (the workflows ask for what they need), but with release-please **"Allow GitHub Actions to create and approve pull requests"** must be on, or it can't open its release PR. Since June 2026 the checks on a pull request opened by `github-actions[bot]` run only after someone with write access clicks **"Approve and run workflows"** — on the release PR after every update. That is intended (generated changes don't run workflows unasked); approve when you want to release. A GitHub App token for release-please (`actions/create-github-app-token`) makes the checks run without approval, at the cost of an app and two secrets — worth it only when releases are frequent.
3. **Security** (Settings → Advanced Security; free on public repos): private vulnerability reporting (SECURITY.md points there), Dependabot alerts, secret scanning with push protection, CodeQL default setup (Python, JavaScript/TypeScript, Actions).
4. **Releases**: turn on immutable releases, so a published release and its tag can't be changed afterwards.
5. **DCO** (with external contributors): install the DCO GitHub App and make its check required, as CONTRIBUTING.md asks for sign-offs.
6. **Package**: the first push creates `ghcr.io/<owner>/<repository>` as private. Make it public (or give the servers a read token) so `docker compose pull` works; link it to the repository so the workflows keep write access.
7. **Community profile** (Insights → Community standards) should then be complete: README, CODE_OF_CONDUCT, CONTRIBUTING, LICENSE, SECURITY, issue and PR templates.
