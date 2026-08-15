<script setup lang="ts">
import { VAULT_SECTIONS, type VaultSectionId } from './sections';

defineProps<{
  modelValue: VaultSectionId;
  counts: Record<string, number>;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', id: VaultSectionId): void;
}>();
</script>

<template>
  <nav class="flex h-full flex-col gap-0.5 overflow-y-auto p-2" aria-label="知识库分区">
    <p class="mb-1 px-2 text-[10px] font-semibold uppercase tracking-[0.2em] text-[rgb(var(--lz-accent-bright)/0.7)]">分区</p>
    <button
      v-for="s in VAULT_SECTIONS"
      :key="s.id"
      type="button"
      class="flex w-full items-center gap-2 rounded-xl px-2.5 py-2 text-left transition"
      :class="
        modelValue === s.id
          ? 'bg-[rgb(var(--lz-accent)/0.25)] text-white ring-1 ring-[rgb(var(--lz-accent)/0.4)]'
          : 'text-slate-300 hover:bg-white/5 hover:text-white'
      "
      @click="emit('update:modelValue', s.id)"
    >
      <img class="h-4 w-5 shrink-0 object-contain" :src="s.icon" alt="" aria-hidden="true" />
      <span class="min-w-0 flex-1">
        <span class="block truncate text-xs font-semibold">{{ s.label }}</span>
        <span class="block truncate text-[10px] text-slate-500">{{ s.hint }}</span>
      </span>
      <span
        v-if="(counts[s.id] ?? 0) > 0"
        class="shrink-0 rounded-full bg-white/10 px-1.5 py-0.5 text-[10px] tabular-nums text-slate-300"
      >
        {{ counts[s.id] }}
      </span>
    </button>
  </nav>
</template>
