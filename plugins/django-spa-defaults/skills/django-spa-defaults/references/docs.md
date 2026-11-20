# Documentation (VitePress, German + English)

Only when step 1 decided on docs (default for apps with end users or operators; small internal tools may live with README + CONTRIBUTING). Without docs: delete every `[DOCS]` block (build.yaml, dependabot.yml, Dockerfile, app.conf.template, tasks.json, AGENTS.md) and skip this file.

## Files (copy `assets/docs/`)

| File | Purpose |
|------|---------|
| `docs/.vitepress/config.mts` | base `/docs/`, clean URLs, one locale per language with its own sidebar (`SIDEBAR`: German and English title per page), inline scripts moved into files for the CSP |
| `docs/.vitepress/theme/` | default theme + `LanguageSwitch` (same page in the other language) and `LanguageRedirect` (start page → `/de/` or `/en/` by browser language) |
| `docs/scripts/check-links.mjs` | after the build: anchors exist, every page has its counterpart in the other language |
| `docs/index.md`, `docs/{de,en}/index.md`, `getting-started.md` | starting pages; replace the `<…>` text with real content |
| `docs/package.json` | `build` = `vitepress build && node scripts/check-links.mjs .`; `packageManager` = the frontend's pnpm |

Then `pnpm add -D vitepress` in `docs/` (newest stable; check whether it still pins an outdated Vite and override it in `pnpm-workspace.yaml` if that Vite gets no security fixes), and commit `pnpm-lock.yaml` and `pnpm-workspace.yaml`.

## Structure and rules

- Every page exists under the same path in `docs/de/` and `docs/en/`; file and folder names in English. The build fails on a missing counterpart.
- Areas by audience once there is more than a handful of pages (e.g. `users/`, `admins/`, `operations/` for installation, configuration, backups, `development/` for contributors). An area that must stay shareable gets a rule in `check-links.mjs` that it never links into an internal one.
- `operations/configuration` lists every environment variable of `.env.example`; a new variable gets its row there in both languages.
- Professional and direct, no filler. Use the exact UI labels from `frontend/src/i18n/locales/{de,en}`. Edge cases go into `::: info` boxes on the feature's page.
- Served by nginx from the image under `/docs/` (Dockerfile stage `docs`, location in `app.conf.template`), with the same CSP as the SPA.
