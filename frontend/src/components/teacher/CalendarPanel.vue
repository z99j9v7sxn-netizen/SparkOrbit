<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import {
  createCalendarEvent,
  deleteCalendarEvent,
  fetchCalendar,
  type CalendarEvent,
} from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const month = ref(new Date().toISOString().slice(0, 7));
const events = ref<CalendarEvent[]>([]);
const loading = ref(false);
const msg = ref('');
const selectedDate = ref('');

const newTitle = ref('');
const newKind = ref('custom');
const newNote = ref('');

const kindLabel: Record<string, string> = {
  custom: '事项',
  exam: '考试',
  lesson: '课程',
  meeting: '会议',
  assignment: '作业截止',
};

const kindClass: Record<string, string> = {
  assignment: 'bg-t-warn/15 text-t-warn',
  exam: 'bg-t-danger/15 text-t-danger',
  lesson: 'bg-t-accent/15 text-t-accent',
  meeting: 'bg-t-accent2/15 text-t-accent2',
  custom: 'bg-t-line/15 text-t-2',
};

const weekDays = ['一', '二', '三', '四', '五', '六', '日'];

const calendarCells = computed(() => {
  const [y, m] = month.value.split('-').map(Number);
  const first = new Date(y, m - 1, 1);
  const daysInMonth = new Date(y, m, 0).getDate();
  // 周一为一周第一天
  const lead = (first.getDay() + 6) % 7;
  const cells: Array<{ date: string; day: number } | null> = [];
  for (let i = 0; i < lead; i += 1) cells.push(null);
  for (let d = 1; d <= daysInMonth; d += 1) {
    cells.push({ date: `${month.value}-${String(d).padStart(2, '0')}`, day: d });
  }
  return cells;
});

const eventsByDate = computed(() => {
  const map: Record<string, CalendarEvent[]> = {};
  for (const e of events.value) {
    (map[e.event_date] ||= []).push(e);
  }
  return map;
});

const selectedEvents = computed(() => (selectedDate.value ? eventsByDate.value[selectedDate.value] || [] : []));

const today = new Date().toISOString().slice(0, 10);

function shiftMonth(delta: number) {
  const [y, m] = month.value.split('-').map(Number);
  const d = new Date(y, m - 1 + delta, 1);
  month.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`;
  selectedDate.value = '';
}

async function load() {
  loading.value = true;
  msg.value = '';
  try {
    const res = await fetchCalendar(classId.value || '', month.value);
    events.value = res.events;
  } catch (e) {
    msg.value = parseApiError(e, '加载日历失败');
  } finally {
    loading.value = false;
  }
}

async function handleCreate() {
  if (!newTitle.value.trim() || !selectedDate.value) return;
  msg.value = '';
  try {
    await createCalendarEvent({
      class_id: classId.value || '',
      title: newTitle.value,
      event_date: selectedDate.value,
      kind: newKind.value,
      note: newNote.value,
    });
    newTitle.value = '';
    newNote.value = '';
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '添加事件失败');
  }
}

async function handleDelete(ev: CalendarEvent) {
  if (ev.kind === 'assignment') return;
  try {
    await deleteCalendarEvent(ev.id);
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '删除失败');
  }
}

watch([classId, month], () => void load());
onMounted(() => void load());
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="教学日历" subtitle="作业截止自动合并 · 可添加考试 / 课程 / 会议等自定义事项">
      <template #actions>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="shiftMonth(-1)">← 上月</button>
        <span class="font-mono-tech text-sm text-t-1">{{ month }}</span>
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="shiftMonth(1)">下月 →</button>
      </template>
    </TeacherPageHeader>

    <p v-if="msg" class="text-xs text-t-danger">{{ msg }}</p>

    <div class="grid gap-4 xl:grid-cols-[1.6fr_1fr]">
      <!-- 月历 -->
      <section class="t-card glass-edge p-5">
        <div class="grid grid-cols-7 gap-1.5">
          <div v-for="d in weekDays" :key="d" class="pb-1 text-center text-[11px] text-t-3">周{{ d }}</div>
          <div
            v-for="(cell, idx) in calendarCells"
            :key="idx"
            class="min-h-[76px] rounded-lg border p-1.5 transition"
            :class="
              cell
                ? [
                    'cursor-pointer',
                    selectedDate === cell.date
                      ? 'border-t-accent/50 bg-t-accent/8'
                      : cell.date === today
                        ? 'border-t-accent2/40 bg-t-accent2/6 hover:border-t-accent/35'
                        : 'border-t-line/10 bg-t-s1/25 hover:border-t-accent/25',
                  ]
                : 'border-transparent'
            "
            @click="cell && (selectedDate = cell.date)"
          >
            <template v-if="cell">
              <p class="text-right font-mono-tech text-[11px]" :class="cell.date === today ? 'font-bold text-t-accent2' : 'text-t-3'">
                {{ cell.day }}
              </p>
              <div class="mt-0.5 space-y-0.5">
                <p
                  v-for="e in (eventsByDate[cell.date] || []).slice(0, 2)"
                  :key="e.id"
                  class="truncate rounded px-1 py-0.5 text-[9px]"
                  :class="kindClass[e.kind] || kindClass.custom"
                >
                  {{ e.title }}
                </p>
                <p v-if="(eventsByDate[cell.date] || []).length > 2" class="px-1 text-[9px] text-t-3">
                  +{{ (eventsByDate[cell.date] || []).length - 2 }} 项
                </p>
              </div>
            </template>
          </div>
        </div>
      </section>

      <!-- 当日详情与添加 -->
      <section class="t-card glass-edge p-5">
        <div class="flex items-baseline justify-between gap-2">
          <h3 class="text-[15px] font-semibold text-t-1">{{ selectedDate || '选择日期' }}</h3>
          <span class="t-kicker">Day Detail</span>
        </div>

        <div v-if="selectedDate" class="mt-3 space-y-3">
          <div class="space-y-2">
            <div
              v-for="e in selectedEvents"
              :key="e.id"
              class="flex items-start justify-between gap-2 rounded-xl border border-t-line/10 bg-t-s1/30 px-3 py-2.5"
            >
              <div class="min-w-0">
                <div class="flex items-center gap-1.5">
                  <span class="rounded px-1.5 py-0.5 text-[10px]" :class="kindClass[e.kind] || kindClass.custom">
                    {{ kindLabel[e.kind] || e.kind }}
                  </span>
                  <p class="truncate text-sm text-t-1">{{ e.title }}</p>
                </div>
                <p v-if="e.note" class="mt-0.5 text-[11px] text-t-3">{{ e.note }}</p>
              </div>
              <button
                v-if="e.kind !== 'assignment'"
                type="button"
                class="shrink-0 text-[11px] text-t-danger transition hover:opacity-75"
                @click="handleDelete(e)"
              >
                删除
              </button>
            </div>
            <TeacherEmptyState v-if="!selectedEvents.length" title="当日暂无事项" />
          </div>

          <div class="border-t border-t-line/10 pt-3">
            <p class="text-xs font-medium text-t-2">添加事项</p>
            <input v-model="newTitle" placeholder="标题，如：期中考试" class="t-input mt-2" />
            <div class="mt-2 flex gap-2">
              <select v-model="newKind" class="t-input flex-1 cursor-pointer">
                <option value="custom">事项</option>
                <option value="exam">考试</option>
                <option value="lesson">课程</option>
                <option value="meeting">会议</option>
              </select>
              <input v-model="newNote" placeholder="备注（可选）" class="t-input flex-[2]" />
            </div>
            <button type="button" class="t-btn t-btn--primary t-btn--md mt-3" :disabled="!newTitle.trim()" @click="handleCreate">
              添加到 {{ selectedDate }}
            </button>
          </div>
        </div>
        <TeacherEmptyState v-else class="mt-3" title="点击左侧日期" description="查看当日事项或添加新安排" />
      </section>
    </div>
  </div>
</template>
