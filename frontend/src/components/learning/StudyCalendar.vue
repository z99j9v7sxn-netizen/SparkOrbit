<script setup lang="ts">
import { computed, onMounted, ref } from 'vue';
import { fetchStudyCalendar, type CalendarDay, type StudyCalendarData } from '../../api/review';
import { LzBadge, LzButton, LzCard, LzSkeleton } from './ui';

const emit = defineEmits<{ (e: 'open-dock', id: string): void }>();

const now = new Date();
const year = ref(now.getFullYear());
const month = ref(now.getMonth() + 1);
const data = ref<StudyCalendarData | null>(null);
const loading = ref(false);
const selected = ref<CalendarDay | null>(null);

const monthKey = computed(() => `${year.value}-${String(month.value).padStart(2, '0')}`);
const todayKey = computed(() => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
});

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日'];

/** 月首对齐星期一的前置空格数 */
const leadingBlanks = computed(() => {
  const first = new Date(year.value, month.value - 1, 1).getDay(); // 0=Sun
  return (first + 6) % 7;
});

function heat(day: CalendarDay): string {
  const activity = day.focus_minutes + day.practice_items * 2 + day.tasks_done * 5;
  if (!activity) return 'bg-white/[0.03]';
  if (activity < 15) return 'bg-emerald-500/15';
  if (activity < 40) return 'bg-emerald-500/30';
  if (activity < 90) return 'bg-emerald-500/50';
  return 'bg-emerald-400/70';
}

async function load() {
  loading.value = true;
  selected.value = null;
  try {
    data.value = await fetchStudyCalendar(monthKey.value);
    selected.value = data.value.days.find((d) => d.date === todayKey.value) ?? null;
  } catch {
    data.value = null;
  } finally {
    loading.value = false;
  }
}

function shift(delta: number) {
  const d = new Date(year.value, month.value - 1 + delta, 1);
  year.value = d.getFullYear();
  month.value = d.getMonth() + 1;
  void load();
}

onMounted(load);
</script>

<template>
  <div class="dock-panel space-y-4">
    <header class="space-y-1">
      <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Study Calendar</p>
      <h3 class="lz-title">学习日历</h3>
      <p class="lz-desc">每日任务、作业截止、专注与训练强度一览。绿色越深，当天学习强度越高。</p>
    </header>

    <div class="flex items-center justify-between">
      <LzButton size="sm" variant="ghost" @click="shift(-1)">← 上月</LzButton>
      <p class="lz-subtitle font-mono-tech">{{ monthKey }}</p>
      <LzButton size="sm" variant="ghost" @click="shift(1)">下月 →</LzButton>
    </div>

    <LzCard v-if="data && data.review_due_today > 0" padding="sm" class="border-amber-400/30">
      <div class="flex items-center justify-between gap-2">
        <p class="lz-desc">🔥 今天有 <span class="text-amber-200 font-semibold">{{ data.review_due_today }}</span> 项复习到期</p>
        <LzButton size="sm" variant="primary" @click="emit('open-dock', 'review')">去复习</LzButton>
      </div>
    </LzCard>

    <LzSkeleton v-if="loading" preset="list" :rows="5" />

    <template v-else-if="data">
      <div class="grid grid-cols-7 gap-1 text-center">
        <span v-for="w in WEEKDAYS" :key="w" class="lz-caption py-1">{{ w }}</span>
        <span v-for="i in leadingBlanks" :key="`blank-${i}`"></span>
        <button
          v-for="day in data.days"
          :key="day.date"
          type="button"
          class="relative aspect-square rounded-lg border text-xs transition"
          :class="[
            heat(day),
            selected?.date === day.date ? 'border-sky-400/70 ring-1 ring-sky-400/40' : 'border-white/5 hover:border-white/25',
            day.date === todayKey ? 'font-bold text-sky-200' : 'text-slate-300',
          ]"
          @click="selected = day"
        >
          {{ Number(day.date.slice(-2)) }}
          <span
            v-if="day.assignments_due.length"
            class="absolute right-0.5 top-0.5 h-1.5 w-1.5 rounded-full"
            :class="day.assignments_due.every((a) => a.submitted) ? 'bg-emerald-400' : 'bg-rose-400'"
          ></span>
          <span v-if="day.signed_in" class="absolute bottom-0.5 left-1/2 h-0.5 w-3 -translate-x-1/2 rounded bg-sky-400/70"></span>
        </button>
      </div>

      <LzCard v-if="selected" padding="md" class="space-y-2">
        <div class="flex items-center justify-between">
          <p class="lz-subtitle font-mono-tech">{{ selected.date }}</p>
          <LzBadge v-if="selected.signed_in" tone="success">已签到</LzBadge>
        </div>
        <div class="grid grid-cols-3 gap-2 text-center">
          <div class="rounded-lg bg-white/[0.04] p-2">
            <p class="text-base font-semibold text-sky-200">{{ selected.focus_minutes }}</p>
            <p class="lz-caption">专注分钟</p>
          </div>
          <div class="rounded-lg bg-white/[0.04] p-2">
            <p class="text-base font-semibold text-emerald-200">{{ selected.tasks_done }}/{{ selected.tasks_total }}</p>
            <p class="lz-caption">任务完成</p>
          </div>
          <div class="rounded-lg bg-white/[0.04] p-2">
            <p class="text-base font-semibold text-amber-200">{{ selected.practice_items }}</p>
            <p class="lz-caption">训练条目</p>
          </div>
        </div>
        <template v-if="selected.assignments_due.length">
          <p class="lz-caption">当天截止作业</p>
          <button
            v-for="a in selected.assignments_due"
            :key="a.id"
            type="button"
            class="flex w-full items-center justify-between rounded-lg border border-white/10 px-2.5 py-1.5 text-left text-xs hover:border-white/25"
            @click="emit('open-dock', 'homework')"
          >
            <span class="truncate text-slate-200">{{ a.title }}</span>
            <LzBadge :tone="a.submitted ? 'success' : 'warning'">{{ a.submitted ? '已提交' : '待提交' }}</LzBadge>
          </button>
        </template>
        <div class="flex gap-2 pt-1">
          <LzButton size="sm" variant="soft" @click="emit('open-dock', 'tasks')">今日任务</LzButton>
          <LzButton size="sm" variant="soft" @click="emit('open-dock', 'focus')">番茄钟</LzButton>
        </div>
      </LzCard>
    </template>
  </div>
</template>
