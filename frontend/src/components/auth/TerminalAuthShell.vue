<script setup lang="ts">
import TerminalStarfield from './TerminalStarfield.vue';

defineProps<{
  title?: string;
  subtitle?: string;
}>();
</script>

<template>
  <main class="auth-terminal relative flex min-h-screen flex-col overflow-hidden bg-[#0a0a0c]">
    <div class="pointer-events-none absolute inset-0 z-0">
      <TerminalStarfield />
    </div>

    <header class="relative z-20 flex shrink-0 items-center justify-between border-b border-[var(--term-line)]/80 px-5 py-3 sm:px-8">
      <div class="flex items-baseline gap-3">
        <span class="text-[11px] tracking-[0.35em] text-[var(--term-muted)]">SPARKORBIT</span>
        <span class="text-[11px] text-[var(--term-line)]">//</span>
        <span class="text-[11px] tracking-[0.2em] text-[var(--term-accent)]">{{ title || '接入门' }}</span>
      </div>
      <p v-if="subtitle" class="hidden text-[10px] tracking-wider text-[var(--term-muted)] sm:block">{{ subtitle }}</p>
    </header>

    <div class="relative z-10 grid min-h-0 flex-1 lg:grid-cols-[minmax(280px,38%)_1fr]">
      <section
        class="relative flex flex-col justify-center px-5 py-10 sm:px-10 lg:border-r lg:border-[var(--term-line)]/70"
      >
        <!-- readability veil over starfield -->
        <div
          class="pointer-events-none absolute inset-0 -z-0 bg-gradient-to-r from-[#0a0a0c]/92 via-[#0a0a0c]/78 to-[#0a0a0c]/25 lg:to-transparent"
          aria-hidden="true"
        />
        <div class="relative z-10">
          <slot />
        </div>
      </section>

      <aside class="relative order-first h-28 overflow-hidden border-b border-[var(--term-line)]/70 lg:order-none lg:h-auto lg:min-h-0 lg:border-b-0">
        <slot name="geometry" />
        <slot name="logs" />
      </aside>
    </div>
  </main>
</template>
