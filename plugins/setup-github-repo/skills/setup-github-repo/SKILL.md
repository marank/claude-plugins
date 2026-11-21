---
name: "setup-github-repo"
description: Set a GitHub repository's settings to the house defaults with the gh CLI - squash merge only with the PR title, branches deleted after merge, ruleset "Protect main" (pull requests, resolved threads, required status checks taken from the workflows, no force push) and "Protect release tags", Dependabot alerts and security updates, secret scanning with push protection, private vulnerability reporting, CodeQL default setup, actions pinned by SHA, read-only workflow token, immutable releases, Dependabot labels. Use it when the user wants a new or existing GitHub repo set up "like the others", asks for the repo defaults, branch protection, rulesets or security settings, or wants to check whether a repo's settings still fit. Idempotent, with a dry run.
---

# GitHub repository defaults

One script sets everything that GitHub keeps outside the repository's files. It reads before it writes, so a repo that already fits gives "Nothing to change", and it is safe to run again after the workflows change.

## What it sets

| Area | Setting |
|---|---|
| Merging | squash merge only, commit title = PR title, empty body; "Update branch" button; delete head branches after merge; no auto-merge |
| Features | Discussions on, Wiki and Projects off |
| Ruleset "Protect main" | on the default branch: no deletion, no force push, pull request required (0 approvals, conversations resolved, squash only), required status checks; admins may bypass (so the owner can still push directly) |
| Ruleset "Protect release tags" | `refs/tags/v*`: no deletion, no update, no force push; admins may bypass |
| Security | Dependabot alerts and security updates, secret scanning with push protection, private vulnerability reporting (public repos), CodeQL default setup |
| Actions | actions must be pinned by commit SHA; `GITHUB_TOKEN` read-only; Actions may create and approve pull requests (release-please needs it) |
| Releases | immutable releases |
| Labels | the ones Dependabot uses (`dependencies`, `docker`, `github_actions`, `javascript`, `python:uv`), plus `autorelease: pending` with release-please |

Not touched: description, topics, homepage (they differ per project — suggest them, set with `gh repo edit --description … --add-topic …` only after the user agrees), visibility, collaborators, secrets, the ghcr package's visibility.

## How to run it

Needs `gh` signed in with the `repo` scope (`gh auth status`) and [uv](https://docs.astral.sh/uv/). Run from the repository's checkout; the repo comes from the `origin` remote, or pass `--repo owner/name`.

```bash
uv run --no-project --python ">=3.11" <skill-dir>/scripts/setup_github_repo.py --list-checks
uv run --no-project --python ">=3.11" <skill-dir>/scripts/setup_github_repo.py --dry-run
uv run --no-project --python ">=3.11" <skill-dir>/scripts/setup_github_repo.py
```

1. **Checks first.** `--list-checks` prints the required status checks it found: every job of a workflow triggered by `pull_request`, under the name GitHub reports (the job's `name:` or key; matrix jobs expanded like `image (linux/amd64, ubuntu-24.04)`), without reusable-workflow calls and jobs whose `if:` skips them on pull requests. Show the list to the user. A check that never reports on a PR blocks every merge, one missing lets red PRs through. To change it, pass `--check NAME` once per check (quote names with spaces), or `--no-checks`. A computed matrix (`${{ … }}`) can't be expanded; the script stops and asks for `--check`.
2. **Dry run.** `--dry-run` lists every change without making it. Tell the user what will change in plain words, especially settings that get stricter (e.g. merge commits disabled, new required checks).
3. **Apply** on the user's go-ahead, then run `--dry-run` again: it must say "Nothing to change".

`release-please-config.json` in the checkout adds the release-please label; `--release-please` forces it.

## Good to know

- **Empty repository**: everything can be set before the first push. Rulesets apply to the default branch once it exists; CodeQL finds its languages only after code is there — if no scan runs after the first push, switch the default setup off and on once (Settings → Advanced Security).
- **Renamed or new CI jobs** change the check names: run the script again afterwards, or merges hang on "Expected — waiting for status".
- The script never deletes anything: rulesets with other names, extra labels and settings it doesn't know stay as they are. Mention them if they look like leftovers.
- Organisation-owned repos can get the same rules once for all repos (organisation rulesets and security configurations); the script still works per repo there.
