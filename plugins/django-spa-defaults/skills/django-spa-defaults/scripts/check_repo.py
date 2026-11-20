#!/usr/bin/env python3
"""Check a repository against the house defaults checklist (references/checklist.md).

    uv run --no-project --python ">=3.11" <skill-dir>/scripts/check_repo.py <repo> [--new] [--full] [--json]

Decides every `auto` item the same way on every run, applies the accepted deviations from
the repo's AGENTS.md ("## House defaults" section: accepted deviations and settled
judgements), and lists candidate lines for the `judge` items that are not settled yet.
Items with scope `new` are only checked with --new (fresh scaffolds); --full ignores the
settled list.
Exit code 0 when no unaccepted `auto` item fails, 1 otherwise. Standard library only.
"""

from __future__ import annotations

import json
import re
import sys
import tomllib
from fnmatch import fnmatch
from dataclasses import dataclass, field
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parents[1]
CHECKLIST = SKILL_DIR / "references" / "checklist.md"
ID_RE = r"[A-Z]+-\d{2}"
TASK_FILES = ("justfile", "Makefile", "Taskfile.yml", "Taskfile.yaml", "mise.toml")
JS_LOCKS = {"pnpm": "pnpm-lock.yaml", "npm": "package-lock.json", "yarn": "yarn.lock", "bun": "bun.lock", "bun ": "bun.lockb"}
PY_LOCKS = ("uv.lock", "poetry.lock", "pdm.lock")
TOOL_LIST = re.compile(r"\((?:[\w@/.-]+, )+[\w@/. -]+\)$")  # "(import-linter, tach)": no known tool found
UNKNOWN = "another tool? record `- {id}: met with <tool>` in AGENTS.md"
SKIP_DIRS = {".git", "node_modules", ".venv", "dist", "build", "__pycache__", ".mypy_cache", ".ruff_cache"}


# --- Checklist and repo helpers -------------------------------------------------------------


@dataclass
class Item:
    id: str
    level: str
    scope: str
    how: str
    rule: str
    tools: str


@dataclass
class Result:
    status: str  # pass | fail | judge | ask | n/a
    details: list[str] = field(default_factory=list)


def load_checklist() -> tuple[str, list[Item], dict[str, list[str]], set[str]]:
    text = CHECKLIST.read_text(encoding="utf-8")
    version = re.search(r"^Checklist version: (\S+)", text, re.M).group(1)
    items = []
    for m in re.finditer(rf"^\| ({ID_RE}) \| (\w+) \| (\w+) \| (\w+) \| (.+?) \| (.+) \|$", text, re.M):
        items.append(Item(*m.groups()))
    added: dict[str, list[str]] = {}
    retired: set[str] = set()
    for m in re.finditer(r"^- \*\*(\d+\.\d+)\*\*[^\n]*", text, re.M):
        new_part, _, retired_part = m.group(0).partition("retired")
        added[m.group(1)] = re.findall(ID_RE, new_part)
        retired |= set(re.findall(ID_RE, retired_part))
    return version, items, added, retired


class Repo:
    def __init__(self, root: Path) -> None:
        self.root = root

    def path(self, rel: str) -> Path:
        return self.root / rel

    def exists(self, rel: str) -> bool:
        return self.path(rel).exists()

    def read(self, rel: str) -> str:
        p = self.path(rel)
        return p.read_text(encoding="utf-8", errors="replace") if p.is_file() else ""

    def files(self, pattern: str) -> list[Path]:
        return sorted(
            p for p in self.root.glob(pattern)
            if p.is_file() and not SKIP_DIRS.intersection(p.relative_to(self.root).parts)
        )

    def rel(self, p: Path) -> str:
        return p.relative_to(self.root).as_posix()

    def grep(self, pattern: str, files: list[Path], skip_tests: bool = True) -> list[str]:
        hits = []
        for p in files:
            if not p.is_file():
                continue
            rel = self.rel(p)
            if skip_tests and ("/tests/" in f"/{rel}" or Path(rel).name.startswith(("test_", "conftest"))):
                continue
            for n, line in enumerate(p.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
                if re.search(pattern, line):
                    hits.append(f"{rel}:{n}: {line.strip()[:100]}")
        return hits

    def pyproject(self) -> dict:
        try:
            return tomllib.loads(self.read("backend/pyproject.toml"))
        except tomllib.TOMLDecodeError:
            return {}

    def workflows(self) -> list[Path]:
        return self.files(".github/workflows/*.y*ml")

    def workflows_text(self) -> str:
        return "\n".join(p.read_text(encoding="utf-8") for p in self.workflows())

    def nginx_text(self) -> str:
        files = [p for p in self.files("docker/**/*") if "nginx" in p.name or p.suffix in {".conf", ".template"}]
        lines = []
        for p in files:
            lines += [ln for ln in p.read_text(encoding="utf-8", errors="replace").splitlines()
                      if not ln.strip().startswith(("#", ";"))]
        return "\n".join(lines)

    def settings_text(self) -> str:
        return self.read("backend/config/settings.py")

    def apps(self) -> list[str]:
        return sorted(p.parent.name for p in self.root.glob("backend/apps/*/apps.py"))

    def has_frontend(self) -> bool:
        return self.exists("frontend/package.json")

    def has_docker(self) -> bool:
        return self.exists("Dockerfile")

    def tasks_text(self) -> str:
        """The task runner's file, whichever it is (just, make, Task, mise)."""
        return "".join(self.read(f) for f in TASK_FILES)

    def package_manager(self) -> str | None:
        """The frontend's package manager, by its lock file."""
        found = [pm for pm, lock in JS_LOCKS.items() if self.exists(f"frontend/{lock}")]
        return found[0] if len(found) == 1 else None


def justfile_recipes(text: str) -> dict[str, tuple[list[str], str]]:
    """Recipe name -> (dependencies, body) from a justfile."""
    recipes: dict[str, tuple[list[str], str]] = {}
    current = None
    for line in text.splitlines():
        header = re.match(r"^@?([a-z][\w-]*)(?:\s+[^:=]*)?:(?!=)\s*(.*)$", line)
        if header and not line.startswith((" ", "\t")):
            current = header.group(1)
            deps = re.findall(r"[a-z][\w-]*", header.group(2).split("#")[0])
            recipes[current] = (deps, "")
        elif current and line.startswith((" ", "\t")):
            deps, body = recipes[current]
            recipes[current] = (deps, body + line.strip() + "\n")
        elif line.strip() and not line.startswith(("#", "[")):
            current = None
    return recipes


def recipe_text(recipes: dict[str, tuple[list[str], str]], name: str, seen: set[str] | None = None) -> str:
    seen = seen or set()
    if name in seen or name not in recipes:
        return ""
    seen.add(name)
    deps, body = recipes[name]
    return body + "".join(recipe_text(recipes, d, seen) for d in deps)


def run_blocks(path: Path) -> list[tuple[int, str]]:
    """(line number, script) for every `run:` step of a workflow (line-based YAML scan)."""
    lines = path.read_text(encoding="utf-8").splitlines()
    blocks, i = [], 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:- )?run:\s*(.*)$", lines[i])
        if not m:
            i += 1
            continue
        indent, rest, start = len(m.group(1)), m.group(2), i + 1
        script = [] if rest.startswith(("|", ">")) else [rest]
        i += 1
        while i < len(lines) and (not lines[i].strip() or len(lines[i]) - len(lines[i].lstrip()) > indent):
            script.append(lines[i])
            i += 1
        blocks.append((start, "\n".join(script)))
    return blocks


def missing(required: list[str], text: str) -> list[str]:
    return [r for r in required if r not in text]


def verdict(problems: list[str]) -> Result:
    return Result("fail", problems) if problems else Result("pass")


# --- Checks ---------------------------------------------------------------------------------


def repo_01(r: Repo) -> Result:
    problems = []
    if not r.exists("AGENTS.md"):
        problems.append("AGENTS.md missing")
    if "AGENTS.md" not in r.read("CLAUDE.md"):
        problems.append("CLAUDE.md missing or not pointing to AGENTS.md")
    return verdict(problems)


def repo_02(r: Repo) -> Result:
    problems = [f"{f} missing" for f in ("README.md", "CONTRIBUTING.md") if not r.exists(f)]
    if not r.exists("LICENSE") and '"UNLICENSED"' not in r.read("frontend/package.json"):
        problems.append("LICENSE missing")
    return verdict(problems)


def has_check_target(r: Repo) -> bool:
    return ("check" in justfile_recipes(r.read("justfile"))
            or bool(re.search(r"^check\s*:", r.read("Makefile"), re.M))
            or bool(re.search(r"^  check\s*:", r.read("Taskfile.yml") + r.read("Taskfile.yaml"), re.M))
            or bool(re.search(r"^\[tasks\.\"?check\"?\]", r.read("mise.toml"), re.M)))


def repo_03(r: Repo) -> Result:
    problems = [] if has_check_target(r) else ["no task runner with a `check` target (justfile, Makefile, Taskfile, mise)"]
    tool = re.compile(r"\b(uv run|pytest|ruff|mypy|pnpm (?:check|test|lint|build|audit|size|run)|manage\.py)\b")
    for wf in r.workflows():
        for line, script in run_blocks(wf):
            if tool.search(script):
                problems.append(f"{r.rel(wf)}:{line}: runs a check directly instead of through `just`")
    return verdict(problems)


def repo_05(r: Repo) -> Result:
    pattern = re.compile(
        r"""(?:env_\w+\(|os\.environ\.get\(|os\.getenv\(|os\.environ\[)\s*["']([A-Z][A-Z0-9_]+)["']""")
    # Only what the app reads at runtime (settings, apps): variables of CI and tooling
    # scripts (CI, GITHUB_*, …) don't belong in an operator's .env.
    names: set[str] = set()
    for p in r.files("backend/config/**/*.py") + r.files("backend/apps/**/*.py"):
        if "/tests/" in f"/{r.rel(p)}" or p.name in {"settings_test.py", "conftest.py"}:
            continue
        names |= set(pattern.findall(p.read_text(encoding="utf-8", errors="replace")))
    names -= {"DJANGO_SETTINGS_MODULE", "CI"}
    names = {n for n in names if not n.startswith(("GITHUB_", "RUNNER_", "PYTEST_"))}
    documented = set(re.findall(r"^\s*#?\s*([A-Z][A-Z0-9_]+)=", r.read(".env.example"), re.M))
    if not r.exists(".env.example"):
        return Result("fail", [".env.example missing"])
    return verdict([f"{n} has no entry in .env.example" for n in sorted(names - documented)])


def repo_06(r: Repo) -> Result:
    problems = []
    parts = [("backend", PY_LOCKS)] if r.exists("backend/pyproject.toml") else []
    parts += [(p.parent.name, tuple(JS_LOCKS.values())) for p in r.files("*/package.json")]
    for folder, locks in parts:
        found = [lock for lock in locks if r.exists(f"{folder}/{lock}")]
        if not found:
            problems.append(f"{folder}: no lock file committed")
        elif len(found) > 1:
            problems.append(f"{folder}: several package managers ({', '.join(found)})")
    return verdict(problems)


def repo_07(r: Repo) -> Result:
    problems = [] if r.exists(".editorconfig") else [".editorconfig missing"]
    if not re.search(r"^/?\.env$", r.read(".gitignore"), re.M):
        problems.append(".gitignore does not ignore .env")
    return verdict(problems)


def repo_19(r: Repo) -> Result:
    if not r.exists(".gitattributes"):
        return Result("fail", [".gitattributes missing"])
    lines = [line.split() for line in r.read(".gitattributes").splitlines()]
    ok = any(parts[0] == "*" and "eol=lf" in parts[1:] for parts in lines if parts)
    return verdict([] if ok else [".gitattributes does not set `* text=auto eol=lf`"])


def be_01(r: Repo) -> Result:
    if not r.exists("backend/apps"):
        return Result("fail", ["backend/apps missing"])
    return verdict([f"backend/apps/{a}/models.py is a module, not a package" for a in r.apps()
                    if r.exists(f"backend/apps/{a}/models.py")])


def be_02(r: Repo) -> Result:
    return verdict([] if "AUTH_USER_MODEL" in r.settings_text() else ["AUTH_USER_MODEL not set"])


def be_03(r: Repo) -> Result:
    ok = any("E001" in p.read_text(encoding="utf-8") and "uuid" in p.read_text(encoding="utf-8").lower()
             for p in r.files("backend/apps/*/checks.py"))
    return verdict([] if ok else ["no UUID primary key system check (E001) in apps/*/checks.py"])


def be_04(r: Repo) -> Result:
    py = r.files("backend/apps/**/*.py") + r.files("backend/config/**/*.py")
    problems = []
    if not r.grep(r"""Lower\(\s*["']username["']\s*\)""", py):
        problems.append('no Lower("username") unique constraint')
    problems += [f"exact username lookup: {h}" for h in r.grep(
        r"\.(filter|get|exclude|get_or_create|update_or_create)\("
        r"([^)]*\busername\s*=|\s*\*\*\{\s*\w+\.USERNAME_FIELD\s*:)", py)]
    return verdict(problems)


def be_05(r: Repo) -> Result:
    if not r.exists("backend/config/env.py") and "pydantic_settings" in r.settings_text():
        return verdict(r.grep(r"os\.environ|os\.getenv", [r.path("backend/config/settings.py")]))
    return be_05_env_py(r)


def be_05_env_py(r: Repo) -> Result:
    env = r.read("backend/config/env.py")
    if not env:
        return Result("fail", ["backend/config/env.py missing"])
    problems = [f"reads the environment directly: {h}" for h in
                r.grep(r"os\.environ|os\.getenv", [r.path("backend/config/settings.py")])]
    env_bool = re.search(r"def env_bool.*?(?=\ndef |\Z)", env, re.S)
    if not env_bool or "raise" not in env_bool.group(0):
        problems.append("env_bool does not reject invalid values")
    return verdict(problems)


def be_06(r: Repo) -> Result:
    text = r.read("backend/pyproject.toml") + r.read("backend/.importlinter")
    if "[tool.importlinter]" in text or "[importlinter]" in text:
        return verdict([f"apps.{a} missing from the import-linter contracts" for a in r.apps()
                        if not re.search(rf"\bapps\.{a}\b", text)])
    tach = r.read("backend/tach.toml") + r.read("tach.toml")
    if tach or "[tool.tach]" in text:
        tach += text
        return verdict([f"apps.{a} missing from the tach modules" for a in r.apps()
                        if not re.search(rf"apps[./]{a}\b", tach)])
    return Result("fail", ["no import boundaries configured (import-linter, tach)"])


def be_07(r: Repo) -> Result:
    lint = r.pyproject().get("tool", {}).get("ruff", {})
    lint = {**lint, **lint.get("lint", {})}
    select = set(lint.get("select", [])) | set(lint.get("extend-select", []))
    ignore = set(lint.get("ignore", []))
    if not select:
        flake8 = r.read("backend/.flake8") + r.read("backend/setup.cfg") + r.read("backend/tox.ini")
        if "[flake8]" in flake8:
            return Result("judge", ["flake8: compare its plugins with the rule families"])
        return Result("fail", ["no linter configured (ruff, flake8)"])
    if "ALL" in select:
        return Result("pass")
    problems = [f"ruff does not select {c}" for c in
                ["E", "F", "I", "UP", "B", "DJ", "SIM", "C90", "DTZ", "T20", "ERA", "S"] if c not in select]
    if select & {"PL", "PLR", "PLR0915"} and "PLR0915" not in ignore:
        problems.append("ruff selects the statement-count limit PLR0915")
    return verdict(problems)


def be_08(r: Repo) -> Result:
    tool = r.pyproject().get("tool", {})
    for name in ("pyright", "basedpyright"):
        conf = tool.get(name) or {}
        if not conf and name == "pyright" and r.exists("backend/pyrightconfig.json"):
            conf = json.loads(r.read("backend/pyrightconfig.json") or "{}")
        if conf:
            problems = [] if conf.get("typeCheckingMode") == "strict" else [f"{name} is not in strict mode"]
            if "django-types" not in r.read("backend/pyproject.toml"):
                problems.append("django-types not installed")
            return verdict(problems)
    mypy = tool.get("mypy", {})
    if not mypy:
        return Result("fail", ["no type checker configured (mypy, pyright)"])
    problems = [] if mypy.get("strict") is True else ["mypy strict is not on"]
    if "mypy_django_plugin.main" not in mypy.get("plugins", []):
        problems.append("django-stubs plugin not configured")
    return verdict(problems)


def be_09(r: Repo) -> Result:
    data = r.pyproject().get("tool", {})
    fail_under = data.get("coverage", {}).get("report", {}).get("fail_under")
    if fail_under is None:
        m = re.search(r"--cov-fail-under[= ](\d+)", str(data.get("pytest", {})))
        fail_under = int(m.group(1)) if m else None
    return verdict([] if fail_under is not None and fail_under >= 90 else [f"coverage fail_under is {fail_under}"])


def be_10(r: Repo) -> Result:
    return verdict([f"settings lack {t}" for t in missing(["sqlite3", "postgresql", "DB_HOST"], r.settings_text())])


def be_11(r: Repo) -> Result:
    return Result("judge", r.grep(r"\bDEBUG\s*=|SECRET_KEY\s*=|ImproperlyConfigured", [r.path("backend/config/settings.py")]))


def be_14(r: Repo) -> Result:
    api = r.files("backend/apps/*/api/**/*.py") + r.files("backend/apps/*/views*.py")
    writes = r"^(?!\s*@).*(\.(save|delete)\(|\.objects\.\w+\(|(objects|filter\(.*\))\..*\b(update|delete)\()"
    candidates = [h for h in r.grep(writes, api) if re.search(r"save\(|delete\(|create\(|update\(", h)]
    return Result("judge", candidates)


def be_13(r: Repo) -> Result:
    py = [p for p in r.files("backend/apps/**/*.py") if p.name != "tasks.py"]
    return Result("judge", r.grep(r"^(?!\s*def ).*(\bsend_mail\(|EmailMessage\(|EmailMultiAlternatives\(|\.send\(\))", py))


def sec_01(r: Repo) -> Result:
    settings = [r.path("backend/config/settings.py")]
    problems = r.grep(r"SECURE_HSTS_SECONDS\s*=\s*(?!0\s*(#|$))", settings)
    problems += r.grep(r"SECURE_SSL_REDIRECT\s*=\s*(?!False\b)", settings)
    problems += r.grep(r"(SESSION|CSRF)_COOKIE_DOMAIN\s*=\s*(?!None\b)", settings)
    if "Strict-Transport-Security" in r.nginx_text():
        problems.append("nginx sends Strict-Transport-Security")
    return verdict(problems)


def sec_02(r: Repo) -> Result:
    nginx = r.nginx_text()
    if nginx:
        return verdict([f"nginx does not send {h}" for h in missing(
            ["Content-Security-Policy", "X-Content-Type-Options", "Referrer-Policy", "Permissions-Policy",
             "Cross-Origin-Opener-Policy"], nginx)])
    settings = r.settings_text()
    if not settings:
        return Result("n/a")
    # Without nginx Django sends them: SecurityMiddleware covers nosniff, referrer and COOP by default.
    problems = [] if "SecurityMiddleware" in settings else ["SecurityMiddleware is not installed"]
    if not re.search(r"SECURE_CSP\b|CONTENT_SECURITY_POLICY\b", settings):
        problems.append("no CSP (SECURE_CSP or django-csp)")
    if "PERMISSIONS_POLICY" not in settings:
        problems.append("no Permissions-Policy (django-permissions-policy)")
    return verdict(problems)


def sec_04(r: Repo) -> Result:
    ok = re.search(r"PASSWORD_HASHERS\s*=\s*\[\s*[\"'][^\"']*(Argon2|Scrypt)", r.settings_text())
    return verdict([] if ok else ["neither Argon2 nor scrypt is the first password hasher"])


def sec_05(r: Repo) -> Result:
    if not r.has_docker():
        return Result("n/a")
    text = r.read("Dockerfile") + "".join(p.read_text(encoding="utf-8", errors="replace") for p in r.files("docker/**/*"))
    return verdict([] if "check --deploy" in text else ["the container does not run check --deploy at start"])


def sec_06(r: Repo) -> Result:
    nginx = r.nginx_text()
    if nginx:
        ok = "frame-ancestors 'none'" in nginx or re.search(r"X-Frame-Options[\"']?\s+[\"']?DENY", nginx, re.I)
        return verdict([] if ok else ["nginx does not deny framing (frame-ancestors 'none' or X-Frame-Options DENY)"])
    settings = r.settings_text()
    if not settings:
        return Result("n/a")
    ok = "XFrameOptionsMiddleware" in settings and not re.search(r"X_FRAME_OPTIONS\s*=\s*[\"']SAMEORIGIN", settings)
    return verdict([] if ok else ["Django does not deny framing (XFrameOptionsMiddleware with DENY)"])


def docker_01(r: Repo) -> Result:
    if not r.has_docker():
        return Result("n/a")
    problems = [] if re.search(r"^USER\s+(?!root\b|0\b)\S+", r.read("Dockerfile"), re.M) else ["Dockerfile sets no non-root USER"]
    compose = r.read("compose.yml") or r.read("docker-compose.yml")
    problems += [f"compose lacks {t}" for t in missing(["read_only: true", "ALL", "no-new-privileges"], compose)]
    return verdict(problems)


def docker_03(r: Repo) -> Result:
    if not r.has_docker():
        return Result("n/a")
    text = r.workflows_text() + "".join(
        p.read_text(encoding="utf-8", errors="replace") for p in r.files("docker/*smoke*") + r.files("scripts/*smoke*"))
    if "smoke" not in text.lower():
        return Result("fail", ["no smoke test of the built image in CI"])
    checks = {"no process as root": r"Uid:|as root", "read-only root filesystem": r"touch\b",
              "health": r"/api/health", "SPA route": r"probe /\s|/some/|client/route",
              "static files": r"static", "/api/auth/me status": r"/api/auth/me", "programs running": r"RUNNING"}
    return verdict([f"smoke test does not check: {name}" for name, pat in checks.items() if not re.search(pat, text)])


def docker_04(r: Repo) -> Result:
    conf = "".join(p.read_text(encoding="utf-8", errors="replace") for p in r.files("docker/**/*supervisord*"))
    if not conf:
        return Result("n/a")
    return verdict([f"supervisord config lacks {s}" for s in missing(["[unix_http_server]", "[supervisorctl]"], conf)])


def docker_06(r: Repo) -> Result:
    if not r.has_docker():
        return Result("n/a")
    stages = set(re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)", r.read("Dockerfile"), re.M | re.I))
    froms = [f for f in re.findall(r"^FROM\s+(?:--\S+\s+)*(\S+)", r.read("Dockerfile"), re.M) if f not in stages]
    return verdict([f"FROM {f} is not pinned by digest" for f in froms if "@sha256:" not in f])


def ci_01(r: Repo) -> Result:
    problems = []
    for wf in r.workflows():
        for n, line in enumerate(wf.read_text(encoding="utf-8").splitlines(), 1):
            m = None if line.lstrip().startswith("#") else re.search(r"uses:\s*([^\s#]+)", line)
            if m and not m.group(1).startswith(("./", "docker://")) and not re.search(r"@[0-9a-f]{40}$", m.group(1)):
                problems.append(f"{r.rel(wf)}:{n}: {m.group(1)}")
    return verdict(problems)


def ci_02(r: Repo) -> Result:
    problems = []
    for wf in r.workflows():
        text = wf.read_text(encoding="utf-8")
        if not re.search(r"^permissions:", text, re.M):
            problems.append(f"{r.rel(wf)}: no top-level permissions")
        lines = text.splitlines()
        for n, line in enumerate(lines):
            if re.search(r"uses:\s*actions/checkout@", line) and \
                    "persist-credentials: false" not in "\n".join(lines[n + 1:n + 5]):
                problems.append(f"{r.rel(wf)}:{n + 1}: checkout persists credentials")
    return verdict(problems)


def ci_03(r: Repo) -> Result:
    return verdict([f"{r.rel(wf)}:{line}: ${{{{ … }}}} inside run" for wf in r.workflows()
                    for line, script in run_blocks(wf) if "${{" in script])


def ci_04(r: Repo) -> Result:
    text = r.tasks_text()
    problems = [] if "actionlint" in text else ["the check targets don't run actionlint"]
    if not re.search(r"zizmor|poutine", text):
        problems.append("the check targets don't run a security linter for workflows (zizmor, poutine)")
    return verdict(problems)


def ci_05(r: Repo) -> Result:
    text = r.workflows_text()
    scanned = re.search(r"trivy|grype|docker scout|scout-action", text, re.I)
    return verdict(([] if scanned else ["no image scan (Trivy, Grype, Docker Scout)"]) +
                   ([] if "schedule:" in text else ["no scheduled rebuild"]))


def ci_06(r: Repo) -> Result:
    text = r.read(".github/dependabot.yml")
    if not text:
        return Result("fail", ["no .github/dependabot.yml"])
    entries = re.split(r"^\s*- package-ecosystem:", text, flags=re.M)[1:]
    ecosystems = {e.split()[0].strip("\"'") for e in entries}
    problems = [f"Dependabot does not cover {name}" for name, options in
                [("Python", {"uv", "pip"}), ("npm", {"npm"}), ("Docker", {"docker"}), ("GitHub Actions", {"github-actions"})]
                if not ecosystems & options]
    return verdict(problems)


def ci_08(r: Repo) -> Result:
    entries = re.split(r"^\s*- package-ecosystem:", r.read(".github/dependabot.yml"), flags=re.M)[1:]
    if not entries:
        return Result("n/a")
    return verdict([f"Dependabot entry {e.split()[0]} has no cooldown" for e in entries if "cooldown:" not in e])


def ci_09(r: Repo) -> Result:
    pm = r.package_manager()
    if pm in (None, "npm"):  # npm comes with Node; no frontend or no single lock file (REPO-06)
        return Result("n/a")
    package = json.loads(r.read("frontend/package.json") or "{}")
    problems = [] if str(package.get("packageManager", "")).startswith(pm.strip()) else [
        f"frontend/package.json sets no packageManager for {pm.strip()}"]
    for p in [r.path("Dockerfile")] + r.workflows():
        if not p.is_file():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        installs = re.search(r"npm (?:install|i) (?:-g|--global) corepack", text)
        for n, line in enumerate(text.splitlines(), 1):
            if line.lstrip().startswith("#"):
                continue
            if re.search(r"\bcorepack (enable|prepare|use|install)\b", line) and not installs:
                problems.append(f"{r.rel(p)}:{n}: corepack without installing it (missing on Node 25+)")
            if re.search(r"\b(pnpm|yarn)@\d", line):
                problems.append(f"{r.rel(p)}:{n}: a second place for the package manager version")
        problems += [f"{r.rel(p)}: pnpm/action-setup sets its own version" for _ in
                     re.finditer(r"pnpm/action-setup\S*[^\n]*\n(?:[ \t]+(?!- )[^\n]*\n)*?[ \t]+version:", text)]
    return verdict(problems)


def fe_01(r: Repo) -> Result:
    problems = [] if r.exists("frontend/openapi.json") or r.exists("frontend/openapi.yaml") else ["frontend/openapi.json missing"]
    generators = r"openapi-typescript|orval|@hey-api/openapi-ts"
    if not re.search(generators, r.read("frontend/package.json")):
        problems.append("no type generator (openapi-typescript, orval, @hey-api/openapi-ts)")
    if not re.search(r"schema\.d\.ts|api-types|" + generators, r.tasks_text() + r.workflows_text()):
        problems.append("no check that the API types are up to date")
    return verdict(problems)


def fe_02(r: Repo) -> Result:
    return verdict([] if "allValues" in r.read("frontend/src/utils/enums.ts") else ["no allValues in src/utils/enums.ts"])


def fe_03(r: Repo) -> Result:
    dirs = [p for p in r.root.glob("frontend/src/**/locales") if p.is_dir() and "node_modules" not in p.parts]
    if not dirs:
        return Result("fail", ["no locales folder in frontend/src"])
    problems = []
    for d in dirs:
        en, de = ({p.relative_to(d / lang).as_posix() for p in (d / lang).rglob("*") if p.is_file()}
                  for lang in ("en", "de"))
        if not en or not de:
            problems.append(f"{r.rel(d)}: en or de missing")
        problems += [f"{r.rel(d)}: only in en: {f}" for f in sorted(en - de)]
        problems += [f"{r.rel(d)}: only in de: {f}" for f in sorted(de - en)]
    return verdict(problems)


def fe_04(r: Repo) -> Result:
    text = "".join(p.read_text(encoding="utf-8") for p in
                   r.files("frontend/eslint.config.*") + r.files("frontend/.oxlintrc.json"))
    biome = r.read("frontend/biome.json") + r.read("frontend/biome.jsonc") + r.read("biome.json")
    if not text and biome:
        return verdict([f"Biome does not set `{t}`" for t in
                        missing(["noExcessiveCognitiveComplexity", "noRestrictedImports"], biome)])
    problems = [f"the linter does not set `{t}`" for t in missing(["complexity", "max-depth", "no-restricted-imports"], text)]
    problems += [f"the linter sets the length limit `{t}`" for t in ("max-lines", "max-statements")
                 if re.search(rf"['\"]{t}['\"]\s*:", text)]
    return verdict(problems)


def fe_05(r: Repo) -> Result:
    text = "".join(p.read_text(encoding="utf-8") for p in r.files("frontend/vite*.config.*") + r.files("frontend/jest.config.*"))
    problems = []
    for key, minimum in (("lines", 90), ("statements", 90), ("functions", 85), ("branches", 85)):
        m = re.search(rf"\b{key}:\s*(\d+)", text)
        if not m or int(m.group(1)) < minimum:
            problems.append(f"coverage {key} is {m.group(1) if m else 'not set'}, minimum {minimum}")
    return verdict(problems)


def fe_06(r: Repo) -> Result:
    text = "".join(p.read_text(encoding="utf-8") for p in r.files("frontend/tsconfig*.json"))
    return verdict([] if re.search(r'"noUncheckedIndexedAccess"\s*:\s*true', text) else ["noUncheckedIndexedAccess is off"])


def fe_07(r: Repo) -> Result:
    ok = re.search(r'"(openapi-fetch|openapi-react-query|orval|@hey-api/client-\w+)"', r.read("frontend/package.json"))
    return verdict([] if ok else ["no client typed from the schema (openapi-fetch, orval, @hey-api)"])


def repo_10(r: Repo) -> Result:
    recipes = justfile_recipes(r.read("justfile"))
    if not recipes:
        if has_check_target(r):
            return Result("judge", ["not a justfile: compare the check targets with the rule"])
        return Result("fail", ["no task runner with check targets"])
    backend = recipe_text(recipes, "check-backend")
    goals = {"lint": r"ruff check|flake8|pylint", "formatting": r"ruff format --check|black --check",
             "types": r"mypy|pyright", "migrations check": r"makemigrations --check",
             "Django system checks": r"manage\.py check", "API schema drift": r"check_openapi|openapi",
             "tests": r"pytest|manage\.py test"}
    problems = [f"check-backend does not cover {g}" for g, pat in goals.items() if not re.search(pat, backend)]
    if r.has_frontend():
        frontend = recipe_text(recipes, "check-frontend")
        goals = {"lint, formatting, types and tests": r"(pnpm|npm|yarn|bun)( run)? (check|lint)",
                 "API types drift": r"schema\.d\.ts|api-types|openapi-typescript|orval|openapi-ts",
                 "the build": r"build"}
        problems += [f"check-frontend does not cover {g}" for g, pat in goals.items() if not re.search(pat, frontend)]
    return verdict(problems)


def repo_11(r: Repo) -> Result:
    text = r.tasks_text() + r.read("frontend/package.json") + r.workflows_text()
    goals = {"unused or missing dependencies": r"deptry|fawltydeps|knip",
             "dependency licenses": r"check_licenses|check:licenses|pip-licenses|license-checker|licensee",
             "frontend bundle size": r"size-limit|pnpm size|bundlesize|bundlewatch"}
    if not r.has_frontend():
        goals.pop("frontend bundle size")
    return verdict([f"no check for {g}" for g, pat in goals.items() if not re.search(pat, text)])


def repo_12(r: Repo) -> Result:
    return verdict([] if r.exists("SECURITY.md") or r.exists(".github/SECURITY.md") else ["SECURITY.md missing"])


def sec_07(r: Repo) -> Result:
    nginx = r.nginx_text()
    if "limit_req_zone" in nginx and re.search(r"location[^{]*auth/login[^{]*\{[^}]*limit_req\b", nginx):
        return Result("pass")
    py = r.files("backend/apps/**/*.py") + r.files("backend/config/**/*.py")
    if r.grep(r"(?i)throttl|ratelimit|rate_limit|axes", py):
        return Result("pass")
    return Result("fail", ["no login rate limit, neither in nginx nor in the backend"])


def docker_08(r: Repo) -> Result:
    compose = r.read("compose.yml") or r.read("docker-compose.yml")
    if not compose:
        return Result("n/a")
    if re.search(r"^  [\w-]*worker[\w-]*:", compose, re.M):
        return Result("pass")
    supervisor = "".join(p.read_text(encoding="utf-8", errors="replace") for p in r.files("docker/**/*supervisord*"))
    if re.search(r"^\[program:[^\]]*\]\s*\n(?:[^\[]*\n)*?command\s*=.*(worker|procrastinate|celery|rq|dramatiq|huey|qcluster)", supervisor, re.M):
        return Result("pass")
    return Result("fail", ["the job worker runs neither as its own compose service nor as its own supervisord program"])


def be_15(r: Repo) -> Result:
    if not r.exists("backend/locale/de"):
        return Result("pass")  # English-only backend
    text = r.tasks_text()
    return verdict([] if "check_translations" in text or "makemessages" in text
                   else ["backend/locale/de exists, but no translation check runs"])


def project_decision(r: Repo, key: str, options: tuple[str, ...]) -> str | None:
    """`- Releases: release-please` and the like in AGENTS.md's House defaults section."""
    m = re.search(r"^## House defaults\s*$(.*?)(?=^## |\Z)", r.read("AGENTS.md"), re.M | re.S)
    section = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S) if m else ""
    d = re.search(rf"^\s*[-*]\s*{key}:\s*(.+?)\s*$", section, re.M | re.I)
    value = d.group(1).strip().lower() if d else ""
    return next((o for o in options if value.startswith(o)), None)


RELEASES = ("Releases", ("release-please", "by hand"))
ADRS = ("ADRs", ("yes", "no"))
CONTRIBUTIONS = ("Contributions", ("external", "team only"))


def repo_shows(r: Repo, key: str) -> str | None:
    """What the repo itself shows for a project decision that AGENTS.md doesn't record."""
    if key == "ADRs":
        return "yes" if r.path("adr").is_dir() or r.path("docs/adr").is_dir() else None
    if key == "Releases":
        return "release-please" if r.exists("release-please-config.json") or "release-please" in r.workflows_text() else None
    flat = " ".join(r.read("CONTRIBUTING.md").replace("**", "").split()).lower()
    if "pull requests are not accepted" in flat:
        return "team only"
    if "pull requests are welcome" in flat or "signed-off-by" in flat:
        return "external"
    return None


def decision(r: Repo, spec: tuple[str, tuple[str, ...]]) -> str | None:
    """The recorded decision, else what the repo shows (the dependent items check against it)."""
    return project_decision(r, *spec) or repo_shows(r, spec[0])


def not_recorded(r: Repo, spec: tuple[str, tuple[str, ...]]) -> Result | None:
    key, options = spec
    if project_decision(r, key, options):
        return None
    shown = repo_shows(r, key)
    if shown:
        return Result("ask", [f"not recorded, but the repo shows {shown}: record `- {key}: {shown}` without asking"])
    return Result("ask", [f"{key}: {' or '.join(options)}? (repo-files.md section 4)"])


def repo_13(r: Repo) -> Result:
    if open_question := not_recorded(r, RELEASES):
        return open_question
    choice = decision(r, RELEASES)
    if choice == "by hand":
        return Result("pass")
    return verdict([f"{f} missing" for f in
                    ("release-please-config.json", ".release-please-manifest.json", ".github/workflows/release.yaml")
                    if not r.exists(f)])


def repo_14(r: Repo) -> Result:
    if open_question := not_recorded(r, CONTRIBUTIONS):
        return open_question
    choice = decision(r, CONTRIBUTIONS)
    if choice == "team only":
        return Result("pass")
    problems = [] if r.exists("CODE_OF_CONDUCT.md") or r.exists(".github/CODE_OF_CONDUCT.md") else ["CODE_OF_CONDUCT.md missing"]
    if "Signed-off-by" not in r.read("CONTRIBUTING.md") and "git commit -s" not in r.read("CONTRIBUTING.md"):
        problems.append("CONTRIBUTING.md does not ask for the DCO sign-off")
    return verdict(problems)


def repo_15(r: Repo) -> Result:
    text = r.read("CONTRIBUTING.md")
    if not text:
        return Result("fail", ["CONTRIBUTING.md missing"])
    problems = [f"CONTRIBUTING.md has no section `{h}`" for h in
                ("## Issues", "## Pull requests", "## License") if h not in text]
    flat = " ".join(text.split()).lower()
    choice = decision(r, CONTRIBUTIONS)
    if choice == "team only" and "pull requests are not accepted" not in flat.replace("**", ""):
        problems.append("CONTRIBUTING.md does not say that pull requests are not accepted for now")
    if choice == "external" and "pull requests are welcome" not in flat:
        problems.append("CONTRIBUTING.md does not invite pull requests")
    return verdict(problems)


def repo_16(r: Repo) -> Result:
    m = re.search(r"^## Contributing\s*$(.*?)(?=^## |\Z)", r.read("README.md"), re.M | re.S)
    if not m:
        return Result("fail", ["README.md has no `## Contributing` section"])
    flat = " ".join(m.group(1).split()).lower()
    problems = [] if "contributing.md" in flat else ["the README's Contributing section does not point to CONTRIBUTING.md"]
    choice = decision(r, CONTRIBUTIONS)
    if choice == "team only" and "pull requests are not accepted yet" not in flat:
        problems.append("the README's Contributing section does not say that pull requests are not accepted yet")
    if choice == "external" and "pull requests are welcome" not in flat:
        problems.append("the README's Contributing section does not invite pull requests")
    return verdict(problems)


def repo_17(r: Repo) -> Result:
    if decision(r, RELEASES) != "release-please":
        return Result("n/a")
    try:
        manifest = json.loads(r.read(".release-please-manifest.json") or "{}")
        config = json.loads(r.read("release-please-config.json") or "{}")
    except json.JSONDecodeError:
        return Result("fail", ["release-please files are not valid JSON"])
    if any(v != "0.0.0" for v in manifest.values()):
        return Result("pass")  # released already: the start version no longer matters
    packages = config.get("packages", {}) or {".": {}}
    return verdict([f"package {path!r} would start at 1.0.0: set \"initial-version\": \"0.1.0\""
                    for path, conf in packages.items()
                    if (conf.get("initial-version") or config.get("initial-version")) != "0.1.0"])


def repo_18(r: Repo) -> Result:
    recorded = project_decision(r, *ADRS)
    if recorded is None and repo_shows(r, "ADRs"):
        return Result("ask", ["not recorded, but the repo has ADRs: record `- ADRs: yes` without asking"])
    if recorded != "yes":
        return Result("n/a")  # no line or `no`: the project keeps no ADRs
    folder = "adr" if r.path("adr").is_dir() else "docs/adr"
    if not r.path(folder).is_dir():
        return Result("fail", ["adr/ missing"])
    return verdict([] if any(p.name.startswith("0000") for p in r.path(folder).iterdir())
                   else [f"{folder}/ has no template (0000-template.md)"])


CHECKS = {name.upper().replace("_", "-"): fn for name, fn in globals().copy().items()
          if re.fullmatch(r"(repo|be|sec|docker|ci|fe)_\d{2}", name)}


# --- House defaults section of AGENTS.md ------------------------------------------------------


@dataclass
class Decision:
    reason: str
    paths: list[str]  # empty: the whole item; otherwise only findings in these paths (globs)


def house_defaults(r: Repo) -> tuple[str | None, dict[str, Decision]]:
    """`- ID: reason` accepts or settles a whole item; `- ID [path, path]: reason` only the
    findings in those paths (globs), so new findings elsewhere still show."""
    m = re.search(r"^## House defaults\s*$(.*?)(?=^## |\Z)", r.read("AGENTS.md"), re.M | re.S)
    if not m:
        return None, {}
    section = re.sub(r"<!--.*?-->", "", m.group(1), flags=re.S)  # examples in comments don't count
    version = re.search(r"checklist (\d+\.\d+)", section)
    decisions = {}
    for d in re.finditer(rf"^\s*[-*]\s*\**({ID_RE})\**(?:\s*\[([^\]]+)\])?\s*[:—–-]\s*(.+)$", section, re.M):
        paths = [p.strip().strip("`") for p in (d.group(2) or "").split(",") if p.strip()]
        decisions[d.group(1)] = Decision(d.group(3).strip(), paths)
    return (version.group(1) if version else None), decisions


def finding_path(detail: str) -> str | None:
    m = re.search(r"([\w./-]+\.\w+):\d+", detail)
    return m.group(1) if m else None


def outside(details: list[str], paths: list[str]) -> list[str]:
    """The findings not covered by a path-scoped decision (findings without a path stay)."""
    keep = []
    for detail in details:
        path = finding_path(detail)
        if not path or not any(fnmatch(path, p) or path.startswith(p.rstrip("/") + "/") for p in paths):
            keep.append(detail)
    return keep


# --- Main -----------------------------------------------------------------------------------


def frontend_item(item: Item) -> bool:
    return item.id.startswith("FE-")


def main() -> int:
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if len(args) != 1:
        print(__doc__, file=sys.stderr)
        return 2
    repo = Repo(Path(args[0]).resolve())
    new_project = "--new" in sys.argv
    full = "--full" in sys.argv  # ignore the settled list: re-judge and re-report everything
    version, items, added, retired = load_checklist()
    checked_against, accepted = house_defaults(repo)

    rows = []
    for item in items:
        if item.scope == "new" and not new_project:
            continue
        if frontend_item(item) and not repo.has_frontend():
            result = Result("n/a")
        else:
            result = CHECKS[item.id](repo)
        status = result.status
        decision = None if full else accepted.get(item.id)
        if decision and decision.paths and status in {"fail", "judge"}:
            result.details = outside(result.details, decision.paths)
            if not result.details:  # everything open lies in the accepted paths
                status = "accepted" if status == "fail" else "settled"
        elif decision:
            met = decision.reason.lower().startswith("met with")  # goal reached with another tool
            status = {"fail": "settled" if met else "accepted", "judge": "settled",
                      "pass": "accepted, no longer needed"}.get(status, status)
            if status in {"accepted", "settled"}:
                result.details = []
        if status == "fail" and "· " in item.tools and any(TOOL_LIST.search(d) for d in result.details):
            result.details.append(UNKNOWN.format(id=item.id))
        rows.append({"id": item.id, "level": item.level, "how": item.how, "status": status,
                     "rule": item.rule, "tools": item.tools, "details": result.details,
                     "reason": accepted[item.id].reason if item.id in accepted else None,
                     "scope": accepted[item.id].paths if item.id in accepted else []})

    known = {i.id for i in items}
    notes = [f"AGENTS.md lists {i}, which was retired from the checklist; remove the line"
             for i in sorted(set(accepted) & retired)]
    notes += [f"AGENTS.md lists unknown item {i}" for i in sorted(set(accepted) - known - retired)]
    if checked_against is None:
        notes.append("AGENTS.md has no '## House defaults' section: first review against the checklist.")
    elif checked_against != version:
        newer = [v for v in added if tuple(map(int, v.split("."))) > tuple(map(int, checked_against.split(".")))]
        new_ids = sorted({i for v in newer for i in added[v]})
        if any(not added[v] for v in newer):  # a version without IDs (the first one) brings all items
            new_ids = ["all items"]
        notes.append(f"Checklist changed since the last review ({checked_against} -> {version}); "
                     f"new or changed items: {', '.join(new_ids) or 'none'}.")

    failing = [row for row in rows if row["status"] == "fail"]
    if "--json" in sys.argv:
        print(json.dumps({"checklist": version, "checked_against": checked_against, "notes": notes,
                          "items": rows}, indent=2, ensure_ascii=False))
    else:
        print(f"House defaults checklist {version} — {repo.root.name}")
        for note in notes:
            print(f"note: {note}")
        # Passed and not applicable items only by ID; the rule text only where something is open.
        for status in ("pass", "n/a"):
            ids = [row["id"] for row in rows if row["status"] == status]
            if ids:
                print(f"{status.upper():<9} {' '.join(ids)}")
        for row in rows:
            if row["status"] in ("pass", "n/a"):
                continue
            closed = row["status"] in ("accepted", "settled")
            print(f"{row['status'].upper():<9} {row['id']:<10} {row['level']:<6} {'' if closed else row['rule']}".rstrip())
            for detail in row["details"]:
                print(f"{'':27}{detail}")
            if row["reason"]:
                where = f" (only {', '.join(row['scope'])})" if row["scope"] else ""
                print(f"{'':27}decided{where}: {row['reason']}")
        counts = {s: sum(1 for row in rows if row["status"] == s)
                  for s in ("pass", "fail", "judge", "ask", "accepted", "settled", "n/a")}
        print("summary: " + ", ".join(f"{n} {s}" for s, n in counts.items()))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
