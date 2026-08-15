<script setup lang="ts">
import type { ProfileHistoryItem } from '../../api/profiles';
import { LzEmptyState, LzSkeleton } from '../learning/ui';
import { cleanSummaryText } from './profileText';

defineProps<{
  items: ProfileHistoryItem[];
  loading: boolean;
}>();

const emit = defineEmits<{
  (e: 'recall', item: ProfileHistoryItem): void;
  (e: 'collect'): void;
}>();

function historyMiniScores(item: ProfileHistoryItem): { label: string; score: number }[] {
  const keys: { label: string; scoreKey: keyof ProfileHistoryItem }[] = [
    { label: '前置', scoreKey: 'prior_knowledge_score' },
    { label: '易错', scoreKey: 'mistake_tendency_score' },
    { label: '目标', scoreKey: 'learning_goal_score' },
    { label: '动机', scoreKey: 'motivation_level_score' },
  ];
  return keys.map((k) => ({
    label: k.label,
    score: Number(item[k.scoreKey] ?? 0) || 0,
  }));
}
</script>

<template>
  <div class="max-h-60 overflow-auto pr-1">
    <LzSkeleton v-if="loading" preset="list" :rows="3" class="py-2" />
    <LzEmptyState
      v-else-if="!items.length"
      icon="✦"
      title="暂无历史版本"
      desc="完成首次采集后，每次更新都会出现在这里。"
      action-text="去采集"
      @action="emit('collect')"
    />
    <template v-else>
      <button
        v-for="(item, idx) in items"
        :key="item.id"
        type="button"
        class="group relative flex w-full gap-3 border-0 bg-transparent py-0 text-left"
        @click="emit('recall', item)"
      >
        <div class="flex w-3 shrink-0 flex-col items-center">
          <span
            class="mt-3 h-2.5 w-2.5 rounded-full ring-2 ring-slate-950"
            :class="idx === 0 ? 'bg-[rgb(var(--lz-accent))]' : 'bg-slate-500'"
          />
          <span
            v-if="idx < items.length - 1"
            class="w-px flex-1 bg-white/10"
            aria-hidden="true"
          />
        </div>
        <div class="lz-card lz-card--hover mb-2 min-w-0 flex-1 p-2.5">
          <div class="flex items-center justify-between gap-2">
            <p class="lz-caption">
              {{ item.created_at ? new Date(item.created_at).toLocaleString() : '最近' }}
            </p>
            <span class="lz-caption lz-accent-text opacity-0 transition group-hover:opacity-100">回看 →</span>
          </div>
          <p class="lz-body mt-1">
            {{ cleanSummaryText(item.summary) || '（无摘要，点击回看该版本雷达）' }}
          </p>
          <div class="mt-2 grid grid-cols-2 gap-1.5">
            <div
              v-for="s in historyMiniScores(item)"
              :key="s.label"
              class="flex items-center gap-1.5"
            >
              <span class="w-6 shrink-0 text-[9px] text-slate-500">{{ s.label }}</span>
              <div class="h-1 min-w-0 flex-1 overflow-hidden rounded-full bg-white/10">
                <div
                  class="h-full rounded-full"
                  :class="s.score < 60 ? 'bg-amber-400/80' : 'bg-[rgb(var(--lz-accent)/0.8)]'"
                  :style="{ width: `${Math.max(4, Math.min(100, s.score))}%` }"
                />
              </div>
              <span class="w-5 text-right font-mono text-[9px] tabular-nums text-slate-400">{{ s.score }}</span>
            </div>
          </div>
        </div>
      </button>
    </template>
  </div>
</template>
