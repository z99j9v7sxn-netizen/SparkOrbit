<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { fetchGradebook, type GradebookRow } from '../../api/teacher';
import { useTeacherClassStore } from '../../stores/teacherClass';
import { teacherNavItems } from './teacherNav';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: 'close'): void }>();

const router = useRouter();
const classStore = useTeacherClassStore();

const query = ref('');
const activeIndex = ref(0);
const inputRef = ref<HTMLInputElement | null>(null);
const students = ref<GradebookRow[]>([]);
const studentsLoaded = ref(false);
let loadedForClass = '';

type PaletteEntry =
  | { kind: 'page'; label: string; icon: string; path: string }
  | { kind: 'student'; label: string; sub: string; id: string };

const results = computed<PaletteEntry[]>(() => {
  const q = query.value.trim().toLowerCase();
  const pages = teacherNavItems
    .filter((i) => !q || i.label.toLowerCase().includes(q) || i.keywords?.toLowerCase().includes(q))
    .map((i) => ({ kind: 'page' as const, label: i.label, icon: i.icon, path: i.path }));
  const matched = q
    ? students.value
        .filter(
          (s) =>
            s.display_name.toLowerCase().includes(q) || s.username.toLowerCase().includes(q),
        )
        .slice(0, 8)
        .map((s) => ({
          kind: 'student' as const,
          label: s.display_name,
          sub: `@${s.username}`,
          id: s.user_id,
        }))
    : [];
  return [...pages, ...matched];
});

watch(
  () => props.open,
  async (open) => {
    if (!open) return;
    query.value = '';
    activeIndex.value = 0;
    await nextTick();
    inputRef.value?.focus();
    const cid = classStore.classId;
    if (cid && (!studentsLoaded.value || loadedForClass !== cid)) {
      try {
        students.value = await fetchGradebook(cid);
        studentsLoaded.value = true;
        loadedForClass = cid;
      } catch {
        students.value = [];
      }
    }
  },
);

watch(results, () => {
  if (activeIndex.value >= results.value.length) activeIndex.value = 0;
});

function pick(entry: PaletteEntry) {
  if (entry.kind === 'page') {
    void router.push(entry.path);
  } else {
    void router.push({ path: `/teacher/students/${entry.id}`, query: { class_id: classStore.classId } });
  }
  emit('close');
}

function onKeydown(e: KeyboardEvent) {
  if (e.key === 'Escape') {
    emit('close');
    return;
  }
  if (e.key === 'ArrowDown') {
    e.preventDefault();
    activeIndex.value = (activeIndex.value + 1) % Math.max(results.value.length, 1);
  } else if (e.key === 'ArrowUp') {
    e.preventDefault();
    activeIndex.value =
      (activeIndex.value - 1 + Math.max(results.value.length, 1)) % Math.max(results.value.length, 1);
  } else if (e.key === 'Enter') {
    const entry = results.value[activeIndex.value];
    if (entry) pick(entry);
  }
}
</script>

<template>
  <Transition name="fade-scale">
    <div v-if="open" class="t-cmdk-overlay" @click.self="emit('close')">
      <div class="t-cmdk" role="dialog" aria-label="快捷导航" @keydown="onKeydown">
        <div class="flex items-center gap-2.5 border-b border-t-line/10 px-4 py-3">
          <svg viewBox="0 0 16 16" class="h-4 w-4 shrink-0 text-t-3" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round">
            <circle cx="7" cy="7" r="4.5" />
            <path d="m13.5 13.5-3.2-3.2" />
          </svg>
          <input
            ref="inputRef"
            v-model="query"
            type="text"
            placeholder="搜索页面或学生…"
            class="w-full bg-transparent text-sm text-t-1 outline-none placeholder:text-t-3"
          />
          <span class="t-kbd shrink-0">ESC</span>
        </div>

        <div class="max-h-[46vh] overflow-y-auto p-2">
          <template v-if="results.length">
            <button
              v-for="(entry, idx) in results"
              :key="entry.kind === 'page' ? entry.path : entry.id"
              type="button"
              class="t-cmdk-item"
              :class="{ 'is-active': idx === activeIndex }"
              @mouseenter="activeIndex = idx"
              @click="pick(entry)"
            >
              <img
                v-if="entry.kind === 'page'"
                :src="entry.icon"
                alt=""
                class="t-icon-img h-4 w-4 shrink-0 opacity-90"
              />
              <span
                v-else
                class="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-t-accent/15 text-[10px] font-semibold text-t-accent"
              >
                {{ entry.label.slice(0, 1) }}
              </span>
              <span class="min-w-0 flex-1 truncate">{{ entry.label }}</span>
              <span v-if="entry.kind === 'student'" class="shrink-0 text-[11px] text-t-3">{{ entry.sub }}</span>
              <span v-else class="shrink-0 text-[11px] text-t-3">页面</span>
            </button>
          </template>
          <p v-else class="px-3 py-6 text-center text-sm text-t-3">没有匹配的结果</p>
        </div>

        <div class="flex items-center gap-3 border-t border-t-line/10 px-4 py-2 text-[11px] text-t-3">
          <span class="flex items-center gap-1"><span class="t-kbd">↑↓</span> 选择</span>
          <span class="flex items-center gap-1"><span class="t-kbd">Enter</span> 跳转</span>
        </div>
      </div>
    </div>
  </Transition>
</template>
