<script setup lang="ts">
import { LzButton, LzInput, LzTextarea } from '../ui';

type PlanetOption = { slug: string; name: string };

withDefaults(
  defineProps<{
    /** 沉浸模式紧凑布局：更矮的引用输入、更小的框选预览、答案限高滚动 */
    compact?: boolean;
    pageNo?: number;
    pageHasSelectableText?: boolean;
    quoteText: string;
    askQuestion: string;
    askAnswer: string;
    askLoading?: boolean;
    regionPreview: string;
    feynmanMode: boolean;
    socraticMode: boolean;
    clipPickerOpen?: boolean;
    pendingPlanetSlug: string;
    planets?: PlanetOption[];
  }>(),
  {
    compact: false,
    pageNo: undefined,
    pageHasSelectableText: true,
    askLoading: false,
    clipPickerOpen: false,
    planets: () => [],
  },
);

const emit = defineEmits<{
  (e: 'update:quoteText', value: string): void;
  (e: 'update:askQuestion', value: string): void;
  (e: 'update:pageNo', value: number | undefined): void;
  (e: 'update:feynmanMode', value: boolean): void;
  (e: 'update:socraticMode', value: boolean): void;
  (e: 'update:pendingPlanetSlug', value: string): void;
  (e: 'ask'): void;
  (e: 'clip'): void;
  (e: 'collect-word'): void;
  (e: 'clear-region'): void;
  (e: 'confirm-clip'): void;
  (e: 'cancel-clip'): void;
}>();

function onFeynmanChange(ev: Event) {
  const checked = (ev.target as HTMLInputElement).checked;
  emit('update:feynmanMode', checked);
  // 与伴学舱一致：费曼模式开启时关闭苏格拉底引导
  if (checked) emit('update:socraticMode', false);
}

function onSocraticChange(ev: Event) {
  emit('update:socraticMode', (ev.target as HTMLInputElement).checked);
}

function onPageNoInput(ev: Event) {
  const raw = (ev.target as HTMLInputElement).value;
  const n = Number(raw);
  emit('update:pageNo', raw === '' || Number.isNaN(n) ? undefined : n);
}
</script>

<template>
  <div class="border-t border-[var(--border-soft)] px-4 py-3" :class="compact ? 'bg-black/80' : 'bg-black/60'">
    <p class="lz-caption lz-accent-text uppercase tracking-wider">划词 / 剪藏</p>
    <p class="mt-1 lz-caption">
      拖选文字，或用涂抹笔 / 圈选笔框选区域；当前页码
      <span class="lz-accent-text">{{ pageNo || '—' }}</span>
    </p>
    <p v-if="!pageHasSelectableText" class="mt-1 text-[11px] leading-5 text-amber-200/90">
      本页无可选文字 · 请用工具栏「涂抹笔 / 圈选笔」框选后，可补充说明再点「问伴学」
    </p>

    <div v-if="regionPreview" class="mt-2 flex items-start gap-2">
      <img
        :src="regionPreview"
        alt="框选预览"
        class="rounded-[var(--radius-ctl)] border border-[rgb(var(--lz-accent)/0.3)] bg-white object-contain"
        :class="compact ? 'max-h-24 max-w-[36%]' : 'max-h-28 max-w-[40%]'"
      />
      <LzButton variant="ghost" size="sm" @click="emit('clear-region')">清除框选</LzButton>
    </div>

    <LzTextarea
      class="mt-2"
      :model-value="quoteText"
      :rows="compact ? 2 : 3"
      placeholder="划词内容（可选；有框选图时可不填）…"
      @update:model-value="(v) => emit('update:quoteText', v)"
    />

    <div class="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-300">
      <label class="flex cursor-pointer items-center gap-1.5">
        <input type="checkbox" class="rounded" :checked="feynmanMode" @change="onFeynmanChange" />
        费曼讲解
      </label>
      <label v-if="!feynmanMode" class="flex cursor-pointer items-center gap-1.5">
        <input type="checkbox" class="rounded" :checked="socraticMode" @change="onSocraticChange" />
        苏格拉底引导
      </label>
    </div>

    <div class="mt-2 flex flex-wrap items-center gap-2">
      <div class="w-20 shrink-0">
        <input
          :value="pageNo ?? ''"
          type="number"
          min="1"
          placeholder="页码"
          class="lz-input h-8 px-2.5"
          @input="onPageNoInput"
        />
      </div>
      <LzInput
        class="min-w-[140px] flex-1"
        :model-value="askQuestion"
        size="sm"
        :placeholder="feynmanMode ? '用自己的话讲解框选内容…' : '可选追问（可与框选区域一起发给伴学）…'"
        @update:model-value="(v) => emit('update:askQuestion', v)"
      />
      <LzButton variant="primary" size="sm" :loading="askLoading" @click="emit('ask')">
        {{
          askLoading
            ? feynmanMode
              ? '点评中…'
              : '提问中…'
            : feynmanMode
              ? '点评讲解'
              : '问伴学'
        }}
      </LzButton>
      <button
        type="button"
        class="rounded-[var(--radius-ctl)] border border-emerald-400/35 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-100 transition hover:bg-emerald-500/20"
        @click="emit('clip')"
      >
        划词剪藏
      </button>
      <button
        type="button"
        class="rounded-[var(--radius-ctl)] border border-sky-400/35 bg-sky-500/10 px-3 py-1.5 text-xs font-medium text-sky-100 transition hover:bg-sky-500/20"
        title="把划词内容加入复习队列（生词本）"
        @click="emit('collect-word')"
      >
        ＋生词本
      </button>
    </div>

    <div
      v-if="clipPickerOpen"
      class="mt-2 flex flex-wrap items-center gap-2 rounded-[var(--radius-card)] border border-emerald-400/25 bg-emerald-500/5 px-3 py-2"
    >
      <span class="text-[11px] text-emerald-100/90">归属星球</span>
      <select
        :value="pendingPlanetSlug"
        class="lz-input h-8 min-w-[140px] flex-1 px-2.5"
        @change="emit('update:pendingPlanetSlug', ($event.target as HTMLSelectElement).value)"
      >
        <option value="">选择知识点…</option>
        <option v-for="p in planets" :key="p.slug" :value="p.slug">{{ p.name }}</option>
      </select>
      <button
        type="button"
        class="rounded-[var(--radius-ctl)] border border-emerald-400/40 bg-emerald-500/15 px-3 py-1.5 text-xs font-semibold text-emerald-50 transition hover:bg-emerald-500/25"
        @click="emit('confirm-clip')"
      >
        确认剪藏
      </button>
      <LzButton variant="ghost" size="sm" @click="emit('cancel-clip')">取消</LzButton>
    </div>

    <p
      v-if="askAnswer"
      class="mt-2 whitespace-pre-wrap rounded-[var(--radius-ctl)] border border-[rgb(var(--lz-accent)/0.2)] bg-[rgb(var(--lz-accent)/0.06)] p-2.5 lz-body"
      :class="compact ? 'max-h-40 overflow-auto' : ''"
    >
      {{ askAnswer }}
    </p>
  </div>
</template>
