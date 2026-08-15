<script setup lang="ts">
import type { VaultSearchHit } from '../../../api/vault';
import { relativeTime } from './sections';

defineProps<{
  items: VaultSearchHit[];
  activePath: string;
  loading?: boolean;
  emptyHint?: string;
}>();

const emit = defineEmits<{
  (e: 'open', path: string): void;
}>();
</script>

<template>
  <div class="flex h-full flex-col overflow-hidden">
    <p v-if="loading" class="p-4 text-xs text-slate-500">加载中…</p>
    <div v-else-if="!items.length" class="flex flex-1 flex-col items-center justify-center gap-2 p-6 text-center">
      <p class="text-sm text-slate-400">{{ emptyHint || '这个分区还没有笔记' }}</p>
      <slot name="empty" />
    </div>
    <ul v-else class="flex-1 space-y-1.5 overflow-y-auto p-2">
      <li v-for="item in items" :key="item.path">
        <button
          type="button"
          class="w-full rounded-xl border px-3 py-2.5 text-left transition"
          :class="
            activePath === item.path
              ? 'border-[rgb(var(--lz-accent)/0.45)] bg-[rgb(var(--lz-accent)/0.2)] text-white'
              : 'border-white/8 bg-white/[0.03] hover:border-[rgb(var(--lz-accent)/0.25)] hover:bg-white/[0.06]'
          "
          @click="emit('open', item.path)"
        >
          <p class="truncate text-xs font-semibold text-white">{{ item.title || item.path }}</p>
          <p v-if="item.snippet" class="mt-1 line-clamp-2 text-[11px] leading-4 text-slate-400">
            {{ item.snippet }}
          </p>
          <div class="mt-1.5 flex flex-wrap items-center gap-1.5 text-[10px] text-slate-500">
            <span v-if="item.updated_at">{{ relativeTime(item.updated_at) }}</span>
            <span v-if="item.word_count" class="tabular-nums">{{ item.word_count }} 字</span>
            <span
              v-for="tag in (item.tags || []).slice(0, 3)"
              :key="tag"
              class="rounded-full border border-[rgb(var(--lz-accent)/0.2)] bg-[rgb(var(--lz-accent)/0.1)] px-1.5 py-0.5 text-[rgb(var(--lz-accent-bright)/0.8)]"
            >
              #{{ tag }}
            </span>
          </div>
        </button>
      </li>
    </ul>
  </div>
</template>
