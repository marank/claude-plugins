# Frontend: React variant

Read `frontend.md` first; this file only adds what is specific to React. The counterparts to the Vue variant: TanStack Query instead of composables for server data, React state/context instead of Pinia, react-i18next instead of vue-i18n, Testing Library instead of `@vue/test-utils`.

## 1. Scaffolding

```bash
# from the repo root (check `pnpm create vite@latest --help` for the current template names)
pnpm create vite@latest frontend --template react-ts
cd frontend && pnpm install
pnpm add react-router @tanstack/react-query i18next react-i18next lucide-react
pnpm add -D vitest jsdom @testing-library/react @testing-library/user-event @testing-library/dom \
  eslint-config-prettier eslint-plugin-oxlint eslint-plugin-jsx-a11y @eslint-react/eslint-plugin
```

Plus the shared dependencies from `frontend.md` section 1. Delete the demo (`App.css`, the counter, `src/assets/react.svg`, `public/vite.svg`). Keep `StrictMode`. If the template offers the React Compiler, keep its default.

UI library (decided in step 1):
- **shadcn/ui + Tailwind** — custom look, few data-heavy screens: `pnpm add -D tailwindcss @tailwindcss/vite`, then shadcn/ui's current Vite guide (`pnpm dlx shadcn@latest init`) and a starter set (`button input label card sonner`). Components land in `src/components/ui/` — vendored, edit freely.
- **Mantine** — admin-style apps with many tables, forms and dates: `@mantine/core @mantine/hooks` (plus `@mantine/dates`, `@mantine/form` when needed) and the PostCSS setup from Mantine's current Vite guide; theme in `src/theme/`, one `MantineProvider` in `main.tsx`. Mantine writes its CSS variables into a `<style>` element, which the CSP's `style-src 'unsafe-inline'` already allows.

## 2. Directory layout

```
frontend/src/
├── main.tsx                ensureCsrf, providers (QueryClient, i18n, UI), RouterProvider, onUnauthorized
├── router.tsx              createBrowserRouter: public routes + a RequireAuth layout route around the rest
├── api/                    shared (frontend.md section 3)
├── queries/<area>.ts       TanStack Query hooks per area: query keys, useXyz(), useUpdateXyz()
├── components/<area>/      shared components by area; ui/ for shadcn/ui
├── hooks/                  other reusable hooks (not data loading)
├── layouts/                AppLayout.tsx (nav + <Outlet/>), AuthLayout.tsx
├── pages/<area>/           one page component per route
├── utils/                  pure functions, tested on their own (enums.ts, formatting, …)
├── i18n/                   index.ts (i18next init, language detection, typed keys), locales/{en,de}/
├── theme/                  Mantine only: theme
└── __tests__/              specs, fakeBackend.ts, renderWithProviders.tsx
```

## 3. Data, state, auth, i18n

- **Server data only through TanStack Query.** Each area has `src/queries/<area>.ts` with a query-key factory (`projectKeys.all`, `projectKeys.detail(id)`) and hooks on top of the `src/api/<area>.ts` functions; mutations invalidate the affected keys. No `useEffect` + `fetch` for loading data.
- **Client state:** component state and context. Add a store library (Zustand) only when real global client state appears, and note the decision in AGENTS.md.
- **Auth:** `useMe()` is a query on `['auth', 'me']` (`null` when logged out). `main.tsx`: `await ensureCsrf()`, prefetch `me`, register `onUnauthorized` (`queryClient.setQueryData(['auth', 'me'], null)`, `router.navigate('/login')`), then render. `RequireAuth` renders `<Outlet/>` for a user and `<Navigate to="/login" replace/>` otherwise.
- **i18n:** react-i18next with the resources from `src/i18n/locales`; declare `CustomTypeOptions` with the English resources so `t('…')` keys are type-checked.
- Vite plugins as generated (`react()`), plus `tailwindcss()` with Tailwind. The React plugin's dev-only inline preamble doesn't matter for the CSP: production is served by nginx without it.

## 4. Tests

Vitest with `environment: 'jsdom'` (in `vite.config.ts` or `vitest.config.ts`). `renderWithProviders(ui, { route })` builds a fresh `QueryClient` (`retry: false`) and a memory router per test; interact with `userEvent`, find with `screen.getByRole`/`findByRole` — Testing Library's role queries match the rule to assert through roles and `aria-*`. Shared rules in `frontend.md` section 6.

## 5. Lint, type-check and knip

- Readability limits and import boundaries: append the blocks from `frontend.md` section 8 to create-vite's ESLint config; `noUncheckedIndexedAccess` in `tsconfig.app.json`.
- Scripts: split create-vite's `build` (`tsc -b && vite build`) into `type-check` = `tsc -b`, `build-only` = `vite build`, `build` = `pnpm type-check && pnpm build-only`; add `test:unit` = `vitest`.
- ESLint: create-vite's config (typescript-eslint, `eslint-plugin-react-hooks`, `eslint-plugin-react-refresh`) plus `eslint-config-prettier` and `eslint-plugin-oxlint` after them, so ESLint skips what oxlint checks, and the readability blocks of `frontend.md` section 8 at the very end. The hooks rules are errors, not warnings, from `reactHooks.configs.flat.recommended` of a current `eslint-plugin-react-hooks` — it includes the React Compiler's rules (no mutation during render and the like). Add:
  - `jsxA11y.flatConfigs.recommended` from `eslint-plugin-jsx-a11y` (alt texts, labelled form fields, keyboard access);
  - from `@eslint-react/eslint-plugin` only these rules (names as in its current docs): `dom/no-dangerously-set-innerhtml` (no unescaped HTML — XSS; a real exception gets `eslint-disable-next-line … -- reason`), `no-leaked-conditional-rendering` (`{count && <List/>}` renders "0"; type-aware), `no-nested-component-definitions` (a component defined inside another loses its state on every render), `no-array-index-key`.
- Prettier: create-vite writes no config; add a `.prettierrc.json` (e.g. `{ "semi": false, "singleQuote": true, "printWidth": 100 }`, as create-vue does for Vue) so `format:check` has rules.
- knip: entry `src/main.tsx`, project `src/**/*.{ts,tsx}`, ignore `src/components/ui/**` and `src/api/schema.d.ts`.
- Coverage excludes: `src/components/ui/**`, `src/api/schema.d.ts`, `src/main.tsx`, `**/*.d.ts`.
- VS Code: drop the `[VUE]` line (`vue.volar`) from `.vscode/extensions.json`.
