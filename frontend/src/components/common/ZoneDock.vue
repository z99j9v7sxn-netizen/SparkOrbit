<script setup lang="ts">
import { computed, nextTick, ref, watch } from 'vue';

export type DockAccent = 'sky' | 'violet' | 'amber' | 'emerald' | 'rose';

export interface DockItem {
  key: string;
  label: string;
  icon?: string;
  iconSrc?: string;
  /** 面板头部的一句话描述 */
  desc?: string;
  /** 模块强调色（一屏一主色），默认 sky */
  accent?: DockAccent;
  /** 功能域分组标题，相同 group 的项渲染在一起 */
  group?: string;
  /** 该面板展开时的宽度 class，覆盖默认宽度 */
  panelClass?: string;
}

const props = defineProps<{
  items: DockItem[];
  modelValue: string | null;
  panelClass?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', value: string | null): void;
}>();

const awakened = ref(false);
const navRef = ref<HTMLElement | null>(null);
const itemRefs = new Map<string, HTMLButtonElement>();
const indicator = ref({ top: 0, height: 0, visible: false });

const expanded = computed(() => awakened.value || Boolean(props.modelValue));

const activeItem = computed(() => props.items.find((i) => i.key === props.modelValue) ?? null);
const activeAccentClass = computed(() => `lz-accent-${activeItem.value?.accent ?? 'sky'}`);
const activePanelClass = computed(
  () => activeItem.value?.panelClass || props.panelClass || 'w-[min(520px,92vw)]',
);

/** 按 group 归组，保持 items 的先后顺序 */
const groups = computed(() => {
  const out: { label: string; items: DockItem[] }[] = [];
  for (const item of props.items) {
    const label = item.group ?? '';
    const last = out[out.length - 1];
    if (last && last.label === label) last.items.push(item);
    else out.push({ label, items: [item] });
  }
  return out;
});

function setItemRef(key: string, el: HTMLButtonElement | null) {
  if (el) itemRefs.set(key, el);
  else itemRefs.delete(key);
}

function toggle(key: string) {
  emit('update:modelValue', props.modelValue === key ? null : key);
}

async function syncIndicator() {
  await nextTick();
  const nav = navRef.value;
  const btn = props.modelValue ? itemRefs.get(props.modelValue) : null;
  if (!nav || !btn) {
    indicator.value = { ...indicator.value, visible: false };
    return;
  }
  const navRect = nav.getBoundingClientRect();
  const btnRect = btn.getBoundingClientRect();
  indicator.value = {
    top: btnRect.top - navRect.top + nav.scrollTop + 8,
    height: btnRect.height - 16,
    visible: true,
  };
}

watch(() => [props.modelValue, expanded.value, props.items], syncIndicator, { deep: true });

/** 键盘上下键在侧栏项间移动焦点 */
function onNavKeydown(ev: KeyboardEvent) {
  if (ev.key !== 'ArrowDown' && ev.key !== 'ArrowUp') return;
  ev.preventDefault();
  const keys = props.items.map((i) => i.key);
  const focused = document.activeElement as HTMLElement | null;
  let idx = keys.findIndex((k) => itemRefs.get(k) === focused);
  if (idx === -1) idx = keys.findIndex((k) => k === props.modelValue);
  const next = ev.key === 'ArrowDown' ? Math.min(keys.length - 1, idx + 1) : Math.max(0, idx - 1);
  itemRefs.get(keys[next])?.focus();
}
</script>

<template>
  <div
    class="pointer-events-none absolute bottom-24 left-0 top-24 z-40 flex items-stretch gap-3"
    @mouseenter="awakened = true"
    @mouseleave="awakened = false"
  >
    <div class="pointer-events-auto absolute bottom-0 left-0 top-0 w-5" aria-hidden="true"></div>
    <transition name="dock-panel">
      <aside
        v-if="modelValue"
        class="pointer-events-auto order-2 ml-3 flex flex-col overflow-hidden rounded-3xl border border-white/10 bg-slate-950/92 shadow-glow-lg backdrop-blur-xl"
        :class="[activePanelClass, activeAccentClass]"
      >
        <div class="zone-dock-panel-head flex items-center justify-between gap-3 border-b border-white/10 px-4 py-3">
          <div class="flex min-w-0 items-center gap-2.5">
            <span class="zone-dock-panel-dot" aria-hidden="true"></span>
            <img v-if="activeItem?.iconSrc" :src="activeItem.iconSrc" alt="" class="h-5 w-5 shrink-0" />
            <div class="min-w-0">
              <p class="truncate text-sm font-semibold text-white">{{ activeItem?.label ?? '功能面板' }}</p>
              <p v-if="activeItem?.desc" class="lz-caption truncate">{{ activeItem.desc }}</p>
            </div>
          </div>
          <button
            type="button"
            class="lz-btn lz-btn--ghost lz-btn--sm shrink-0"
            @click="emit('update:modelValue', null)"
          >
            收起
          </button>
        </div>
        <div :key="modelValue" class="dock-panel lz-fade-up flex min-h-0 flex-1 flex-col overflow-y-auto p-4">
          <slot :name="modelValue" :active="modelValue" />
        </div>
      </aside>
    </transition>

    <nav
      ref="navRef"
      class="pointer-events-auto relative order-1 flex max-h-full flex-col gap-0.5 self-center overflow-y-auto rounded-r-2xl border border-l-0 border-white/10 bg-slate-950/90 p-2 backdrop-blur-xl transition-transform duration-300"
      :class="expanded ? 'translate-x-0' : '-translate-x-[calc(100%-18px)]'"
      aria-label="学习区功能侧栏"
      @keydown="onNavKeydown"
      @scroll="syncIndicator"
    >
      <span
        class="zone-dock-indicator"
        :class="activeAccentClass"
        :style="{
          top: `${indicator.top}px`,
          height: `${indicator.height}px`,
          opacity: indicator.visible && expanded ? 1 : 0,
        }"
        aria-hidden="true"
      ></span>
      <template v-for="(g, gi) in groups" :key="g.label || gi">
        <p v-if="g.label && expanded" class="zone-dock-group-label">{{ g.label }}</p>
        <div v-else-if="gi > 0" class="mx-2 my-1 h-px shrink-0 bg-white/8" aria-hidden="true"></div>
        <button
          v-for="item in g.items"
          :key="item.key"
          :ref="(el) => setItemRef(item.key, el as HTMLButtonElement | null)"
          type="button"
          class="zone-dock-item group flex h-10 min-w-11 shrink-0 items-center gap-2.5 rounded-xl px-2.5 text-left"
          :class="[
            `lz-accent-${item.accent ?? 'sky'}`,
            modelValue === item.key ? 'is-active' : '',
            expanded ? 'w-44' : 'w-11',
          ]"
          :title="item.desc ? `${item.label} · ${item.desc}` : item.label"
          @click="toggle(item.key)"
        >
          <img v-if="item.iconSrc" :src="item.iconSrc" alt="" class="h-5 w-5 shrink-0 opacity-90" />
          <span v-else-if="item.icon" class="w-5 shrink-0 text-center text-base leading-none">{{ item.icon }}</span>
          <span v-if="expanded" class="truncate text-xs tracking-wide">{{ item.label }}</span>
          <span v-else-if="!item.iconSrc && !item.icon" class="truncate text-[10px] leading-tight">{{ item.label.slice(0, 2) }}</span>
        </button>
      </template>
    </nav>
  </div>
</template>

<style scoped>
.dock-panel-enter-active,
.dock-panel-leave-active {
  transition: transform 0.28s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.28s ease;
}
.dock-panel-enter-from,
.dock-panel-leave-to {
  transform: translateX(-24px);
  opacity: 0;
}

.zone-dock-panel-head {
  background: linear-gradient(90deg, rgb(var(--lz-accent) / 0.12), transparent 65%);
}

.zone-dock-panel-dot {
  width: 8px;
  height: 8px;
  border-radius: 999px;
  flex-shrink: 0;
  background: rgb(var(--lz-accent-bright));
  box-shadow: 0 0 12px rgb(var(--lz-accent) / 0.85);
}

.zone-dock-group-label {
  margin: 0.375rem 0.625rem 0.125rem;
  font-size: 10px;
  font-weight: 600;
  letter-spacing: 0.14em;
  color: rgb(100 116 139);
  flex-shrink: 0;
  user-select: none;
}

.zone-dock-item {
  color: rgb(148 163 184);
  transition: background 0.18s ease, color 0.18s ease, box-shadow 0.18s ease, width 0.3s ease;
}

.zone-dock-item:hover {
  background: rgba(255, 255, 255, 0.05);
  color: rgb(226 232 240);
}

.zone-dock-item:focus-visible {
  outline: none;
  box-shadow: 0 0 0 2px rgb(var(--lz-accent) / 0.4);
}

.zone-dock-item.is-active {
  background: rgb(var(--lz-accent) / 0.16);
  color: #fff;
  box-shadow: inset 0 0 0 1px rgb(var(--lz-accent) / 0.35), 0 0 18px -8px rgb(var(--lz-accent) / 0.5);
}

.zone-dock-indicator {
  position: absolute;
  left: 4px;
  width: 2.5px;
  border-radius: 999px;
  background: linear-gradient(180deg, rgb(var(--lz-accent-bright)), rgb(var(--lz-accent)));
  box-shadow: 0 0 10px rgb(var(--lz-accent) / 0.9);
  pointer-events: none;
  transition: top 0.28s cubic-bezier(0.22, 1, 0.36, 1), height 0.28s cubic-bezier(0.22, 1, 0.36, 1), opacity 0.2s ease;
}

@media (prefers-reduced-motion: reduce) {
  .dock-panel-enter-active,
  .dock-panel-leave-active {
    transition-duration: 0.01ms;
  }

  .zone-dock-indicator,
  .zone-dock-item {
    transition: none;
  }
}
</style>
