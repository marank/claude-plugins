# Repository files, developer tooling and README

## 1. Files to copy and fill

From `assets/`: `justfile`, `adr/` (only with ADRs: yes), `.vscode/`, `.claude/`, `AGENTS.md`, `CLAUDE.md`, `CONTRIBUTING.md`, `SECURITY.md`, `CODE_OF_CONDUCT.md`, `.github/ISSUE_TEMPLATE/`, `.github/pull_request_template.md`, `.github/CODEOWNERS`, and the license text if the license calls for it (section 2).

- **`justfile`** — every command of the project, the one place: `<OPENAPI_EXPORT_COMMAND>` = the export command for the chosen API library (backend.md), writing to `../frontend/openapi.json`; `<DEV_PORT>`; `<project>`; `<ACTIONLINT>`, `<ZIZMOR>` (ci.md section 2). Recipes run in bash/zsh and, via `windows-shell`, in PowerShell; keep each line a plain command. CI and the VS Code tasks call recipes and nothing else, so a check is changed only here. Needs just ≥ 1.38 (`uv tool install rust-just`, `brew install just`, `winget install Casey.Just`).
- **`.vscode/tasks.json`**: one task per everyday recipe (`just …`); AGENTS.md and the README refer to the labels.
- **`.claude/launch.json`**: `<DEV_PORT>`; with React nothing else changes.
- **`.vscode/extensions.json`**: keep the `[VUE]` line only for Vue, the `[TAILWIND]` line only with Tailwind.
- **`AGENTS.md`**: `<API_LIBRARY>` (Django Ninja / Django REST framework), `<SCHEMA_DIR>` (`schemas` / `serializers`), `<FRONTEND>` (Vue 3 / React), `<UI_LIBRARY>`, `<DEV_PORT>`, the project name and one sentence on what the app does. Keep the `[VUE]` or `[REACT]` block of the frontend rules. Add project-specific rules (domain terms, date/time conventions, permissions model) as their own section. Every later session, human or agent, reads it first — keep it short and true.
- **`CONTRIBUTING.md`**: `<LICENSE_ID>`; keep `[RELEASE_PLEASE]` or `[MANUAL_RELEASES]`, and `[EXTERNAL]` (pull requests welcome, Code of Conduct, DCO) or `[TEAM_ONLY]` (in active development: an IMPORTANT note that pull requests are not accepted for now and are closed without review; the steps stay, introduced as how a change gets in once they are) — section 4. Everything outside these blocks is the same in every project: keep the template's wording and only fill in names, so contributors meet the same text everywhere. Proprietary projects replace the License section with one sentence on who owns contributions.
- **`CODE_OF_CONDUCT.md`**: only with external contributors (section 4). `<CONDUCT_EMAIL>` = a maintainer address the user names (ask; unattended: drop the email part, the private GitHub report stays).
- **`SECURITY.md`**, issue forms (`bug_report.yml`, `feature_request.yml`, `config.yml` with `<owner>/<project>` for the advisory link), PR template, **`CODEOWNERS`** (`* @<owner>`).
- **`release-please-config.json`**, **`.release-please-manifest.json`**, `.github/workflows/release.yaml`: only with release-please (section 4), as they are (ci.md section 1); without them the project tags releases by hand (`git tag v1.2.3 && git push --tags` builds the versioned image), and the PR template's first line about Conventional Commits goes. release-please writes `CHANGELOG.md` and `version.txt`; don't create them by hand. `pyproject.toml` and `package.json` versions stay at their initial value — the release version is the git tag.
- **`adr/0000-template.md`**: only with ADRs: yes (section 4) — otherwise drop `adr/` and the `[ADRS]` block of AGENTS.md. Copy it; write the first ADRs for the step-1 decisions that had real alternatives (API library, frontend and UI library, license) — short, with the reasons given in the conversation. The AGENTS.md `Glossary` section starts empty and gets a line per domain term as they appear.
- **`BACKLOG.md`** (write it): a heading per area with what's planned and known limitations — start with what came up during scaffolding.

## 2. License (decided in step 1)

`<LICENSE_ID>` is the SPDX identifier everywhere it appears (`pyproject.toml`, `frontend/package.json`, `docs/package.json`, `CONTRIBUTING.md`):

| Choice | When | LICENSE file | `pyproject.toml` / `package.json` |
|---|---|---|---|
| `AGPL-3.0-or-later` | public, self-hosted apps (recommended there): changes made by whoever runs it as a service stay open | `assets/LICENSE-AGPL-3.0` copied as `LICENSE` | `AGPL-3.0-or-later` |
| `MIT` / `Apache-2.0` | libraries, tools, anything where adoption matters more than reciprocity | the official text (SPDX license list, or `gh api /licenses/mit --jq .body` when gh is signed in), with year and owner filled in | the SPDX id |
| proprietary | internal and customer projects | none | `LicenseRef-Proprietary` / `"UNLICENSED"` plus `"private": true` |

The dependency license gate (no GPL/AGPL/SSPL in production dependencies) stays in every variant: it keeps the project's own license a free choice.

## 3. README

Copy `assets/README.md` and fill it. The README is for someone deciding whether to use the project and getting it running — nothing else. Short, from the user's side, no tech stack; about 150 lines. The sections, in this order:

1. **`# <Project>` and one paragraph**: what it is, for whom, what it does from request to result, self-hosted with Docker, the languages. Plain words, no framework names. If the code is written by an AI coding agent, a second short paragraph may say so and what keeps it in shape (types, tests, checks) — only when the user wants that.
2. **One screenshot** of the main screen (`docs/public/screenshots/`), once there is one; a second one further down at most. Until then leave the image out.
3. **`## Features`**, grouped with `###` by area or audience (e.g. "Self-service for employees", "Administration and security"). Bullets of one to three lines: a **bold term** where it helps, then what the user gets — not how it is built. Security and operations (roles, sign-in, hardened container, backups) are one group, last.
4. **`## Quick start with Docker`**: download `compose.yml` and `.env.example`, a table of only the variables that must be set, `docker compose up -d`, where to open it and how to sign in, one line on updates, one line on the TLS proxy with a link.
5. **`## Documentation`** (with docs): where it is (`docs/` and `/docs/` in the running app, languages) and one bullet per area (operations, using it, development) with links. Without docs: a short `## Operations` instead (TLS, settings explained in `.env.example`, backups).
6. **`## Contributing`**: the fixed wording for the recorded mode, then the two commands to run it from source:
   - team only: "<Project> is still in active development, so pull requests are not accepted yet; bug reports and ideas are welcome as issues. See [CONTRIBUTING.md](CONTRIBUTING.md)."
   - external: "Bug reports, ideas and pull requests are welcome. See [CONTRIBUTING.md](CONTRIBUTING.md)."
7. **`## License`**: the license with a link, and one sentence on what it means for the reader — AGPL: "Running a modified <Project> for others over a network obliges you to offer them its source."; MIT/Apache: "You may use, change and share it, keeping the copyright notice."; proprietary: "All rights reserved."

Not in the README — it goes where its readers look: tech stack, project structure and architecture → `docs/…/development/` (or AGENTS.md); every setting → `docs/…/operations/configuration` and `.env.example`; development setup, `just` recipes, checks, release process and GitHub setup → `docs/…/development/` and CONTRIBUTING.md; backups, updates, verifying the image (`gh attestation verify`), `scripts/sync_env.py` → `docs/…/operations/`; internals such as authentication flows → the docs page of that feature. Lines wrap at about 90 characters.

If `git` is available: `git init -b main` and a first commit, so the repo can be pushed right away.

## 4. Releases, contributions and ADRs — three questions

Releases and contributions are asked for every new project (step 1) and, when the repo's AGENTS.md doesn't record them yet and the repo doesn't show them, in every review of an existing one (`check_repo.py` reports them as `ASK`). The answers go into AGENTS.md's `## House defaults` section as `- Releases: release-please` or `- Releases: by hand`, and `- Contributions: external` or `- Contributions: team only`; then they are not asked again. Show the user what each option looks like — most people haven't seen these before:

**Releases: release-please or by hand?**
- *release-please*: commit titles follow Conventional Commits (`feat: show the owner on the detail page`, `fix: keep the filter when paging`, `feat!: …` for breaking changes; with squash merges only the PR title has to). release-please keeps a pull request "chore(main): release 1.3.0" open that updates `CHANGELOG.md` (sections "Features", "Bug Fixes", one line per change with its commit); `fix` or `deps` only → 1.2.1, any `feat` → 1.3.0, `feat!` → 2.0.0. Merging it tags `v1.3.0`, creates the GitHub release and builds the image `1.3.0` / `1.3` / `1`. Worth it once other people run the app and want to know what changed.
- *by hand*: commit titles are plain imperative sentences; a release is `git tag v1.3.0 && git push --tags`, the changelog is written by hand or not at all. Enough while you develop and run it yourselves.

**Contributions: external or team only (in development)?**
- *external*: a `CODE_OF_CONDUCT.md` (adopts the Contributor Covenant by reference, says where to report misconduct) and the DCO: every commit carries `Signed-off-by: Name <mail>` (`git commit -s`), certifying the author may contribute it under the project's license; a GitHub app fails pull requests without it. Matters for AGPL projects that might relicense or face questions about where code came from.
- *team only*: the project is in active development — issues and ideas are welcome, pull requests are not accepted for now and are closed without review (CONTRIBUTING.md says so in an IMPORTANT note and keeps the steps for later); no Code of Conduct, no DCO. Switch to *external* once the structure has settled.

**ADRs: yes or no?** (`- ADRs: yes` / `no`; no line counts as no and is not asked in reviews — an existing `adr/` folder is recorded as yes)
- *yes*: an `adr/` folder with numbered short files, e.g. `adr/0002-sqlite-natively.md` — Context: everyday development should need no database server. Decision: SQLite natively, PostgreSQL in Docker and production. Consequences: no PostgreSQL-only fields or lookups; CI runs on PostgreSQL to catch differences. A file is never rewritten; a changed mind gets a new one that supersedes it. Worth it for projects that live for years or have several people: in a year nobody remembers why.
- *no*: decisions live in commit messages, pull requests and AGENTS.md. Enough for small or short-lived tools.

Unattended: release-please and external contributions for a public repo, by hand and team only otherwise; no ADRs.

