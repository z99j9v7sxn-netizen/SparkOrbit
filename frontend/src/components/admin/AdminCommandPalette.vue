<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';
import { useRouter } from 'vue-router';
import { useAdminTheme } from '../../composables/useAdminTheme';
import { adminNavItems } from './adminNav';

const props = defineProps<{ open: boolean }>();
const emit = defineEmits<{ (e: 'close'): void }>();

const router = useRouter();
const { isLight, toggleTheme } = useAdminTheme();

const query = ref('');
const activeIndex = ref(0);
const inputRef = ref<HTMLInputElement | null>(null);

type PaletteEntry =
  | { kind: 'page'; label: string; icon: string; path: string }
  | { kind: 'action'; label: string; icon: string; run: () => void };

const THEME_ICON =
  '<circle cx="8" cy="8" r="3.2"/><path d="M8 1.5v1.7M8 12.8v1.7M1.5 8h1.7M12.8 8h1.7M3.4 3.4l1.2 1.2M11.4 11.4l1.2 1.2M12.6 3.4l-1.2 1.2M4.6 11.4 3.4 12.6"/>';
const TEACHER_ICON =
  '<path d="M2.5 3.5h11v8h-11z"/><path d="M5.5 13.5h5M8 11.5v2"/>';

const actions = computed<PaletteEntry[]>(() => [
  {
    kind: 'action',
    label: isLight.value ? '切换到深色主题' : '切换到浅色主题',
    icon: THEME_ICON,
    run: toggleTheme,
  },
  {
    kind: 'action',
    label: '前往教师工作台',
    icon: TEACHER_ICON,
    run: () => void router.push('/teacher'),
  },
]);

const results = computed<PaletteEntry[]>(() => {
  const q = query.value.trim().toLowerCase();
  const pages = adminNavItems
    .filter((i) => !q || i.label.toLowerCase().includes(q) || i.keywords?.toLowerCase().includes(q))
    .map((i) => ({ kind: 'page' as const, label: i.label, icon: i.icon, path: i.path }));
  const acts = actions.value.filter((a) => !q || a.label.toLowerCase().includes(q));
  return [...pages, ...acts];
});

watch(
  () => props.open,
  async (open) => {
    if (!open) return;
    query.value = '';
    activeIndex.value = 0;
    await nextTick();
    inputRef.value?.focus();
  },
);

watch(results, () => {
  if (activeIndex.value >= results.value.length) activeIndex.value = 0;
});

function pick(entry: PaletteEntry) {
  if (entry.kind === 'page') {
    void router.push(entry.path);
  } else {
    entry.run();
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
            placeholder="搜索页面或操作…"
            class="w-full bg-transparent text-sm text-t-1 outline-none placeholder:text-t-3"
          />
          <span class="t-kbd shrink-0">ESC</span>
        </div>

        <div class="max-h-[46vh] overflow-y-auto p-2">
          <template v-if="results.length">
            <button
              v-for="(entry, idx) in results"
              :key="entry.kind === 'page' ? entry.path : entry.label"
              type="button"
              class="t-cmdk-item"
              :class="{ 'is-active': idx === activeIndex }"
              @mouseenter="activeIndex = idx"
              @click="pick(entry)"
            >
              <svg
                viewBox="0 0 16 16"
                class="h-4 w-4 shrink-0 opacity-80"
                fill="none"
                stroke="currentColor"
                stroke-width="1.3"
                stroke-linecap="round"
                stroke-linejoin="round"
                aria-hidden="true"
                v-html="entry.icon"
              />
              <span class="min-w-0 flex-1 truncate">{{ entry.label }}</span>
              <span class="shrink-0 text-[11px] text-t-3">{{ entry.kind === 'page' ? '页面' : '操作' }}</span>
            </button>
          </template>
          <p v-else class="px-3 py-6 text-center text-sm text-t-3">没有匹配的结果</p>
        </div>

        <div class="flex items-center gap-3 border-t border-t-line/10 px-4 py-2 text-[11px] text-t-3">
          <span class="flex items-center gap-1"><span class="t-kbd">↑↓</span> 选择</span>
          <span class="flex items-center gap-1"><span class="t-kbd">Enter</span> 执行</span>
        </div>
      </div>
    </div>
  </Transition>
</template>
