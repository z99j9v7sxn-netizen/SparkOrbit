<script setup lang="ts">
import { onMounted, ref, watch } from 'vue';
import { gradeAnswers } from '../../api/ai';
import {
  createMistake,
  createMistakesBatch,
  fetchMistakes,
  importMistakePhoto,
  ocrMistakePhoto,
  removeMistake,
  type MistakeDraft,
  type MistakeItem,
} from '../../api/zone';
import type { MistakeTutorPayload } from '../../api/digitalTutor';
import DigitalTutorPanel from './DigitalTutorPanel.vue';
import { LzButton, LzCard, LzEmptyState, LzInput, LzTextarea } from './ui';

const props = defineProps<{
  pendingTutor?: MistakeTutorPayload | null;
}>();

const emit = defineEmits<{
  (e: 'simulate', topic: string): void;
  (e: 'tutor-closed'): void;
}>();

const items = ref<MistakeItem[]>([]);
const question = ref('');
const studentAnswer = ref('');
const correctAnswer = ref('');
const subject = ref('');
const explaining = ref('');
const loading = ref(false);
const ocrHint = ref('');
const tutorMistake = ref<MistakeTutorPayload | null>(null);

function openTutor(payload: MistakeTutorPayload) {
  tutorMistake.value = { ...payload };
}

function closeTutor() {
  tutorMistake.value = null;
  emit('tutor-closed');
}

watch(
  () => props.pendingTutor,
  (p) => {
    if (p?.question) openTutor(p);
  },
  { immediate: true },
);

async function onPhotoOcr(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  if (!file) return;
  ocrHint.value = '识别中…';
  try {
    const res = await ocrMistakePhoto(file);
    if (res.question) question.value = res.question;
    if (res.subject_guess) subject.value = res.subject_guess;
    if (res.correct_answer_guess) correctAnswer.value = res.correct_answer_guess;
    ocrHint.value = res.vision_unavailable ? '视觉识别不可用，请手动输入' : '已识别，请核对后提交';
  } catch (e) {
    ocrHint.value = e instanceof Error ? e.message : '识别失败';
  }
}

// ---- 拍照批量导入：识别 → 预览勾选 → 批量入库 ----
const importDrafts = ref<MistakeDraft[]>([]);
const importChecked = ref<boolean[]>([]);
const importing = ref(false);
const importSaving = ref(false);

async function onBatchImport(ev: Event) {
  const file = (ev.target as HTMLInputElement).files?.[0];
  (ev.target as HTMLInputElement).value = '';
  if (!file) return;
  importing.value = true;
  ocrHint.value = '批量识别中（可能需要十几秒）…';
  try {
    const res = await importMistakePhoto(file);
    importDrafts.value = res.items;
    importChecked.value = res.items.map(() => true);
    ocrHint.value = `识别出 ${res.items.length} 道题，请核对后确认导入`;
  } catch (e) {
    ocrHint.value = e instanceof Error ? e.message : '批量识别失败';
  } finally {
    importing.value = false;
  }
}

async function confirmImport() {
  const items = importDrafts.value.filter((_, i) => importChecked.value[i]);
  if (!items.length) return;
  importSaving.value = true;
  try {
    await createMistakesBatch(items);
    ocrHint.value = `已导入 ${items.length} 道错题，将进入复习队列`;
    importDrafts.value = [];
    importChecked.value = [];
    await load();
  } catch (e) {
    ocrHint.value = e instanceof Error ? e.message : '导入失败';
  } finally {
    importSaving.value = false;
  }
}

async function load() {
  try {
    items.value = await fetchMistakes();
  } catch {
    items.value = [];
  }
}

async function add() {
  if (!question.value.trim()) return;
  loading.value = true;
  try {
    await createMistake({
      question: question.value.trim(),
      student_answer: studentAnswer.value.trim(),
      correct_answer: correctAnswer.value.trim(),
      subject: subject.value.trim(),
      note: '',
    });
    question.value = '';
    studentAnswer.value = '';
    correctAnswer.value = '';
    subject.value = '';
    await load();
  } finally {
    loading.value = false;
  }
}

async function explain(item: MistakeItem) {
  explaining.value = '讲解生成中…';
  try {
    const res = await gradeAnswers([
      {
        question: item.question,
        reference_answer: item.correct_answer,
        student_answer: item.student_answer || '未作答',
      },
    ]);
    explaining.value = res.items[0]?.feedback || res.summary || '暂无讲解';
  } catch (e) {
    explaining.value = e instanceof Error ? e.message : '讲解失败';
  }
}

function openDigitalTutor(item: MistakeItem) {
  openTutor({
    mistake_id: item.id,
    question: item.question,
    student_answer: item.student_answer,
    correct_answer: item.correct_answer,
    note: item.note,
    subject: item.subject,
  });
}

async function remove(id: string) {
  await removeMistake(id);
  await load();
}

function simulate(item: MistakeItem) {
  emit('simulate', item.subject || item.question.slice(0, 40));
}

onMounted(load);

defineExpose({ openTutor, closeTutor, reload: load });
</script>

<template>
  <div class="dock-panel space-y-4">
    <template v-if="tutorMistake">
      <div class="flex items-center justify-between gap-2">
        <p class="lz-desc">错题本 · 数字人分镜讲解</p>
        <LzButton variant="ghost" size="sm" @click="closeTutor">返回列表</LzButton>
      </div>
      <DigitalTutorPanel
        :mistake="tutorMistake"
        :planet-slug="tutorMistake.planet_slug"
        :planet-name="tutorMistake.subject || tutorMistake.planet_slug"
        :auto-start="false"
      />
    </template>

    <template v-else>
      <header class="space-y-1">
        <p class="lz-caption lz-accent-text uppercase tracking-[0.28em]">Mistake Book</p>
        <h3 class="lz-title">错题本</h3>
        <p class="lz-desc">
          归档错题，并可一键生成分镜讲稿：DeepSeek 分析 + 实时虚拟人朗读 + GSAP 切幕（无需等待短视频）。
        </p>
      </header>

      <div class="space-y-2">
        <div class="flex gap-2">
          <label class="flex-1 cursor-pointer rounded-[var(--radius-ctl)] border border-dashed border-[rgb(var(--lz-accent)/0.35)] px-3 py-2 text-center text-xs text-[rgb(var(--lz-accent-bright))] transition hover:bg-[rgb(var(--lz-accent)/0.1)]">
            <img class="inline-block h-4 w-4 align-[-3px]" src="/icons/camera.svg" alt="" aria-hidden="true" /> 拍照识别题目
            <input type="file" accept="image/*" capture="environment" class="hidden" @change="onPhotoOcr" />
          </label>
          <label class="flex-1 cursor-pointer rounded-[var(--radius-ctl)] border border-dashed border-amber-400/35 px-3 py-2 text-center text-xs text-amber-200 transition hover:bg-amber-500/10">
            📷 整页批量导入
            <input type="file" accept="image/*" class="hidden" :disabled="importing" @change="onBatchImport" />
          </label>
        </div>
        <p v-if="ocrHint" class="lz-caption">{{ ocrHint }}</p>

        <!-- 批量导入预览 -->
        <div v-if="importDrafts.length" class="space-y-2 rounded-[var(--radius-card)] border border-amber-400/25 bg-amber-500/5 p-3">
          <p class="lz-subtitle">导入预览（勾选要保留的题目）</p>
          <div v-for="(d, i) in importDrafts" :key="i" class="flex items-start gap-2">
            <input v-model="importChecked[i]" type="checkbox" class="mt-1 shrink-0 rounded" />
            <div class="min-w-0 flex-1 space-y-1">
              <LzTextarea v-model="d.question" :rows="2" placeholder="题目" />
              <div class="grid grid-cols-2 gap-1.5">
                <LzInput v-model="d.correct_answer" placeholder="正确答案" />
                <LzInput v-model="d.subject" placeholder="学科" />
              </div>
            </div>
          </div>
          <div class="flex gap-2">
            <LzButton variant="primary" size="sm" :loading="importSaving" @click="confirmImport">
              确认导入（{{ importChecked.filter(Boolean).length }} 道）
            </LzButton>
            <LzButton variant="ghost" size="sm" @click="importDrafts = []; importChecked = []">取消</LzButton>
          </div>
        </div>
        <LzInput v-model="subject" placeholder="学科（可选）" />
        <LzTextarea v-model="question" :rows="2" placeholder="错题题目" />
        <LzTextarea v-model="studentAnswer" :rows="1" placeholder="你的作答" />
        <LzTextarea v-model="correctAnswer" :rows="1" placeholder="正确答案" />
        <LzButton variant="primary" block :disabled="loading" @click="add">加入错题本</LzButton>
      </div>
      <p v-if="explaining" class="lz-card lz-desc p-3">{{ explaining }}</p>
      <div class="max-h-72 space-y-2 overflow-auto">
        <LzCard v-for="item in items" :key="item.id" padding="sm" hover>
          <p class="lz-caption">{{ item.subject || '未分类' }}</p>
          <p class="lz-subtitle mt-1">{{ item.question }}</p>
          <div class="mt-2 flex flex-wrap gap-2">
            <LzButton variant="soft" size="sm" @click="openDigitalTutor(item)">数字人讲这道</LzButton>
            <LzButton variant="ghost" size="sm" @click="explain(item)">智能讲解</LzButton>
            <LzButton variant="ghost" size="sm" @click="simulate(item)">替身预演</LzButton>
            <LzButton variant="danger" size="sm" @click="remove(item.id)">删除</LzButton>
          </div>
        </LzCard>
        <LzEmptyState v-if="!items.length" icon="📖" title="暂无错题" desc="拍照或手动录入第一道错题，建立你的错题档案" />
      </div>
    </template>
  </div>
</template>
