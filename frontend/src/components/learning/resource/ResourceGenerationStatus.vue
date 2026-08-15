<script setup lang="ts">
import { computed } from 'vue';
import { LzBadge, LzProgress } from '../ui';

const props = withDefaults(
  defineProps<{
    generating: boolean;
    degraded?: boolean;
    error?: string;
    preview?: string;
    items: { agent: string; status: 'waiting' | 'running' | 'done' }[];
    expected: number;
  }>(),
  { degraded: false, error: '', preview: '' },
);

const doneCount = computed(() => props.items.filter((i) => i.status === 'done').length);
const progress = computed(() =>
  Math.min(100, Math.round((doneCount.value / Math.max(props.expected, 1)) * 100)),
);

function toneOf(status: 'waiting' | 'running' | 'done'): 'success' | 'accent' | 'neutral' {
  if (status === 'done') return 'success';
  if (status === 'running') return 'accent';
  return 'neutral';
}
</script>

<template>
  <section class="lz-card lz-card--flat p-3">
    <div class="flex flex-wrap items-center gap-2">
      <p class="lz-subtitle">Agent 协作状态</p>
      <LzBadge v-if="generating" tone="accent">workflow · 流水线运行中</LzBadge>
      <LzBadge v-if="degraded" tone="warning">演示降级</LzBadge>
      <LzBadge v-if="error" tone="danger">出错 / 中断</LzBadge>
    </div>
    <LzProgress
      v-if="generating || doneCount"
      class="mt-2"
      :value="progress"
      label="生成进度"
      show-value
    />
    <div class="mt-2 flex flex-wrap gap-1.5">
      <LzBadge v-for="item in items" :key="item.agent" :tone="toneOf(item.status)">
        {{ item.agent }} · {{ item.status }}
      </LzBadge>
    </div>
    <p v-if="preview" class="lz-desc mt-2 max-h-24 overflow-auto">{{ preview }}</p>
  </section>
</template>
