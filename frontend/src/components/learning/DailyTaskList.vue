<script setup lang="ts">
import { onMounted, ref } from 'vue';
import { fetchDailyTasks, toggleDailyTask, type DailyTask } from '../../api/zone';
import { useOrbitStore } from '../../stores/orbit';
import { LzBadge, LzSkeleton } from './ui';

const orbit = useOrbitStore();
const tasks = ref<DailyTask[]>([]);
const loading = ref(false);

async function load() {
  tasks.value = await fetchDailyTasks().catch(() => []);
}

async function toggle(task: DailyTask) {
  loading.value = true;
  try {
    const updated = await toggleDailyTask(task.id);
    tasks.value = tasks.value.map((t) => (t.id === updated.id ? updated : t));
    if (updated.done) orbit.pushNotification('每日任务', `完成「${updated.title}」+${updated.points} 积分`, 'success');
  } finally {
    loading.value = false;
  }
}

onMounted(load);
</script>

<template>
  <div class="dock-panel space-y-3">
    <p class="lz-desc">基于星轨进度与遗忘曲线生成今日任务（含复习固化）</p>
    <button
      v-for="task in tasks"
      :key="task.id"
      type="button"
      class="flex w-full items-start gap-3 p-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
      :class="task.done
        ? 'rounded-[var(--radius-card)] border border-emerald-400/25 bg-emerald-500/5'
        : 'lz-card lz-card--hover'"
      :disabled="loading"
      @click="toggle(task)"
    >
      <span class="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-md border" :class="task.done ? 'border-emerald-400 bg-emerald-500/20 text-emerald-200' : 'border-[var(--border-strong)]'">
        {{ task.done ? '✓' : '' }}
      </span>
      <div class="min-w-0 flex-1">
        <p class="lz-subtitle" :class="task.done ? 'line-through opacity-70' : ''">{{ task.title }}</p>
        <p class="mt-1 flex items-center gap-2">
          <LzBadge v-if="task.task_type === 'review'" tone="accent">复习</LzBadge>
          <span class="lz-caption lz-accent-text">+{{ task.points }} 积分</span>
        </p>
      </div>
    </button>
    <LzSkeleton v-if="!tasks.length" preset="list" :rows="3" />
  </div>
</template>
