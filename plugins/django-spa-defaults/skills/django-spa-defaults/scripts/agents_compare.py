"""REPO-26: compare a repository's AGENTS.md with the template.

Everything from the first `##` section up to the project's own sections (`## Project`,
`## Glossary`, `## House defaults`) is the shared standard and has to equal the template for the
variants the repository uses. The text before the first section and the project's own sections
are the project's. The template's variant blocks are `<!-- [TAG] -->` ... `<!-- [/] -->` (a block
also ends at the next tag); placeholders like `<Project>` match any text.

Paragraphs (a heading, or a bullet with its continuation lines) are compared, whitespace
normalised. Standard library only.
"""

from __future__ import annotations

import difflib
import re

TAG = re.compile(r"^\s*<!--\s*\[(/?)([A-Z_]*)\]")
PROJECT_OWN = ("Project", "Glossary", "House defaults")
PLACEHOLDER = re.compile(r"<(?:Project|[A-Z][A-Z0-9_]+)>")
MAX_SHOWN = 6


def render(text: str, selected: set[str]) -> list[str]:
    out, current = [], None
    for line in text.splitlines():
        m = TAG.match(line)
        if m:
            current = None if m.group(1) or not m.group(2) else m.group(2)
            continue
        if current is None or current in selected:
            out.append(line)
    return out


def fixed_zone(lines: list[str]) -> list[str]:
    """Lines from the first `## ` heading up to the project's own sections."""
    out, started = [], False
    for line in lines:
        m = re.match(r"^## (.*?)\s*$", line)
        if m and m.group(1) in PROJECT_OWN:
            break
        started = started or bool(m)
        if started:
            out.append(line)
    return out


def paragraphs(lines: list[str]) -> list[str]:
    out: list[str] = []
    open_paragraph = False
    for line in lines:
        if line.lstrip().startswith("<!--"):
            continue
        if not line.strip():
            open_paragraph = False
        elif line.startswith("#"):
            out.append(line.strip())
            open_paragraph = False
        elif line.startswith("- ") or not open_paragraph:
            out.append(line.strip())
            open_paragraph = True
        else:
            out[-1] += " " + line.strip()
    return [re.sub(r"\s+", " ", p) for p in out]


def variants(read, exists, has_docker: bool) -> set[str]:
    chosen = {"BACKEND_DE" if exists("backend/locale/de") else "BACKEND_EN",
              "DOCS" if exists("docs") else "NO_DOCS"}
    package = read("frontend/package.json")
    chosen.add("VUE" if re.search(r'"vue"\s*:', package) else "REACT")
    for tag, present in (("RELEASE_PLEASE", exists("release-please-config.json")), ("ADRS", exists("adr")),
                         ("DOCKER", has_docker)):
        if present:
            chosen.add(tag)
    return chosen


def short(text: str, width: int = 90) -> str:
    return text if len(text) <= width else text[: width - 1] + "…"


def compare(template: str, text: str, selected: set[str]) -> list[str]:
    wanted = paragraphs(fixed_zone(render(template, selected)))
    have = paragraphs(fixed_zone(text.splitlines()))
    patterns = [re.compile("".join(".+?" if PLACEHOLDER.fullmatch(part) else re.escape(part)
                                   for part in re.split(f"({PLACEHOLDER.pattern})", w)) + r"\Z") for w in wanted]
    extra: list[str] = []
    missing: list[str] = []
    j = 0
    for pattern, w in zip(patterns, wanted):
        k = next((i for i in range(j, len(have)) if pattern.match(have[i])), None)
        if k is None:
            missing.append(w)
        else:
            extra += have[j:k]
            j = k + 1
    extra += have[j:]
    problems = []
    for w in missing:
        near = difflib.get_close_matches(w, extra, 1, 0.6)
        if near:
            extra.remove(near[0])
            problems.append(f"changed: `{short(near[0])}` — the template has `{short(w)}`")
        else:
            problems.append(f"missing: `{short(w)}`")
    problems += [f"extra, belongs under `## Project`: `{short(e)}`" for e in extra]
    if len(problems) > MAX_SHOWN:
        problems = problems[:MAX_SHOWN] + [f"… and {len(problems) - MAX_SHOWN} more"]
    return problems
