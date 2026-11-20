import { createHash } from 'node:crypto'
import { mkdirSync, writeFileSync } from 'node:fs'
import { join } from 'node:path'
import { defineConfig, type DefaultTheme } from 'vitepress'

// Served by the app container under /docs/ (docker/app.conf.template).
const base = '/docs/'

// The CSP allows scripts from our own origin only. VitePress inlines two small scripts
// (dark mode, macOS shortcut labels); they move into files that load just as early.
function externalizeInlineScripts(html: string, outDir: string): string {
  return html.replace(/<script( id="[^"]*")?>([\s\S]*?)<\/script>/g, (_, id: string | undefined, code: string) => {
    const name = `inline.${createHash('sha256').update(code).digest('hex').slice(0, 12)}.js`
    mkdirSync(join(outDir, 'assets'), { recursive: true })
    writeFileSync(join(outDir, 'assets', name), code)
    return `<script${id ?? ''} src="${base}assets/${name}"></script>`
  })
}

type Lang = 'de' | 'en'
/** German and English text of one label. */
type Text = Record<Lang, string>
/** A page: its path below the language folder ('' for the index) and its title. */
type Page = [path: string, title: Text]

// Every page exists in de/ and en/ under the same path; only the titles differ.
// A new page gets its entry here (scripts/check-links.mjs fails on a missing counterpart).
const SIDEBAR: { text: Text; pages: Page[] }[] = [
  {
    text: { de: 'Einführung', en: 'Introduction' },
    pages: [
      ['', { de: 'Übersicht', en: 'Overview' }],
      ['getting-started', { de: 'Erste Schritte', en: 'Getting started' }],
    ],
  },
]

const LABELS: Record<Lang, DefaultTheme.Config> = {
  de: {
    outline: { label: 'Auf dieser Seite' },
    docFooter: { prev: 'Zurück', next: 'Weiter' },
    darkModeSwitchLabel: 'Darstellung',
    sidebarMenuLabel: 'Menü',
    returnToTopLabel: 'Nach oben',
    lastUpdated: { text: 'Zuletzt aktualisiert' },
  },
  en: {},
}

const sidebar = (lang: Lang): DefaultTheme.SidebarItem[] =>
  SIDEBAR.map((group) => ({
    text: group.text[lang],
    items: group.pages.map(([path, title]) => ({ text: title[lang], link: `/${lang}/${path}` })),
  }))

export default defineConfig({
  title: '<Project>',
  description: '<Project>: documentation · Dokumentation',
  base,
  cleanUrls: true,
  // Page metadata as a separate script instead of inline: the CSP allows no inline scripts.
  metaChunk: true,
  transformHtml: (html, _id, { siteConfig }) => externalizeInlineScripts(html, siteConfig.outDir),
  // Empty labels hide VitePress' own locale switcher; the theme's LanguageSwitch links to
  // the same page in the other language.
  locales: {
    root: { label: '', lang: 'en-US' },
    de: { label: '', lang: 'de-DE', link: '/de/', themeConfig: { ...LABELS.de, sidebar: sidebar('de') } },
    en: { label: '', lang: 'en-US', link: '/en/', themeConfig: { ...LABELS.en, sidebar: sidebar('en') } },
  },
  themeConfig: {
    search: { provider: 'local' },
  },
})
