# Checking an existing repository

Read this when the user wants an existing repo checked or brought in line. `SKILL.md` has the conventions and the tools check.

Don't scaffold over an existing repo. Bring it in line against `references/checklist.md` — the versioned list of items that make up the house defaults — and nothing else. The other references describe how to build things; here they are only a lookup for fixing an item. A review of an unchanged repo against an unchanged checklist must come out the same every time, and "nothing to do" is a normal result.

1. **Run the script**: `uv run --no-project --python ">=3.11" <skill-dir>/scripts/check_repo.py <repo>`. It decides every `auto` item, skips items for new projects only, and applies the repo's `## House defaults` section in AGENTS.md: accepted deviations and settled judgements are not reported again. Take its verdicts as they are — don't re-argue a pass or add findings to an item.
2. **Settle the `ask` items** — project decisions AGENTS.md doesn't record yet in the `- Releases: …` / `- Contributions: …` lines (prose elsewhere in AGENTS.md doesn't count; the script needs the line). Where the script says what the repo already shows (release-please set up, CONTRIBUTING refusing pull requests), record exactly that without asking and mention it in the report — never ask what the repo already answers. Ask only the rest, with the examples from `references/repo-files.md` section 4. ADRs are never asked: no line means no ADRs. Then rerun the script.
3. **Tools**: the checklist's Tools column names the recommended tool (bold) and alternatives that pass. When fixing an item, keep a tool the repo already uses if it is listed or reaches the goal; bring in the recommended one only where nothing is set up yet. Never report a passing alternative or suggest switching. A tool the script doesn't know: check that it reaches the goal, then record `- ID: met with <tool>` (the script reports the item as settled).
4. **Judge the open `judge` items** from the candidate lines the script lists, by the item's criterion only. A finding needs a clear violation; when in doubt, it passes. Something that breaks the criterion for a stated, good reason (a comment in the code, an ADR) is not a pass: report it as a decision to record, with the reason, so the next run doesn't judge it again and maybe differently.
5. **Observations outside the checklist**: only a real bug or security risk you came across, at most three, marked as observations. No style remarks, no "could also" suggestions.
6. **Report** in the user's language:
   - first line: the plugin version, open items (must / should, judge findings included, so the numbers add up), accepted and settled counts;
   - the open items, `must` first, each with the script's details and the effort (cheap and safe / needs care — data migrations, a CI or framework switch);
   - judge findings, then observations;
   - if nothing is open: "Meets the house defaults (django-spa-defaults X) — nothing to do." and stop there.
   The script's notes say when the checklist changed since the last review; then name the new items.
7. **Ask per open item**: fix it, or accept it as a deviation with a reason. Write the decisions into AGENTS.md's `## House defaults` section and set "Checked against django-spa-defaults X (date)" (X: the version at the top of the checklist):
   - `- ID: decision and reason` for the whole item (settled judge items the same way);
   - `- ID [path, path]: decision and reason` when only some places are exceptions (e.g. a generic CRUD layer) — findings elsewhere keep showing;
   - something that can't be fixed in one go (coverage, many endpoints to move) is recorded as a deviation with today's floor and the plan; once it passes, the script reports "accepted, no longer needed" — then delete the line;
   - lines for items the script reports as retired are deleted.
   A finding the user declines to fix and doesn't want to record stays open — say so once, don't argue.
8. Change only what the user agreed to, one area at a time, and run the repo's checks after each. Rerun the script at the end. Commit messages, PR titles and descriptions say what changed in the project's own terms (`fix: deny framing of the app`, `ci: install pnpm without corepack`) — never the checklist, its version, item IDs or this skill.

`--full` ignores the recorded list and re-checks everything; use it only when the user asks for a full re-review. `--json` gives the result for further processing.

**Maintaining the checklist**: its version is the plugin's version — bump `Version:` at the top of the checklist together with `.claude-plugin/plugin.json` (and the marketplace entry); only a release that changes items gets a changelog line. items name a goal; tools go in the Tools column as examples (recommended first). A new, stricter or different rule gets a new ID; a rule that only widens (more tools pass, nothing that passed fails) keeps its ID. Either way it gets a changelog line naming it, and a version bump; `check_repo.py` gets the matching check (or the item is `judge`). Each item is one decision, so accepting it can't hide an unrelated problem. Without a version bump, repos reviewed before don't see the rule.
