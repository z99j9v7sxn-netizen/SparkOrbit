<script setup lang="ts">
withDefaults(
  defineProps<{
    title: string;
    subtitle?: string;
    accent?: 'cyan' | 'violet' | 'neon';
  }>(),
  { accent: 'cyan' },
);
</script>

<template>
  <header class="mb-5 flex flex-wrap items-end justify-between gap-3">
    <div class="min-w-0">
      <nav class="flex items-center gap-1.5 text-[11px] text-t-3" aria-label="面包屑">
        <span>教师工作台</span>
        <svg viewBox="0 0 16 16" class="h-2.5 w-2.5" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
          <path d="m6 4 4 4-4 4" />
        </svg>
        <span class="text-t-2">{{ title }}</span>
      </nav>
      <h2 class="mt-1.5 flex items-center gap-2 text-xl font-semibold tracking-tight text-t-1">
        <span class="orb-accent" :class="accent !== 'cyan' ? `orb-accent--${accent}` : ''" aria-hidden="true" />
        {{ title }}
      </h2>
      <p v-if="subtitle" class="mt-1 text-xs leading-relaxed text-t-2">{{ subtitle }}</p>
    </div>
    <div v-if="$slots.actions" class="flex flex-wrap items-center gap-2">
      <slot name="actions" />
    </div>
  </header>
</template>
