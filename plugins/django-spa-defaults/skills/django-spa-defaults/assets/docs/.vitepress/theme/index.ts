import { h } from 'vue'
import type { Theme } from 'vitepress'
import DefaultTheme from 'vitepress/theme'

import LanguageRedirect from './LanguageRedirect.vue'
import LanguageSwitch from './LanguageSwitch.vue'

export default {
  extends: DefaultTheme,
  enhanceApp({ app }) {
    app.component('LanguageRedirect', LanguageRedirect)
  },
  Layout: () =>
    h(DefaultTheme.Layout, null, {
      'nav-bar-content-after': () => h(LanguageSwitch),
      'nav-screen-content-after': () => h(LanguageSwitch),
    }),
} satisfies Theme
