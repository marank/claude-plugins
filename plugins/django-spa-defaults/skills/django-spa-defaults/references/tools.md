# The tools, explained

For explaining a tool when the user asks ("what is zizmor?", "why just?", "explain CI-09") and for the half-sentence a report adds when it first names a tool. Each entry: what it does, what it does for us, and when an alternative fits better. Explain in the user's language and in plain words; facts that change (a project's maintenance status, a security incident, a new major version) are looked up before they are stated.

## Contents
1. Repository and commands
2. Python backend
3. Security and Docker
4. CI and dependencies
5. Frontend

## 1. Repository and commands

- **uv** — installs Python and the backend's packages and runs commands in the project's environment; one fast tool instead of pip, venv and pyenv. Writes `uv.lock`, so everyone gets the same versions. *Alternatives*: poetry, pdm — fine in a repo that already uses them.
- **pnpm** — the frontend's package manager: like npm, but stricter (a package can only import what it declares) and saving disk space. Its version lives in `packageManager` in `package.json`. *Alternatives*: npm (comes with Node, no extra install), yarn, bun.
- **corepack** — a helper that used to come with Node and installed pnpm or yarn in the version from `packageManager`. Node 25 and newer no longer ship it, because it stayed experimental and Node didn't want to be responsible for package managers it doesn't maintain. Install pnpm with `npm install -g` instead, or install corepack itself first (CI-09).
- **`just check-changed`** — the checks before a commit, only for what the changed files can break (changed files linted, touched apps tested, related frontend tests); the full `just check` before a push. Deliberately no git hooks (pre-commit): they slow every commit and get skipped anyway.
- **just** — a command runner: `just check`, `just dev`. The one place for project commands, so CI, editor tasks and people run the same thing. *Alternatives*: make (everywhere already, but made for building files and quirky as a command runner), Task, mise tasks.
- **release-please** — reads the commit titles (Conventional Commits: `feat: …`, `fix: …`) and keeps a release pull request with the next version number and the changelog up to date; merging it publishes the release. Starts at `0.1.0` with `initial-version` (REPO-17). *Alternative*: releases by hand (tag + GitHub release) — simpler for projects that rarely release.
- **DCO GitHub App** — checks that every commit in a pull request carries a `Signed-off-by:` line, the contributor's statement that they may contribute the code. Only for projects with outside contributors.

## 2. Python backend

- **ruff** — linter and formatter in one (with `BLE` and `TRY` it also reports swallowed errors such as `except Exception: pass`; `PERF` slow patterns; `FURB` longer spellings of what the standard library does directly), very fast; replaces flake8, isort, black and many plugins. Finds bugs (unused variables, risky patterns), not just style. *Alternative*: flake8 with plugins in older repos.
- **mypy** with **django-stubs** — checks the type hints, so a wrong argument or a possibly-missing value shows up before it runs; the stubs teach it Django's models and querysets. *Alternatives*: pyright or basedpyright (faster, what VS Code uses internally) with django-types.
- **mypy `warn_unreachable` and friends** — report checks the types make impossible (`if user is None` when `user` can't be None, a branch that can never run), the typical "just to be safe" code that makes functions longer without making them safer.
- **mypy error codes `truthy-bool`, `possibly-undefined`, `exhaustive-match`, `ignore-without-code`** — likely bugs `strict` doesn't catch: `if obj:` on something always true, a variable set in only one branch, a `match` that forgets a new enum value, a blanket `# type: ignore`.
- **ruff `PT`, `PGH`, `RUF100`** — pytest rules (tests that assert, clean fixtures), no blanket `# noqa` or `# type: ignore`, no unused ones: a red check gets fixed, not switched off.
- **pytest-randomly** — shuffles the test order each run, so a test that only passes after another one fails right away.
- **complexipy** — measures cognitive complexity: how hard a function is to follow. Unlike plain branch counting, nesting costs more than a flat list of cases, so a long but flat `match` passes and three nested `if`s don't. Limit 15.
- **import-linter** — enforces which code may import which (API → services → selectors → models; `core` imports no other app), so the structure doesn't erode quietly. *Alternative*: tach.
- **pytest** with **pytest-cov** — runs the tests and measures how much code they cover; the build fails below the agreed share.
- **deptry** — finds packages that are installed but unused, or used but not declared. *Alternative*: fawltydeps.
- **procrastinate** — the job queue: work that shouldn't block a request (mails, imports) runs in a separate worker; uses PostgreSQL itself, so no Redis. *Alternatives*: Django's built-in `django.tasks` once a backend matches procrastinate (it is the future default); Celery or Dramatiq for large setups with a message broker; django-q2, RQ, Huey.
- **pydantic-settings** — reads settings from the environment with validation; an alternative to the template's small `config/env.py`. (django-environ doesn't pass BE-05: it reads an invalid boolean as false instead of refusing it.)

## 3. Security and Docker

- **Argon2** — the recommended way to store passwords: deliberately slow and memory-hungry, so stolen hashes are expensive to crack. *Alternative*: scrypt (built into Django, same idea).
- **nginx** — the web server inside the container: serves the SPA and static files, passes `/api` to Django, sets the security headers and limits login attempts (`limit_req`). *Alternatives* for the rate limit: django-axes, the Ninja or DRF throttles (per account; better when many users share one office IP).
- **CSP `frame-ancestors`** — a header that forbids other sites to embed the app in a frame (protects against clickjacking). *Alternative*: the older `X-Frame-Options: DENY`.
- **supervisord** — starts and watches several processes in one container (nginx, gunicorn). *Alternative*: s6-overlay.
- **gunicorn** — runs Django for production, with several worker processes.

## 4. CI and dependencies

- **GitHub Actions** — runs the checks and builds the image on every push and pull request.
- **Pinning by SHA** — an action is referenced by its exact commit, not by a tag that its owner (or an attacker) can move. **pinact** or **ratchet** convert tags to SHAs; Dependabot keeps them current.
- **actionlint** — finds mistakes in workflow files (syntax, wrong expressions) before GitHub runs them.
- **zizmor** — finds security problems in workflows: injectable expressions, too broad permissions, unpinned actions, cache poisoning. *Alternative*: poutine.
- **Trivy** — scans the finished image for known vulnerabilities in system and language packages. Pin it by SHA. *Alternatives*: Grype, Docker Scout.
- **endoflife.date** — a public list of when versions of Python, Debian, Node.js, PostgreSQL, Django and hundreds of other products lose support; `check_eol.py` asks its API weekly and turns the run red 180 days before.
- **Dependabot** — opens pull requests when a dependency, action or base image has a new version (fixed choice for us; waits 7 days after a release, so broken or malicious releases are usually pulled before we see them).
- **dependency-review** — blocks pull requests that add a dependency with a known serious vulnerability (public repos).
- **build provenance attestation** — a signed record of which workflow built the image from which commit; anyone can verify it with `gh attestation verify`.

## 5. Frontend

- **openapi-typescript** — turns the backend's OpenAPI schema into TypeScript types, so the frontend breaks at compile time when the API changes. *Alternatives*: orval, @hey-api/openapi-ts (they can also generate the client code).
- **openapi-fetch** — a tiny fetch wrapper that uses those types: paths, parameters and responses are checked. With React, **openapi-react-query** adds caching on top. *Alternatives*: the clients orval or @hey-api generate.
- **`allValues`** — our small helper that lists an enum's values so that a new value in the backend fails the type check until the frontend handles it.
- **vue-i18n** / **react-i18next** — translations (English and German). *Alternatives*: Lingui, FormatJS.
- **ESLint** — finds bugs and enforces rules in TypeScript and Vue/React code; with us also complexity, nesting depth and import boundaries. *Alternatives*: oxlint (much faster, same rule names), Biome (linter and formatter in one).
- **`no-unnecessary-condition`** (typescript-eslint) — the frontend counterpart of mypy's unreachable check: reports `if (x)` when the types say `x` is always set. Needs type-aware linting.
- **`no-floating-promises`, `no-misused-promises`** — a promise nobody awaits or catches, so its error vanishes (e.g. an `async` function as a click handler).
- **`switch-exhaustiveness-check`** — a `switch` over a union must handle every member, so a new value from the API fails the build instead of falling through.
- **`prefer-nullish-coalescing`** — `??` instead of `||` for defaults: `count || 10` turns a real `0` into 10, `count ?? 10` doesn't.
- **eslint-plugin-sonarjs** — here only for `cognitive-complexity`, the frontend counterpart of complexipy.
- **`eslint-comments`** (`@eslint-community/eslint-plugin-eslint-comments`) and `reportUnusedDisableDirectives` — every `eslint-disable` names its rules and gives a reason, unused ones fail; with `ban-ts-comment` the same for `@ts-expect-error`. The main guard against AI code that silences checks.
- **`@vitest/eslint-plugin`** — tests without an assertion, a forgotten `.only`, skipped tests.
- **jscpd** — finds copied blocks across TypeScript, Vue and Python; fails above 3 % duplication.
- **`eslint-plugin-vuejs-accessibility`** / **`eslint-plugin-jsx-a11y`** — accessibility mistakes: images without alt text, form fields without a label, clickable elements without keyboard access.
- **eslint-plugin-vue presets** — `essential` only catches errors; `strongly-recommended` adds readability rules such as declared emits. `vue/no-v-html` forbids unescaped HTML (XSS), `vue/no-unused-properties` finds dead props and state.
- **`strictTemplates`** (vue-tsc) — a prop, event or component a template uses but nothing declares becomes a type error.
- **`@eslint-react`** — here only four rules: no `dangerouslySetInnerHTML`, no leaked `{count && …}` that renders "0", no component defined inside another, no array index as key.
- **The Claude Code hook** (`.claude/settings.json` + `scripts/lint_file.py`) — formats and lints each file an agent edits, right after the edit; problems go back to the agent in the same step.
- **Prettier** — formats the code, so nobody discusses formatting.
- **Vitest** — runs the frontend tests, using the same setup as Vite. *Alternative*: Jest in older projects.
- **size-limit** — fails the build when the shipped JavaScript grows past a set size. *Alternative*: bundlewatch.
- **VitePress** — builds the documentation site (German and English) from Markdown.
