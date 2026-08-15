<script setup lang="ts">
import MarkdownIt from 'markdown-it';
import hljs from 'highlight.js';
import 'highlight.js/styles/github-dark.css';
import { computed } from 'vue';

const props = withDefaults(
  defineProps<{
    content?: string;
    class?: string;
  }>(),
  { content: '', class: '' },
);

function highlightCode(str: string, lang: string): string {
  if (lang && hljs.getLanguage(lang)) {
    try {
      return `<pre class="hljs rounded-lg p-3 overflow-x-auto"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`;
    } catch {
      /* fallthrough */
    }
  }
  const escaped = str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;');
  return `<pre class="hljs rounded-lg p-3 overflow-x-auto"><code>${escaped}</code></pre>`;
}

const md = new MarkdownIt({
  html: false,
  linkify: true,
  breaks: true,
  highlight: highlightCode,
});

const html = computed(() => md.render(props.content || ''));
</script>

<template>
  <div class="prose prose-invert max-w-none text-sm leading-7 text-slate-200" :class="class" v-html="html" />
</template>

<style scoped>
:deep(h1) {
  font-size: 1.25rem;
  font-weight: 600;
  color: #f8fafc;
  margin: 0.75rem 0 0.5rem;
}
:deep(h2) {
  font-size: 1.05rem;
  font-weight: 600;
  color: #e2e8f0;
  margin: 0.75rem 0 0.4rem;
}
:deep(ul) {
  list-style: disc;
  padding-left: 1.25rem;
}
:deep(ol) {
  list-style: decimal;
  padding-left: 1.25rem;
}
:deep(code) {
  font-size: 0.85em;
  background: rgba(255, 255, 255, 0.06);
  padding: 0.1rem 0.35rem;
  border-radius: 0.25rem;
}
:deep(a) {
  color: #7dd3fc;
}
</style>
