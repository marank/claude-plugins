# Frontend reference (shared by Vue and React)

What every frontend of this stack has in common. The framework-specific parts — scaffolding, UI library, directory layout, data loading, state, i18n wiring, test library, lint and type-check setup — are in `frontend-vue.md` or `frontend-react.md` (step 1 decides). Read this file first, then the variant.

## Contents
1. Package manager and versions
2. Dev port and proxy
3. API client, types and enums
4. Auth flow
5. Translations (English + German)
6. Tests
7. Scripts and quality gates
8. Readability limits

## 1. Package manager and versions

pnpm is the package manager — never npm or yarn in the frontend (no `package-lock.json`; the `preinstall` script refuses other managers). All packages are installed without version specifiers so pnpm resolves the newest release today, and `package.json` gets `"license": "<LICENSE_ID>"` (proprietary: `"UNLICENSED"`) and a `packageManager` field with the researched pnpm version — the only place that version lives (Dockerfile and CI read it).

Before running a scaffolder, check its current flags (`… --help`) — flag names drift between releases, and guessing them is the usual reason scaffolding goes interactive and hangs. Delete the demo components and assets the scaffolder generates.

Shared dependencies for both variants:

```bash
pnpm add openapi-fetch
pnpm add -D openapi-typescript
# quality gates (setup in ci.md): oxlint, knip, size-limit, coverage
pnpm add -D oxlint knip size-limit @size-limit/file @vitest/coverage-v8 prettier jscpd
# lint rules that keep checks honest and tests real (section 8)
pnpm add -D eslint-plugin-sonarjs @eslint-community/eslint-plugin-eslint-comments @vitest/eslint-plugin
```

Fonts and icons are bundled (`@fontsource-variable/*`, Lucide for the framework), never loaded from a CDN — the CSP allows our origin only.

## 2. Dev port and proxy

Every project gets its own dev port (`<DEV_PORT>`, decided in step 1), so several projects run side by side; the backend stays on 8000. Add this `server` block to the generated `vite.config.ts` (the plugins are the variant's):

```ts
const backend = process.env.VITE_BACKEND_URL ?? 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [/* the variant's plugins, as generated */],
  resolve: { alias: { '@': fileURLToPath(new URL('./src', import.meta.url)) } },
  server: {
    port: <DEV_PORT>,
    strictPort: true,
    proxy: {
      '/api': { target: backend },
      '/django-admin': { target: backend },
      '/django-static': { target: backend },
    },
  },
})
```

Don't set `changeOrigin: true`: Django must see the browser's Host (`localhost:<DEV_PORT>`) so the CSRF origin check matches.

## 3. API client, types and enums

Plain TypeScript, identical in both variants.

The schema lives at `frontend/openapi.json`, written by the backend's export command (backend.md); `pnpm api:types` turns it into `src/api/schema.d.ts`. CI checks both are up to date. **The generated schema is the only source of API types** — nothing hand-written, no parallel `types/` folder.

`src/api/types.ts`:

```ts
import type { components } from './schema'

/** Payload types: Schemas['ProjectOut'], Schemas['ProjectIn'], Schemas['ProjectStatus'], … */
export type Schemas = components['schemas']
```

`src/utils/enums.ts` — every value of a generated enum, checked against the backend:

```ts
/**
 * Every value of a generated enum, in the order given. Written as the keys of a record, so the
 * type check fails when the backend adds a value that is missing here (or drops one still listed).
 * Pass the enum type explicitly: allValues<Schemas['ProjectStatus']>({ open: true, done: true }).
 */
export const allValues = <T extends string>(values: Record<T, true>): T[] => Object.keys(values) as T[]
```

Use it for filters, selects and status legends, so a new backend value can't silently go missing in the UI.

`src/api/client.ts` — openapi-fetch checks paths, params and responses against the schema; the middleware sends the CSRF token:

```ts
import createClient, { type Middleware } from 'openapi-fetch'
import type { paths } from './schema'

const SAFE = new Set(['GET', 'HEAD', 'OPTIONS'])

export function getCsrfToken(): string | undefined {
  return document.cookie.split('; ').find((c) => c.startsWith('csrftoken='))?.split('=')[1]
}

export async function ensureCsrf(): Promise<void> {
  if (!getCsrfToken()) await fetch('/api/auth/csrf', { credentials: 'same-origin' })
}

const csrf: Middleware = {
  onRequest({ request }) {
    const token = getCsrfToken() // re-read every time: Django rotates it on login
    if (!SAFE.has(request.method) && token) request.headers.set('X-CSRFToken', token)
    return request
  },
}

export const api = createClient<paths>({ baseUrl: '', credentials: 'same-origin' })
api.use(csrf)
```

Add a second middleware that sends `Accept-Language` with the current UI language and, on 401 (Ninja) / 403 without session (DRF), calls an `onUnauthorized` callback the app registers at start (the variant resets its auth state there and routes to the login page) — except for `/api/auth/me` during boot. Check the openapi-fetch docs for the current middleware signature.

Components never call `api` directly. Each area has a module with one function per endpoint, which unwraps the result and throws an `ApiError` (status, message, field errors) on failure:

```ts
// src/api/projects.ts
import { api, unwrap } from './client'
import type { Schemas } from './types'

export const listProjects = () => unwrap(api.GET('/api/projects'))
export const updateProject = (id: string, body: Schemas['ProjectPatch']) =>
  unwrap(api.PATCH('/api/projects/{project_id}', { params: { path: { project_id: id } }, body }))
```

How views load data through these functions is the variant's business (composables in Vue, TanStack Query hooks in React).

## 4. Auth flow

- Before the app mounts: `await ensureCsrf()`, then load `/api/auth/me` (401 → logged out).
- Routes are protected by default; only routes marked public (login) are reachable without a user.
- Login POSTs `/api/auth/login`. Django rotates the CSRF token on login — re-read the cookie per request (the middleware does), never cache it.
- The login page honours `?next=`: only a same-origin path (starts with `/`, not `//`) is followed; a path the SPA doesn't own (e.g. `/django-admin/…`) is opened with a full page load (`window.location.assign`), everything else through the router.
- Start with the areas `auth` (login page) and `home` (shows the logged-in user), so the path SPA → nginx/Vite → Django → session works from day one.

## 5. Translations (English + German)

Every project ships English and German (more only if step 1 says so).

- `src/i18n/locales/en/<area>.ts` and `de/<area>.ts` (one file per area, `index.ts` merging them); keys grouped by area (`projects.list.title`). No hardcoded user-facing strings in components — `t('…')` everywhere, `aria-label`s included.
- A unit test asserts that `en` and `de` have exactly the same keys, so a forgotten translation fails `pnpm check`.
- Language: a saved choice, else the browser's language if offered, else English; sent as `Accept-Language` so backend messages match.
- Labels for enum values come from `allValues` lists plus ``t(`enums.projectStatus.${value}`)``.

## 6. Tests

Behaviour, not implementation: render views with the router and the app's providers, click and type like a user, then assert what is shown and which requests went out. A small fake backend (`src/__tests__/fakeBackend.ts`) stubs `fetch`, routes by method + path, records requests and answers with fixtures typed by `Schemas[...]` that look like what the backend really sends. Assert state through roles, `aria-*` and `data-*` attributes, not CSS classes.

Coverage gate 90/90/85/85 (lines/statements/functions/branches) in the Vitest config (ci.md section 4).

## 7. Scripts and quality gates

The full script set (`preinstall`, `check`, `size`, `check:licenses`, `api:types`, …) is in ci.md section 4; the variant file says which scaffolder scripts it maps to. Commit `openapi.json` and `src/api/schema.d.ts` so `pnpm build` in Docker doesn't need a running backend.

pnpm may block dependency build scripts (e.g. esbuild) until approved; allow the ones the toolchain needs (`pnpm approve-builds`, stored in `pnpm-workspace.yaml`) and commit `pnpm-workspace.yaml`, so `pnpm install --frozen-lockfile` in Docker and CI doesn't skip them. Approve in `allowBuilds` (`esbuild: true`), which replaced `onlyBuiltDependencies`.

Two pnpm defaults are supply-chain protection; leave them on (FE-24): `minimumReleaseAge` (1440 minutes: a version younger than a day is not installed, transitive dependencies included) and `strictDepBuilds` (an unreviewed build script fails the install). A dependency that needs an urgent fix inside the window goes into `minimumReleaseAgeExclude`; don't set the age to 0. Longer (say 3 days = `4320`) is stricter, but with an explicit value `minimumReleaseAgeStrict` defaults to true and resolution fails when no version in the range is old enough, so only raise it knowingly. Settings per pnpm.io/settings (checked 2026-11-23).

## 8. Readability limits

Limits on tangle, not on length: a long form or table component is fine, a function with twenty branches or five levels of nesting is not, and neither is shared code that reaches into a page. Append to the scaffolder's ESLint flat config (`eslint.config.ts`), keeping its own blocks — at the very end, after `eslint-plugin-oxlint` too, which would otherwise switch these rules off in favour of oxlint's defaults:

```ts
import sonarjs from 'eslint-plugin-sonarjs'
import comments from '@eslint-community/eslint-plugin-eslint-comments'
import vitest from '@vitest/eslint-plugin'

const apiClient = { group: ['@/api/client', '**/api/client'], message: 'Call the area modules in src/api/<area>.ts.' }
const pages = { group: ['@/views/*', '@/pages/*', '@/features/*', '**/views/*', '**/pages/*', '**/features/*'], message: 'Shared code must not depend on a page or feature.' }
// utils may still import the generated payload types (@/api/types).
const impure = { group: ['@/components/*', '**/components/*', '@/api/*', '!@/api/types'], message: 'utils stay pure: no components, no API calls.' }

export default [
  // …the generated config…
  // No silenced checks: every disable names its rules and says why; unused ones fail.
  { name: 'project/linter', linterOptions: { reportUnusedDisableDirectives: 'error' } },
  {
    name: 'project/no-silencing',
    files: ['src/**/*.{ts,tsx,vue}'],
    plugins: { '@eslint-community/eslint-comments': comments },
    rules: {
      '@eslint-community/eslint-comments/no-unlimited-disable': 'error',
      '@eslint-community/eslint-comments/require-description': 'error',
      '@typescript-eslint/ban-ts-comment': ['error', { 'ts-expect-error': 'allow-with-description' }],
    },
  },
  // Tests that test: every test asserts, no `.only` or skipped test is committed.
  {
    name: 'project/tests',
    files: ['src/**/*.{test,spec}.{ts,tsx}'],
    plugins: { vitest },
    rules: {
      'vitest/expect-expect': 'error',
      'vitest/no-focused-tests': 'error',
      'vitest/no-disabled-tests': 'error',
    },
  },
  {
    name: 'project/readability',
    files: ['src/**/*.{ts,tsx,vue}'],
    plugins: { sonarjs },
    rules: {
      complexity: ['error', 15],
      'sonarjs/cognitive-complexity': ['error', 15],
      'max-depth': ['error', 4],
      '@typescript-eslint/no-unnecessary-condition': 'error',
      '@typescript-eslint/no-floating-promises': 'error',
      '@typescript-eslint/no-misused-promises': 'error',
      '@typescript-eslint/switch-exhaustiveness-check': 'error',
      '@typescript-eslint/prefer-nullish-coalescing': 'error',
      'no-restricted-imports': ['error', { patterns: [apiClient] }],
    },
  },
  // Later blocks replace the rule's options, so each lists every pattern that applies.
  { name: 'project/api', files: ['src/api/**'], rules: { 'no-restricted-imports': 'off' } },
  {
    name: 'project/shared',
    files: ['src/components/**', 'src/composables/**', 'src/hooks/**', 'src/queries/**'],
    rules: { 'no-restricted-imports': ['error', { patterns: [apiClient, pages] }] },
  },
  {
    name: 'project/utils',
    files: ['src/utils/**'],
    rules: { 'no-restricted-imports': ['error', { patterns: [apiClient, pages, impure] }] },
  },
]
```

`sonarjs/cognitive-complexity` needs `eslint-plugin-sonarjs` (`pnpm add -D eslint-plugin-sonarjs`); it measures how hard a function is to follow — nesting costs more than a flat list of cases. `no-unnecessary-condition` reports checks the types make pointless (`if (user)` when `user` can't be null) and needs type-aware linting: Vue — `vueTsConfigs.recommendedTypeChecked` instead of `vueTsConfigs.recommended` in `defineConfigWithVueTs`; React — `tseslint.configs.recommendedTypeChecked` with `languageOptions: { parserOptions: { projectService: true, tsconfigRootDir: import.meta.dirname } }`. The other type-aware rules: `no-floating-promises` and `no-misused-promises` report promises nobody awaits or catches (errors would vanish), `switch-exhaustiveness-check` makes a `switch` over a union handle every member (a new API enum value then fails the build, like `allValues`), `prefer-nullish-coalescing` asks for `??` instead of `||`, so `0` and `""` aren't replaced by the default. Delete an unnecessary check rather than disabling the rule; keep one only where data comes from outside the types, with an `eslint-disable-next-line` and the reason.

The `no-silencing` block is what keeps AI-written code honest: a red check gets fixed, not switched off. `eslint-disable-next-line rule -- reason` and `@ts-expect-error reason` stay possible where the reason is real. Duplicated code (copy-paste instead of reusing a helper) is caught by jscpd across frontend and backend (`frontend/.jscpd.json` from the assets: at most 3 % duplicated, tests, migrations and vendored UI excluded), run as `check:duplication` in `pnpm check`.

Deliberately not used: `max-lines`, `max-lines-per-function`, `max-statements`, `max-params` — they force splits that make code harder to follow. In `tsconfig.app.json` set `"noUncheckedIndexedAccess": true` (index access may be `undefined` until checked); in a new project it costs little and catches real bugs.

