# setup-github-repo

One skill that sets everything GitHub keeps outside a repository's files to one set of defaults: squash merges with the PR title, rulesets for `main` and release tags, required status checks read from the workflows, Dependabot, secret scanning, private vulnerability reporting, CodeQL, actions pinned by SHA, a read-only workflow token, immutable releases and the labels Dependabot uses.

It reads before it writes: a dry run shows every change, and a repo that already fits gives "Nothing to change". Run it for a new repo, after renaming CI jobs, or to check that an old repo still fits. The full list is in [`SKILL.md`](skills/setup-github-repo/SKILL.md).

Invoke it with `/setup-github-repo` or ask for a repo to be set up "like the others".

## Requirements

The [GitHub CLI](https://cli.github.com) signed in with the `repo` scope, and [uv](https://docs.astral.sh/uv/) for the script.

## Layout

```
skills/setup-github-repo/
├── SKILL.md                     what it sets and how to run it
└── scripts/setup_github_repo.py idempotent gh api calls, --dry-run, --list-checks
```
