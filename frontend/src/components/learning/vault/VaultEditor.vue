<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import MarkdownView from '../../common/MarkdownView.vue';

type EditorMode = 'edit' | 'preview' | 'split';

const props = defineProps<{
  path: string;
  title: string;
  modelValue: string;
  saving?: boolean;
  dirty?: boolean;
  updatedAt?: string;
}>();

const emit = defineEmits<{
  (e: 'update:modelValue', v: string): void;
  (e: 'save'): void;
  (e: 'delete'): void;
  (e: 'insert-wiki'): void;
  (e: 'mousemove', ev: MouseEvent): void;
  (e: 'mouseleave'): void;
}>();

const mode = ref<EditorMode>('split');
const wordCount = computed(() => (props.modelValue || '').replace(/\s+/g, '').length);

watch(
  () => props.path,
  () => {
    /* keep mode across notes */
  },
);
</script>

<template>
  <section class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/50">
    <div class="flex flex-wrap items-center gap-2 border-b border-white/8 px-3 py-2">
      <span class="min-w-0 flex-1 truncate text-xs font-medium text-slate-200">
        {{ path || '未选择笔记' }}
      </span>
      <div class="inline-flex rounded-lg border border-white/10 bg-black/30 p-0.5 text-[10px]">
        <button
          type="button"
          class="rounded-md px-2 py-1"
          :class="mode === 'edit' ? 'bg-[rgb(var(--lz-accent)/0.3)] text-white' : 'text-slate-400'"
          @click="mode = 'edit'"
        >
          编辑
        </button>
        <button
          type="button"
          class="rounded-md px-2 py-1"
          :class="mode === 'split' ? 'bg-[rgb(var(--lz-accent)/0.3)] text-white' : 'text-slate-400'"
          @click="mode = 'split'"
        >
          分屏
        </button>
        <button
          type="button"
          class="rounded-md px-2 py-1"
          :class="mode === 'preview' ? 'bg-[rgb(var(--lz-accent)/0.3)] text-white' : 'text-slate-400'"
          @click="mode = 'preview'"
        >
          预览
        </button>
      </div>
      <button
        type="button"
        class="rounded-lg border border-white/10 px-2 py-1 text-[10px] text-slate-300 hover:bg-white/5"
        :disabled="!path"
        @click="emit('insert-wiki')"
      >
        插入 [[链接]]
      </button>
      <button
        type="button"
        class="rounded-lg border border-rose-400/25 px-2 py-1 text-[10px] text-rose-200/80 hover:bg-rose-500/10 disabled:opacity-40"
        :disabled="!path || path === 'README.md'"
        @click="emit('delete')"
      >
        删除
      </button>
    </div>

    <div
      v-if="path"
      class="grid min-h-0 flex-1"
      :class="mode === 'split' ? 'grid-cols-1 lg:grid-cols-2' : 'grid-cols-1'"
    >
      <textarea
        v-if="mode === 'edit' || mode === 'split'"
        :value="modelValue"
        class="min-h-0 flex-1 resize-none border-white/5 bg-transparent px-4 py-3 font-mono text-xs leading-relaxed text-slate-100 outline-none"
        :class="mode === 'split' ? 'border-r' : ''"
        placeholder="写 Markdown，支持 [[双链]]…"
        @input="emit('update:modelValue', ($event.target as HTMLTextAreaElement).value)"
        @mousemove="emit('mousemove', $event)"
        @mouseleave="emit('mouseleave')"
      />
      <div
        v-if="mode === 'preview' || mode === 'split'"
        class="min-h-0 overflow-y-auto px-4 py-3"
      >
        <p v-if="title" class="mb-2 text-lg font-semibold text-white">{{ title }}</p>
        <MarkdownView :content="modelValue" />
      </div>
    </div>
    <div
      v-else
      class="flex flex-1 items-center justify-center text-sm text-slate-500"
    >
      从左侧选择一篇笔记，或新建一篇
    </div>

    <div class="flex items-center gap-3 border-t border-white/8 px-3 py-1.5 text-[10px] text-slate-500">
      <span>{{ wordCount }} 字</span>
      <span v-if="saving" class="text-amber-200/80">保存中…</span>
      <span v-else-if="dirty" class="text-sky-200/80">未保存</span>
      <span v-else class="text-emerald-300/70">已同步</span>
      <span v-if="updatedAt" class="ml-auto">更新于 {{ updatedAt }}</span>
      <button
        type="button"
        class="rounded border border-white/10 px-2 py-0.5 text-slate-300 hover:bg-white/5 disabled:opacity-40"
        :disabled="!path || saving || !dirty"
        @click="emit('save')"
      >
        保存
      </button>
    </div>
  </section>
</template>
