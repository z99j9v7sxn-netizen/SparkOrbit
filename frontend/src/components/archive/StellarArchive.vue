<script setup lang="ts">
import { ref } from 'vue';
import { polishArchive, type ArchivePolishResult } from '../../api/zone';
import { LzButton, LzSection } from '../learning/ui';

const props = withDefaults(defineProps<{ embedded?: boolean }>(), { embedded: false });

const emit = defineEmits<{
  (e: 'close'): void;
  (e: 'scan'): void;
}>();

const originalText = ref('');
const selectedFile = ref<File | null>(null);
const fileInputRef = ref<HTMLInputElement | null>(null);
const result = ref<ArchivePolishResult | null>(null);
const isScanning = ref(false);
const error = ref('');

function onFilePick(event: Event) {
  const input = event.target as HTMLInputElement;
  selectedFile.value = input.files?.[0] || null;
  result.value = null;
  error.value = '';
}

function clearFile() {
  selectedFile.value = null;
  if (fileInputRef.value) fileInputRef.value.value = '';
}

async function startScan() {
  if (!originalText.value.trim() && !selectedFile.value) return;
  isScanning.value = true;
  result.value = null;
  error.value = '';
  emit('scan');
  try {
    result.value = await polishArchive(originalText.value, selectedFile.value);
    originalText.value = result.value.original;
  } catch (scanError) {
    error.value = scanError instanceof Error ? scanError.message : '论文润色失败，请稍后重试';
  } finally {
    isScanning.value = false;
  }
}
</script>

<template>
  <component :is="embedded ? 'div' : 'aside'" :class="embedded ? 'flex h-full w-full flex-col' : 'cosmic-drawer absolute right-0 top-0 z-20 flex h-full w-[420px] flex-col border-l border-white/10 p-5 shadow-2xl'">
    <header v-if="!embedded" class="mb-4 flex items-center justify-between">
      <div class="flex items-center gap-3">
        <div class="lz-accent-text flex h-8 w-8 items-center justify-center rounded-full bg-[rgb(var(--lz-accent)/0.15)]"><img class="h-5 w-5" src="/icons/archive.svg" alt="" aria-hidden="true" /></div>
        <div>
          <h2 class="text-lg font-bold text-white text-glow">恒星档案馆</h2>
          <p class="lz-caption lz-accent-text uppercase tracking-widest opacity-80">Stellar Archive · 论文润色</p>
        </div>
      </div>
      <LzButton variant="ghost" size="sm" @click="emit('close')">✕</LzButton>
    </header>

    <div class="flex-1 space-y-4 overflow-auto">
      <LzSection title="论文原文" desc="支持 PDF、DOCX 与 TXT，单个文件不超过 15 MB" boxed>
        <template #actions>
          <label class="lz-btn lz-btn--soft lz-btn--sm cursor-pointer">
            选择文档
            <input
              ref="fileInputRef"
              class="sr-only"
              type="file"
              accept=".pdf,.doc,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain"
              @change="onFilePick"
            />
          </label>
        </template>
        <div v-if="selectedFile" class="lz-card lz-card--flat mb-3 flex items-center justify-between px-3 py-2">
          <div class="min-w-0">
            <p class="lz-subtitle truncate">{{ selectedFile.name }}</p>
            <p class="lz-caption">{{ (selectedFile.size / 1024 / 1024).toFixed(2) }} MB</p>
          </div>
          <LzButton variant="danger" size="sm" class="ml-3 shrink-0" @click="clearFile">移除</LzButton>
        </div>
        <textarea
          v-model="originalText"
          class="lz-input h-52 w-full resize-y p-4 leading-7 md:h-64"
          placeholder="粘贴论文内容，或选择文档后直接扫描"
        />
        <p v-if="error" class="mt-3 rounded-[var(--radius-ctl)] border border-rose-400/20 bg-rose-400/10 px-3 py-2 text-xs text-rose-200">
          {{ error }}
        </p>
        <LzButton
          variant="primary"
          size="lg"
          block
          class="mt-4"
          :loading="isScanning"
          :disabled="!originalText.trim() && !selectedFile"
          @click="startScan"
        >
          {{ isScanning ? '正在解析并润色论文（长文档约需 1–2 分钟）...' : '启动论文润色' }}
        </LzButton>
        <p v-if="isScanning" class="lz-caption mt-2 text-center">
          长文档会优先返回逐条修改建议，请耐心等待
        </p>
      </LzSection>

      <div
        v-if="result"
        class="lz-fade-up space-y-5 rounded-[var(--radius-panel)] border border-[rgb(var(--lz-accent)/0.3)] bg-[var(--surface-2)] p-4 md:p-6"
      >
        <LzSection title="润色全文">
          <div class="max-h-72 overflow-auto whitespace-pre-wrap rounded-[var(--radius-card)] border border-emerald-400/15 bg-emerald-400/[0.06] p-4 text-sm leading-7 text-emerald-50">
            {{ result.revised }}
          </div>
        </LzSection>
        <LzSection v-if="result.issues.length" title="逐项修改说明">
          <div class="grid gap-3 md:grid-cols-2">
            <article
              v-for="(issue, index) in result.issues"
              :key="`${issue.original}-${index}`"
              class="lz-card lz-card--flat p-4"
            >
              <p v-if="issue.original" class="text-xs leading-6 text-rose-200 line-through">{{ issue.original }}</p>
              <p class="mt-2 text-sm leading-6 text-emerald-100">{{ issue.suggestion }}</p>
              <p class="lz-caption mt-2">{{ issue.reason }}</p>
            </article>
          </div>
        </LzSection>
        <LzSection v-if="result.originality_tips.length" title="原创性写作建议">
          <ol class="grid gap-2 md:grid-cols-2">
            <li v-for="(tip, index) in result.originality_tips" :key="tip" class="lz-card lz-card--flat lz-desc p-3">
              {{ index + 1 }}. {{ tip }}
            </li>
          </ol>
        </LzSection>
      </div>
    </div>
  </component>
</template>
