# Frontend: Vue 3 variant

Read `frontend.md` first; this file only adds what is specific to Vue.

## 1. Scaffolding

```bash
# from the repo root; flags: TypeScript, Router, Pinia, Vitest, ESLint + Prettier (check --help first)
pnpm create vue@latest frontend --typescript --router --pinia --vitest --eslint --prettier --force
cd frontend && pnpm install
pnpm add vue-i18n @vueuse/core @lucide/vue
pnpm add -D @vue/test-utils jsdom eslint-plugin-vuejs-accessibility
```

Plus the shared dependencies from `frontend.md` section 1. Delete the demo components (HelloWorld, TheWelcome, icons, AboutView).

UI library (decided in step 1):
- **shadcn-vue + Tailwind** — custom look, few data-heavy screens: `pnpm add -D tailwindcss @tailwindcss/vite`, then shadcn-vue's current Vite guide (`pnpm dlx shadcn-vue@latest init`) and a starter set (`button input label card sonner`). Components land in `src/components/ui/` — vendored, edit freely.
- **Naive UI** — admin-style apps with many tables, forms and trees: `pnpm add naive-ui`; theme overrides in `src/theme/`, one `NConfigProvider` in `App.vue`. No Tailwind unless the user wants both.

## 2. Directory layout

```
frontend/src/
├── main.ts                 createApp, Pinia, router, i18n, CSRF bootstrap, onUnauthorized
├── App.vue                 <RouterView/> inside the active layout
├── api/                    shared (frontend.md section 3)
├── components/<area>/      shared components by area; ui/ for shadcn-vue
├── composables/            useXyz — state and logic shared by components (lists, forms, live data)
├── layouts/                AppLayout.vue (nav + slot), AuthLayout.vue
├── views/<area>/           one view per route
├── router/index.ts         routes (meta.public) + global auth guard
├── stores/                 Pinia, client state only (auth.ts: current user)
├── utils/                  pure functions, tested on their own (enums.ts, formatting, …)
├── i18n/                   index.ts (createI18n, language detection), locales/{en,de}/
├── theme/                  Naive UI only: theme overrides
└── __tests__/              specs + fakeBackend.ts
```

## 3. Data, state, auth, i18n

- Views load data through composables (`useProjects()`: list, loading, error, reload) built on the `src/api/<area>.ts` functions. Pinia holds client state only.
- `main.ts`: `await ensureCsrf()`, `authStore.fetchMe()`, register `onUnauthorized` (clear the store, `router.push({ name: 'login' })`), then mount. The router guard lets only `meta.public` routes through without `authStore.user`.
- vue-i18n in Composition API mode (`legacy: false`), messages from `src/i18n/locales`.
- Vite plugins as generated (`vue()`, `vueDevTools()`), plus `tailwindcss()` with Tailwind.

## 4. Tests

`@vue/test-utils` with the real router and a fresh Pinia per test; `flushPromises()` after actions that load data. Shared rules in `frontend.md` section 6.

## 5. Lint, type-check and knip

- Readability limits and import boundaries: append the blocks from `frontend.md` section 8 to create-vue's ESLint config; `noUncheckedIndexedAccess` in `tsconfig.app.json`.
- `type-check` is create-vue's `vue-tsc --build`; `build-only` is `vite build`.
- ESLint: create-vue's config (eslint-plugin-vue, `@vue/eslint-config-typescript`, Prettier skip-formatting, the oxlint plugin if offered) — keep it, remove `--fix` from the `lint` script, and raise it:
  - `pluginVue.configs['flat/strongly-recommended']` instead of `flat/essential` (declared emits, default props and other readability rules; Prettier handles the formatting ones);
  - `...pluginVueA11y.configs['flat/recommended']` from `eslint-plugin-vuejs-accessibility` (alt texts, labelled form fields, keyboard access);
  - in the `project/readability` block: `'vue/no-v-html': 'error'` (no unescaped HTML — XSS; a real exception gets `eslint-disable-next-line vue/no-v-html -- reason`) and `'vue/no-unused-properties': ['error', { groups: ['props', 'data', 'computed', 'methods', 'setup'] }]`.
- `tsconfig.app.json`: `"vueCompilerOptions": { "strictTemplates": true }` — unknown components, props, events and directives in templates become type errors.
- knip: entry `src/main.ts`, project `src/**/*.{ts,vue}`, ignore `src/components/ui/**` and `src/api/schema.d.ts`.
- Coverage excludes: `src/components/ui/**`, `src/api/schema.d.ts`, `src/main.ts`, `**/*.d.ts`.
- VS Code: keep `vue.volar` in `.vscode/extensions.json` (`[VUE]` line).
