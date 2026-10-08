<template>
  <div class="md-content" v-html="html"></div>
</template>

<script setup>
import { computed } from 'vue'
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js/lib/common'
import 'highlight.js/styles/github-dark.css'

const props = defineProps({ content: { type: String, default: '' } })

const md = new MarkdownIt({
  html: false, // 安全：禁用内嵌 HTML
  linkify: true,
  highlight(code, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre><code class="hljs">${hljs.highlight(code, { language: lang }).value}</code></pre>`
      } catch { /* fallthrough */ }
    }
    return `<pre><code class="hljs">${md.utils.escapeHtml(code)}</code></pre>`
  },
})

const html = computed(() => md.render(props.content))
</script>
