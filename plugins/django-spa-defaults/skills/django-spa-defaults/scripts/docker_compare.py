"""DOCKER-12: compare a repository's Docker files with the template.

The template (assets/) carries variant blocks and extension points:

* `# [WSGI]` ... `# [/WSGI]` (also `;` in supervisord.conf): the variants ASGI/WSGI,
  WORKER_SERVICE/WORKER_PROGRAM and BACKUP_JOB/BACKUP_CONTAINER have an explicit end tag and may
  nest; `[A+B]` keeps a block only when both variants apply. The older tags (`[DOCS]`,
  `[BACKEND_DE]`) end at a blank line, the next tag or `[/]`.
* `# --- project: name ---` ... `# --- end ---`: the project's own lines; ignored on both sides.

The template is rendered for the variants the repository uses, comments, blank lines and what
legitimately differs (project name, owner, image versions and digests) are normalised away, and
the remaining lines are compared. A finding is a line that differs, is missing or is extra.
Standard library only.
"""

from __future__ import annotations

import difflib
import re
from pathlib import Path

NEW_TAGS = {"WSGI", "ASGI", "WORKER_SERVICE", "WORKER_PROGRAM", "BACKUP_JOB", "BACKUP_CONTAINER"}
LEGACY_TAGS = {"DOCS", "NO_DOCS", "BACKEND_DE", "BACKEND_EN"}
KNOWN = NEW_TAGS | LEGACY_TAGS
TAG = re.compile(r"^\s*[#;]\s*\[(/?)([A-Z_]+(?:\+[A-Z_]+)*|)\]")
EXT_START = re.compile(r"^\s*[#;] --- project: .+ ---\s*$")
EXT_END = re.compile(r"^\s*[#;] --- end ---\s*$")
MAX_PER_FILE = 6

# Tuning values: the template's numbers are the defaults; a project may choose others. Such a
# difference is shown as a note and does not make DOCKER-12 fail.
SOFT_KEYS = re.compile(r"^(priority|startsecs|startretries|stopwaitsecs)=\S*$")
SOFT_DEFAULTS = re.compile(r"\$\{(WORKER_CONCURRENCY|GUNICORN_WORKERS|WEB_WORKERS|APP_BIND|BACKUP_TIME|BACKUP_KEEP_DAYS):-[^}]*\}")
SOFT_BUILD = re.compile(r"^RUN pnpm (?:run )?build\S*$")

# Old file names that DOCKER-09 reports; their content is still compared, under the new name.
RENAMED = {"nginx-security-headers.conf": "security_headers.conf", "exit_on_fatal.py": "exit-on-fatal",
           "exit-on-fatal.py": "exit-on-fatal", "healthcheck.sh": "healthcheck", "smoke-test.sh": "smoke-test",
           "start-nginx.sh": "start-nginx", "worker.sh": "worker", "supervisord.ini": "supervisord.conf"}


def render(text: str, selected: set[str]) -> list[str]:
    """The template's lines for the selected variants, variant tag lines removed."""
    out: list[str] = []
    stack: list[tuple[str, bool, bool]] = []  # (tag text, explicit end, kept)
    for line in text.splitlines():
        m = TAG.match(line)
        if m:
            closing, names = m.groups()
            if closing:
                for i in range(len(stack) - 1, -1, -1):
                    if (names and stack[i][0] == names) or (not names and not stack[i][1]):
                        del stack[i:]
                        break
                continue
            while stack and not stack[-1][1]:  # a new tag ends an open older-style block
                stack.pop()
            parts = names.split("+")
            kept = all(p in selected or p not in KNOWN for p in parts)
            stack.append((names, parts[0] in NEW_TAGS, kept))
            continue
        if not line.strip():
            while stack and not stack[-1][1]:
                stack.pop()
        if all(k for _, _, k in stack):
            out.append(line)
    return out


def without_extensions(lines: list[str]) -> list[tuple[int, str]]:
    """(line number, line) without the project's own blocks."""
    out, inside = [], False
    for number, line in enumerate(lines, 1):
        if EXT_START.match(line):
            inside = True
        elif EXT_END.match(line):
            inside = False
        elif not inside:
            out.append((number, line))
    return out


def canonical(line: str, project: str, owner: str | None, template: bool) -> str | None:
    s = line.strip()
    if not s or s.startswith(("#", ";")):
        return None
    if template:
        s = re.sub(r"<(?!DIGEST>)[A-Z][A-Z0-9_]*>", "0", s)
    s = re.sub(r"@sha256:[0-9a-f]{4,}", "@<DIGEST>", s)
    if project:
        s = re.sub(rf"(?i)(?<!\w){re.escape(project)}(?!\w)", "<project>", s)
    if owner:
        s = s.replace(owner, "<owner>")
    s = re.sub(r"\b(node|python|postgres|aquasec/trivy|ghcr\.io/astral-sh/uv|redis|valkey):[^\s@\"']+", r"\1:<V>", s)
    s = re.sub(r"\b(ARG (?:PG_MAJOR|SUPERVISOR_VERSION))=\S+", r"\1=<V>", s)
    s = re.sub(r"\b\w+-pgdg\b", "<DEBIAN>-pgdg", s)
    s = re.sub(r"^(add_header (?:Content-Security-Policy|Permissions-Policy)) .*", r"\1 <value>", s)  # the project's
    s = re.sub(r"/api/v\d+/", "/api/", s)  # a versioned API prefix is the project's choice
    s = re.sub(r"probe /api/\S*/me \S+", "probe <ME> <N>", s)  # the auth library decides the path
    s = re.sub(r"location = /api/\S*login\b", "location = <LOGIN>", s)
    return re.sub(r"\s+", " ", s)


def variants(read, exists) -> set[str]:
    """Which variants of the template the repository uses, from what it contains."""
    sup = read("docker/supervisord.conf")
    compose = read("compose.yml")
    dockerfile = read("Dockerfile")
    commands = re.findall(r"^command=(.*)$", sup, re.M)
    uses = lambda name: any(name in c for c in commands)  # noqa: E731
    chosen = {"ASGI" if (uses("uvicorn") and not uses("gunicorn")) else "WSGI"}
    if re.search(r"^  worker:", compose, re.M):
        chosen.add("WORKER_SERVICE")
    elif uses("procrastinate worker"):
        chosen.add("WORKER_PROGRAM")
    chosen.add("BACKUP_CONTAINER" if re.search(r"^  backup:", compose, re.M) else "BACKUP_JOB")
    chosen.add("DOCS" if (exists("docs/package.json") or exists("docs/.vitepress") or " AS docs" in dockerfile) else "NO_DOCS")
    chosen.add("BACKEND_DE" if exists("backend/locale/de") else "BACKEND_EN")
    return chosen


def files_to_compare(chosen: set[str], template_docker: list[str]) -> list[str]:
    files = ["Dockerfile", "compose.yml", "compose.dev.yml", ".dockerignore"]
    only = {"gunicorn.conf.py": "WSGI", "worker": "WORKER_SERVICE", "backup.sh": "BACKUP_CONTAINER"}
    for name in template_docker:
        if name in only and only[name] not in chosen:
            continue
        files.append(f"docker/{name}")
    return files


def softened(line: str) -> str:
    """The line with its tuning value set aside."""
    line = SOFT_KEYS.sub(lambda m: m.group(1) + "=<N>", line)
    line = SOFT_DEFAULTS.sub(lambda m: "${" + m.group(1) + ":-<D>}", line)
    return SOFT_BUILD.sub("RUN pnpm run build", line)


def where_differs(a: str, b: str) -> str:
    """A short view of the first place two lines differ."""
    n = 0
    while n < min(len(a), len(b)) and a[n] == b[n]:
        n += 1
    start = max(0, n - 25)
    return f"`...{a[start:n + 20]}` -> `...{b[start:n + 20]}`"


def is_soft(tag: str, old: list[str], new: list[str]) -> bool:
    if tag == "replace" and len(old) == len(new):
        return all(softened(a) == softened(b) for a, b in zip(old, new))
    return tag in ("insert", "delete") and all(SOFT_KEYS.match(line) for line in old + new)


def compare(assets: Path, read, exists, project: str, owner: str | None) -> tuple[list[str], list[str]]:
    """(differences that count, notes on tuning values that do not)."""
    chosen = variants(read, exists)
    template_docker = sorted(p.name for p in (assets / "docker").iterdir() if p.is_file())
    problems: list[str] = []
    notes: list[str] = []
    for rel in files_to_compare(chosen, template_docker):
        template_path = assets / rel
        if not template_path.is_file():
            continue
        repo_text = read(rel)
        if not repo_text:
            legacy = [old for old, new in RENAMED.items() if rel == f"docker/{new}" and read(f"docker/{old}")]
            if legacy:
                repo_text = read(f"docker/{legacy[0]}")
            else:
                problems.append(f"{rel} is missing")
                continue
        expected = [c for _, line in without_extensions(render(template_path.read_text(encoding="utf-8"), chosen))
                    if (c := canonical(line, project, owner, True)) is not None]
        found = [(n, c) for n, line in without_extensions(repo_text.splitlines())
                 if (c := canonical(line, project, owner, False)) is not None]
        matcher = difflib.SequenceMatcher(None, expected, [c for _, c in found], autojunk=False)
        findings: list[str] = []
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                continue
            if is_soft(tag, expected[i1:i2], [c for _, c in found[j1:j2]]):
                old_line = expected[i1] if tag != "insert" else ""
                new_line = found[j1][1] if tag != "delete" else ""
                notes.append(f"{rel}:{found[j1][0] if tag != 'delete' and j1 < len(found) else '-'}: tuning value differs from the template: "
                             + (where_differs(old_line, new_line) if old_line and new_line
                                else f"`{(old_line or new_line)[:70]}` {'missing' if old_line else 'added'}"))
                continue
            where = found[j1][0] if j1 < len(found) else (found[-1][0] if found else 1)
            if tag == "replace":
                findings.append(f"{rel}:{where}: expected `{expected[i1][:90]}`, found `{found[j1][1][:90]}`"
                                + (f" (and {max(i2 - i1, j2 - j1) - 1} more lines)" if max(i2 - i1, j2 - j1) > 1 else ""))
            elif tag == "delete":
                findings.append(f"{rel}: missing `{expected[i1][:90]}`" + (f" (and {i2 - i1 - 1} more lines)" if i2 - i1 > 1 else ""))
            else:
                findings.append(f"{rel}:{where}: extra `{found[j1][1][:90]}`" + (f" (and {j2 - j1 - 1} more lines)" if j2 - j1 > 1 else ""))
        if findings:
            problems += findings[:MAX_PER_FILE]
            if len(findings) > MAX_PER_FILE:
                problems.append(f"{rel}: {len(findings) - MAX_PER_FILE} more differences")
    return problems, notes
