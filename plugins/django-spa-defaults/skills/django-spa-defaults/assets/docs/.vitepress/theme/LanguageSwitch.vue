<script setup lang="ts">
// Links to the same page in the other language: every page exists under de/ and en/
// with the same path. VitePress' own switcher would list every area, so it is hidden.
import { computed } from 'vue'
import { useData, withBase } from 'vitepress'

const { page } = useData()

const LANGS = [
  { code: 'de', label: 'Deutsch', short: 'DE' },
  { code: 'en', label: 'English', short: 'EN' },
]

/** de/it/requests.md → ['de', 'it/requests']; null outside the language folders. */
const current = computed(() => {
  const match = /^(de|en)\/(.*?)(index)?\.md$/.exec(page.value.relativePath)
  return match ? { lang: match[1], rest: match[2] } : null
})
</script>

<template>
  <nav v-if="current" class="language-switch" aria-label="Sprache · Language">
    <template v-for="lang in LANGS" :key="lang.code">
      <span v-if="lang.code === current.lang" class="active" :title="lang.label">{{ lang.short }}</span>
      <a v-else :href="withBase(`/${lang.code}/${current.rest}`)" :hreflang="lang.code" :lang="lang.code" :title="lang.label">
        {{ lang.short }}
      </a>
    </template>
  </nav>
</template>

<style scoped>
.language-switch {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-left: 12px;
  font-size: 13px;
  font-weight: 600;
}
.language-switch > * {
  padding: 2px 6px;
  border-radius: 4px;
}
.language-switch a {
  color: var(--vp-c-text-2);
}
.language-switch a:hover {
  color: var(--vp-c-brand-1);
}
.language-switch .active {
  color: var(--vp-c-text-1);
  background: var(--vp-c-default-soft);
}
</style>
