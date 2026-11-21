# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6"]
# ///
"""Bring a GitHub repository's settings in line with the house defaults.

Runs `gh api` for every setting, so it needs the GitHub CLI signed in with the
`repo` scope. Idempotent: run it again and it changes nothing that already fits.
Rulesets are matched by name and updated in place.

    uv run setup_github_repo.py [--repo owner/name] [--check NAME ...] [--release-please] [--dry-run]
"""

from __future__ import annotations

import argparse
import itertools
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

GITHUB_ACTIONS_APP_ID = 15368  # the "GitHub Actions" app that reports workflow checks

REPO_SETTINGS: dict[str, Any] = {
    "allow_merge_commit": False,
    "allow_rebase_merge": False,
    "allow_squash_merge": True,
    "squash_merge_commit_title": "PR_TITLE",
    "squash_merge_commit_message": "BLANK",
    "allow_update_branch": True,
    "delete_branch_on_merge": True,
    "allow_auto_merge": False,
    "has_wiki": False,
    "has_projects": False,
    "has_discussions": True,
}

# Labels Dependabot puts on its PRs (it creates them itself, but only when it first needs them).
DEPENDABOT_LABELS = [
    ("dependencies", "0366d6", "Pull requests that update a dependency file"),
    ("docker", "21ceff", "Pull requests that update docker code"),
    ("github_actions", "000000", "Pull requests that update GitHub Actions code"),
    ("javascript", "168700", "Pull requests that update javascript code"),
    ("python:uv", "2b67c6", "Pull requests that update python:uv code"),
]
RELEASE_PLEASE_LABEL = ("autorelease: pending", "ededed", "")

ADMIN_BYPASS = [{"actor_id": 5, "actor_type": "RepositoryRole", "bypass_mode": "always"}]


def main_ruleset(checks: list[str]) -> dict[str, Any]:
    rules: list[dict[str, Any]] = [
        {"type": "deletion"},
        {"type": "non_fast_forward"},
        {
            "type": "pull_request",
            "parameters": {
                "allowed_merge_methods": ["squash"],
                "dismiss_stale_reviews_on_push": False,
                "require_code_owner_review": False,
                "require_last_push_approval": False,
                "required_approving_review_count": 0,
                "required_review_thread_resolution": True,
            },
        },
    ]
    if checks:
        rules.append(
            {
                "type": "required_status_checks",
                "parameters": {
                    "do_not_enforce_on_create": False,
                    "strict_required_status_checks_policy": False,
                    "required_status_checks": [
                        {"context": c, "integration_id": GITHUB_ACTIONS_APP_ID} for c in checks
                    ],
                },
            }
        )
    return {
        "name": "Protect main",
        "target": "branch",
        "enforcement": "active",
        "bypass_actors": ADMIN_BYPASS,
        "conditions": {"ref_name": {"include": ["~DEFAULT_BRANCH"], "exclude": []}},
        "rules": rules,
    }


TAG_RULESET: dict[str, Any] = {
    "name": "Protect release tags",
    "target": "tag",
    "enforcement": "active",
    "bypass_actors": ADMIN_BYPASS,
    "conditions": {"ref_name": {"include": ["refs/tags/v*"], "exclude": []}},
    "rules": [{"type": "deletion"}, {"type": "update"}, {"type": "non_fast_forward"}],
}


# --- gh helpers ------------------------------------------------------------------


class Gh:
    def __init__(self, repo: str, dry_run: bool) -> None:
        self.repo = repo
        self.dry_run = dry_run
        self.changes = 0

    def get(self, path: str) -> Any:
        """GET; returns None on 404 (feature off or not found)."""
        res = subprocess.run(
            ["gh", "api", f"repos/{self.repo}{path}"], check=False, capture_output=True, text=True
        )
        if res.returncode != 0:
            if "404" in res.stderr or "Not Found" in res.stdout:
                return None
            sys.exit(f"gh api GET {path} failed: {res.stderr.strip() or res.stdout.strip()}")
        return json.loads(res.stdout) if res.stdout.strip() else {}

    def send(self, method: str, path: str, body: Any = None, what: str = "") -> None:
        self.changes += 1
        print(f"  {'would ' if self.dry_run else ''}{what or f'{method} {path}'}")
        if self.dry_run:
            return
        cmd = ["gh", "api", "-X", method, f"repos/{self.repo}{path}", "--silent"]
        res = subprocess.run(
            [*cmd, "--input", "-"] if body is not None else cmd,
            input=json.dumps(body) if body is not None else None,
            check=False,
            capture_output=True,
            text=True,
        )
        if res.returncode != 0:
            sys.exit(f"gh api {method} {path} failed: {res.stderr.strip() or res.stdout.strip()}")


# --- required checks from the workflows ---------------------------------------------


def _triggers(workflow: dict[Any, Any]) -> set[str]:
    on = workflow.get("on", workflow.get(True))  # YAML 1.1 reads a bare `on` as True
    if isinstance(on, str):
        return {on}
    if isinstance(on, list):
        return set(on)
    if isinstance(on, dict):
        return set(on)
    return set()


def _skipped_on_pr(job: dict[str, Any]) -> bool:
    cond = str(job.get("if", ""))
    return bool(
        re.search(r"event_name\s*==\s*'(push|schedule|workflow_dispatch|release)'", cond)
        or re.search(r"event_name\s*!=\s*'pull_request'", cond)
        or re.search(r"github\.ref\s*==", cond)
    )


def _matrix_combos(matrix: Any) -> list[dict[str, Any]] | None:
    """Static matrix combinations, or None if the matrix is computed (`${{ }}`)."""
    if not isinstance(matrix, dict):
        return None if matrix else [{}]
    axes = {k: v for k, v in matrix.items() if k not in ("include", "exclude")}
    if any(not isinstance(v, list) for v in axes.values()):
        return None
    combos = [dict(zip(axes, vals, strict=True)) for vals in itertools.product(*axes.values())]
    for ex in matrix.get("exclude", []) or []:
        combos = [c for c in combos if not all(c.get(k) == v for k, v in ex.items())]
    for inc in matrix.get("include", []) or []:
        merged = False
        for c in combos:
            if all(c.get(k) == v for k, v in inc.items() if k in axes) and all(
                k in axes or k not in c for k in inc
            ):
                c.update(inc)
                merged = True
        if not merged:
            combos.append(dict(inc))
    return combos or [{}]


def _check_names(key: str, job: dict[str, Any]) -> list[str]:
    name = str(job.get("name", key))
    matrix = (job.get("strategy") or {}).get("matrix")
    if not matrix:
        return [name]
    combos = _matrix_combos(matrix)
    if combos is None:
        return [f"{name} (matrix: check by hand)"]
    names = []
    for combo in combos:
        if "${{" in name:
            names.append(
                re.sub(
                    r"\$\{\{\s*matrix\.([\w-]+)\s*\}\}",
                    lambda m, c=combo: str(c.get(m.group(1), "")),
                    name,
                )
            )
        else:
            # GitHub appends the values of the matrix (objects shown as their keys' values).
            vals = [str(v) for v in combo.values() if not isinstance(v, (dict, list))]
            names.append(f"{name} ({', '.join(vals)})" if vals else name)
    return names


def checks_from_workflows(root: Path) -> list[str]:
    checks: list[str] = []
    for path in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        workflow = yaml.safe_load(path.read_text()) or {}
        if "pull_request" not in _triggers(workflow):
            continue
        for key, job in (workflow.get("jobs") or {}).items():
            if isinstance(job, dict) and "uses" not in job and not _skipped_on_pr(job):
                checks.extend(_check_names(key, job))
    return checks


# --- steps -------------------------------------------------------------------------


def repo_from_git() -> str:
    url = subprocess.run(
        ["git", "remote", "get-url", "origin"], capture_output=True, text=True, check=True
    ).stdout.strip()
    m = re.search(r"github\.com[:/]([^/]+/[^/]+?)(\.git)?$", url)
    if not m:
        sys.exit(f"origin is not a GitHub repository ({url}); pass --repo owner/name")
    return m.group(1)


def apply(gh: Gh, checks: list[str], release_please: bool) -> None:
    repo = gh.get("")
    if repo is None:
        sys.exit(f"repository {gh.repo} not found (or no access)")
    public = repo["visibility"] == "public"

    print("Repository")
    wanted = dict(REPO_SETTINGS)
    diff = {k: v for k, v in wanted.items() if repo.get(k) != v}
    if diff:
        gh.send("PATCH", "", diff, "set " + ", ".join(f"{k}={v}" for k, v in diff.items()))

    print("Security")
    sec = repo.get("security_and_analysis") or {}
    wanted_sec = [
        "secret_scanning",
        "secret_scanning_push_protection",
        "dependabot_security_updates",
    ]
    off = [k for k in wanted_sec if (sec.get(k) or {}).get("status") != "enabled"]
    if gh.get("/vulnerability-alerts") is None:
        gh.send("PUT", "/vulnerability-alerts", what="enable Dependabot alerts")
    if off:
        body = {"security_and_analysis": {k: {"status": "enabled"} for k in off}}
        gh.send("PATCH", "", body, "enable " + ", ".join(off))
    if not (gh.get("/automated-security-fixes") or {}).get("enabled"):
        gh.send("PUT", "/automated-security-fixes", what="enable Dependabot security updates")
    if public and not (gh.get("/private-vulnerability-reporting") or {}).get("enabled"):
        gh.send(
            "PUT", "/private-vulnerability-reporting", what="enable private vulnerability reporting"
        )
    scan = gh.get("/code-scanning/default-setup") or {}
    if scan.get("state") != "configured":
        body = {"state": "configured", "query_suite": "default"}
        gh.send("PATCH", "/code-scanning/default-setup", body, "enable CodeQL default setup")

    print("Actions")
    perms = gh.get("/actions/permissions") or {}
    if not perms.get("enabled") or not perms.get("sha_pinning_required"):
        body = {
            "enabled": True,
            "allowed_actions": perms.get("allowed_actions", "all"),
            "sha_pinning_required": True,
        }
        gh.send("PUT", "/actions/permissions", body, "require actions pinned by commit SHA")
    wf = gh.get("/actions/permissions/workflow") or {}
    wanted_wf = {"default_workflow_permissions": "read", "can_approve_pull_request_reviews": True}
    if any(wf.get(k) != v for k, v in wanted_wf.items()):
        gh.send(
            "PUT",
            "/actions/permissions/workflow",
            wanted_wf,
            "read-only token, Actions may create and approve pull requests",
        )

    print("Releases")
    if not (gh.get("/immutable-releases") or {}).get("enabled"):
        gh.send("PUT", "/immutable-releases", what="enable immutable releases")

    print("Rulesets")
    existing = {r["name"]: r["id"] for r in gh.get("/rulesets") or []}
    for ruleset in (main_ruleset(checks), TAG_RULESET):
        rid = existing.get(ruleset["name"])
        if rid is None:
            gh.send("POST", "/rulesets", ruleset, f"create ruleset '{ruleset['name']}'")
            continue
        current = gh.get(f"/rulesets/{rid}") or {}
        if _ruleset_differs(current, ruleset):
            gh.send("PUT", f"/rulesets/{rid}", ruleset, f"update ruleset '{ruleset['name']}'")

    print("Labels")
    have = {label["name"] for label in gh.get("/labels?per_page=100") or []}
    labels = DEPENDABOT_LABELS + ([RELEASE_PLEASE_LABEL] if release_please else [])
    for name, color, desc in labels:
        if name not in have:
            gh.send(
                "POST",
                "/labels",
                {"name": name, "color": color, "description": desc},
                f"create label '{name}'",
            )


def _ruleset_differs(current: dict[str, Any], wanted: dict[str, Any]) -> bool:
    def norm(rs: dict[str, Any]) -> Any:
        rules = []
        for rule in rs.get("rules", []):
            params = rule.get("parameters") or {}
            if rule["type"] == "required_status_checks":
                params = {
                    **params,
                    "required_status_checks": sorted(
                        c["context"] for c in params.get("required_status_checks", [])
                    ),
                }
            elif rule["type"] == "pull_request":
                params = {k: v for k, v in params.items() if k in wanted_pr_keys}
            rules.append((rule["type"], json.dumps(params, sort_keys=True)))
        return (
            rs.get("enforcement"),
            json.dumps(rs.get("conditions"), sort_keys=True),
            sorted(json.dumps(a, sort_keys=True) for a in rs.get("bypass_actors", [])),
            sorted(rules),
        )

    wanted_pr_keys = next(
        (set(r["parameters"]) for r in wanted["rules"] if r["type"] == "pull_request"), set()
    )
    return norm(current) != norm(wanted)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--repo", help="owner/name (default: the origin remote)")
    parser.add_argument("--path", default=".", help="local checkout to read workflows from")
    parser.add_argument(
        "--check",
        action="append",
        dest="checks",
        metavar="NAME",
        help="a required status check; repeat for several "
        "(default: the pull_request jobs in .github/workflows)",
    )
    parser.add_argument("--no-checks", action="store_true", help="require no status checks")
    parser.add_argument(
        "--release-please", action="store_true", help="also create the 'autorelease: pending' label"
    )
    parser.add_argument(
        "--list-checks", action="store_true", help="only print the checks found in the workflows"
    )
    parser.add_argument("--dry-run", action="store_true", help="show what would change")
    args = parser.parse_args()

    root = Path(args.path)
    if args.no_checks:
        checks: list[str] = []
    elif args.checks:
        checks = args.checks
    else:
        checks = checks_from_workflows(root)
    if args.list_checks:
        print("\n".join(checks))
        return
    if any("check by hand" in c for c in checks):
        sys.exit(
            "a job has a computed matrix; pass the check names with --check:\n  "
            + "\n  ".join(checks)
        )

    repo = args.repo or repo_from_git()
    print(
        f"{repo}: required checks {', '.join(checks) or '(none)'}"
        f"{' (dry run)' if args.dry_run else ''}"
    )
    gh = Gh(repo, args.dry_run)
    apply(gh, checks, args.release_please or (root / "release-please-config.json").exists())
    print(
        f"\n{gh.changes} change(s){' to make' if args.dry_run else ''}; "
        "everything else already fits."
        if gh.changes
        else "\nNothing to change."
    )


if __name__ == "__main__":
    main()
