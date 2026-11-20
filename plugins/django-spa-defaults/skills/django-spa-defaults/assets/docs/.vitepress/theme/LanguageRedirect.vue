<script setup lang="ts">
// The start page /docs/ has no content of its own: it opens the documentation in the
// browser's language (German for any German locale, English otherwise).
import { onMounted } from 'vue'
import { useRouter, withBase } from 'vitepress'

const router = useRouter()

onMounted(() => {
  const lang = navigator.languages.some((l) => l.toLowerCase().startsWith('de')) ? 'de' : 'en'
  router.go(withBase(`/${lang}/`))
})
</script>

<template>
  <div class="language-redirect">
    <a :href="withBase('/de/')" hreflang="de" lang="de">Deutsch</a>
    <a :href="withBase('/en/')" hreflang="en" lang="en">English</a>
  </div>
</template>

<style scoped>
.language-redirect {
  display: flex;
  justify-content: center;
  gap: 32px;
  padding: 96px 24px;
  font-size: 18px;
  font-weight: 600;
}
</style>
