<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGalaxies } from '../../api/orbit';
import {
  createAssignment,
  extractAssignmentFromResource,
  extractAssignmentQuestions,
  fetchSubmissions,
  fetchTeacherAssignments,
  gradeSubmission,
  type AssignmentItem,
  type AssignmentQuestion,
  type SubmissionItem,
} from '../../api/teacher';
import { fetchLessonResources, type LessonResourceItem } from '../../api/zone';
import { fetchBankQuestions, type BankQuestion } from '../../api/teacherSuite';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const assignments = ref<AssignmentItem[]>([]);
const submissions = ref<SubmissionItem[]>([]);
const galaxies = ref<{ slug: string; name: string }[]>([]);
const knowledgeResources = ref<LessonResourceItem[]>([]);
const selectedId = ref('');
const title = ref('');
const description = ref('');
const galaxySlug = ref('');
const dueAt = ref('');
const msg = ref('');
const loading = ref(false);
const error = ref('');
const expandedId = ref('');
const gradeDrafts = reactive<Record<string, { score: number; feedback: string }>>({});

const createMode = ref<'manual' | 'ai' | 'library' | 'bank'>('ai');
const extracting = ref(false);
const extractMsg = ref('');
const questions = ref<AssignmentQuestion[]>([]);
const sourceResourceId = ref('');
const selectedLibraryId = ref('');
const bankQuestions = ref<BankQuestion[]>([]);
const selectedBankIds = ref<string[]>([]);
const bankLoaded = ref(false);

const galaxyNameMap = computed(() => Object.fromEntries(galaxies.value.map((g) => [g.slug, g.name])));

const quizLibrary = computed(() =>
  knowledgeResources.value.filter((r) => {
    const kind = r.resource_kind || 'other';
    return kind === 'quiz' || kind === 'plan' || kind === 'other' || kind === 'book';
  }),
);

function isOverdue(a: AssignmentItem) {
  if (!a.due_at) return false;
  return new Date(a.due_at).getTime() < Date.now();
}

async function load() {
  if (!classId.value) {
    assignments.value = [];
    return;
  }
  loading.value = true;
  error.value = '';
  try {
    assignments.value = await fetchTeacherAssignments(classId.value);
  } catch (err) {
    error.value = err instanceof Error ? err.message : '加载作业失败';
  } finally {
    loading.value = false;
  }
}

async function loadLibrary() {
  try {
    knowledgeResources.value = await fetchLessonResources();
  } catch {
    knowledgeResources.value = [];
  }
}

function resetForm() {
  title.value = '';
  description.value = '';
  galaxySlug.value = '';
  dueAt.value = '';
  questions.value = [];
  sourceResourceId.value = '';
  selectedLibraryId.value = '';
  extractMsg.value = '';
}

async function handleExtractFile(event: Event) {
  const input = event.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  extracting.value = true;
  extractMsg.value = '正在读取文件并用 AI 提取题目…';
  try {
    const res = await extractAssignmentQuestions(file, title.value.trim() || file.name);
    questions.value = res.questions || [];
    if (!title.value.trim() && res.title_suggestion) title.value = res.title_suggestion;
    sourceResourceId.value = '';
    extractMsg.value = `${res.message}${res.provider ? ` · ${res.provider}` : ''}`;
  } catch (e) {
    extractMsg.value = e instanceof Error ? e.message : '提取失败';
    questions.value = [];
  } finally {
    extracting.value = false;
    input.value = '';
  }
}

async function handleExtractFromLibrary() {
  if (!selectedLibraryId.value) {
    extractMsg.value = '请先选择知识库资料';
    return;
  }
  extracting.value = true;
  extractMsg.value = '正在从教师知识库读取并用 AI 提取题目…';
  try {
    const res = await extractAssignmentFromResource(selectedLibraryId.value);
    questions.value = res.questions || [];
    const lib = knowledgeResources.value.find((r) => r.id === selectedLibraryId.value);
    if (!title.value.trim()) title.value = res.title_suggestion || lib?.title || '';
    if (!galaxySlug.value && lib?.galaxy_slug) galaxySlug.value = lib.galaxy_slug;
    sourceResourceId.value = selectedLibraryId.value;
    extractMsg.value = `${res.message}${res.provider ? ` · ${res.provider}` : ''}`;
  } catch (e) {
    extractMsg.value = e instanceof Error ? e.message : '提取失败';
    questions.value = [];
  } finally {
    extracting.value = false;
  }
}

async function loadBank() {
  if (bankLoaded.value) return;
  try {
    bankQuestions.value = await fetchBankQuestions();
    bankLoaded.value = true;
  } catch {
    bankQuestions.value = [];
  }
}

function addSelectedFromBank() {
  const picked = bankQuestions.value.filter((q) => selectedBankIds.value.includes(q.id));
  if (!picked.length) {
    extractMsg.value = '请先勾选题目';
    return;
  }
  const base = questions.value.length;
  questions.value = [
    ...questions.value,
    ...picked.map((q, i) => ({
      index: base + i + 1,
      stem: q.stem,
      kind: q.kind,
      options: q.options || [],
      answer: q.answer,
      score: 10,
    })),
  ];
  selectedBankIds.value = [];
  extractMsg.value = `已从题库加入 ${picked.length} 道题目`;
}

function removeQuestion(idx: number) {
  questions.value = questions.value.filter((_, i) => i !== idx).map((q, i) => ({ ...q, index: i + 1 }));
}

function updateStem(idx: number, stem: string) {
  const list = [...questions.value];
  list[idx] = { ...list[idx], stem };
  questions.value = list;
}

async function handleCreate() {
  if (!title.value.trim() || !classId.value) {
    msg.value = '请填写标题并选择班级';
    return;
  }
  if (createMode.value !== 'manual' && !questions.value.length && !description.value.trim()) {
    msg.value = '请先提取题目，或填写作业说明';
    return;
  }
  msg.value = '';
  try {
    await createAssignment({
      class_id: classId.value,
      title: title.value,
      description: description.value,
      galaxy_slug: galaxySlug.value || undefined,
      due_at: dueAt.value ? new Date(dueAt.value).toISOString() : undefined,
      questions: questions.value,
      source_resource_id: sourceResourceId.value || undefined,
    });
    resetForm();
    msg.value = '作业已发布';
    await load();
  } catch {
    msg.value = '发布失败';
  }
}

async function openSubmissions(id: string) {
  selectedId.value = id;
  expandedId.value = '';
  submissions.value = await fetchSubmissions(id);
  for (const s of submissions.value) {
    gradeDrafts[s.id] = {
      score: s.score ?? 85,
      feedback: s.feedback || '',
    };
  }
}

async function handleGrade(sub: SubmissionItem) {
  if (!selectedId.value) return;
  const draft = gradeDrafts[sub.id] || { score: 85, feedback: '' };
  await gradeSubmission(selectedId.value, sub.id, draft.score, draft.feedback);
  submissions.value = await fetchSubmissions(selectedId.value);
  for (const s of submissions.value) {
    gradeDrafts[s.id] = { score: s.score ?? 85, feedback: s.feedback || '' };
  }
}

watch(classId, () => {
  selectedId.value = '';
  submissions.value = [];
  void load();
});

onMounted(async () => {
  galaxies.value = (await fetchGalaxies()).map((g) => ({ slug: g.slug, name: g.name }));
  await Promise.all([load(), loadLibrary()]);
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="作业管理" subtitle="上传文件 AI 抽题 · 选用教师知识库 · 发布与批改" />

    <section class="t-card glass-edge p-5">
      <div class="flex items-center justify-between gap-2">
        <div class="t-tabs">
          <button
            v-for="m in [
              { key: 'ai', label: 'AI 抽题发布' },
              { key: 'library', label: '从知识库发布' },
              { key: 'bank', label: '从题库选题' },
              { key: 'manual', label: '手动布置' },
            ]"
            :key="m.key"
            type="button"
            class="t-tab"
            :class="{ 'is-active': createMode === m.key }"
            @click="createMode = m.key as 'manual' | 'ai' | 'library' | 'bank'; m.key === 'bank' && loadBank()"
          >
            {{ m.label }}
          </button>
        </div>
        <span class="t-kicker hidden sm:inline">New Assignment</span>
      </div>

      <div class="mt-4 grid gap-3 md:grid-cols-2">
        <input v-model="title" placeholder="作业标题" class="t-input" />
        <select v-model="galaxySlug" class="t-input cursor-pointer">
          <option value="">关联星系（可选）</option>
          <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
        </select>
        <input v-model="dueAt" type="datetime-local" class="t-input" />
        <textarea
          v-model="description"
          placeholder="作业说明（可选；有题目时可不填）"
          class="t-input md:col-span-2"
          rows="2"
        />
      </div>

      <div v-if="createMode === 'ai'" class="mt-4">
        <label
          class="flex cursor-pointer flex-col items-center gap-1 rounded-xl border border-dashed border-t-accent2/35 bg-t-accent2/5 px-4 py-6 text-sm text-t-accent2 transition hover:bg-t-accent2/10"
          :class="extracting ? 'pointer-events-none opacity-60' : ''"
        >
          <svg viewBox="0 0 24 24" class="h-6 w-6 opacity-80" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M12 16V4m0 0 4 4m-4-4-4 4" />
            <path d="M4 16v3a1 1 0 0 0 1 1h14a1 1 0 0 0 1-1v-3" />
          </svg>
          <span>{{ extracting ? 'AI 提取中…' : '上传 PDF / 图片 / 文本，AI（豆包/DeepSeek）提取题目' }}</span>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg,.webp,.md,.txt,image/*"
            class="hidden"
            @change="handleExtractFile"
          />
        </label>
      </div>

      <div v-else-if="createMode === 'library'" class="mt-4 space-y-3">
        <select v-model="selectedLibraryId" class="t-input cursor-pointer">
          <option value="">选择教师知识库资料（题库/教案/书本等）</option>
          <option v-for="r in quizLibrary" :key="r.id" :value="r.id">
            [{{ r.resource_kind || 'other' }}] {{ r.title }}
          </option>
        </select>
        <button
          type="button"
          class="t-btn t-btn--soft t-btn--md"
          :disabled="extracting || !selectedLibraryId"
          @click="handleExtractFromLibrary"
        >
          {{ extracting ? '提取中…' : '从知识库提取题目' }}
        </button>
        <TeacherEmptyState
          v-if="!quizLibrary.length"
          title="知识库暂无可用资料"
          description="请先在「教师知识库」上传题库或教案"
        />
      </div>

      <div v-else-if="createMode === 'bank'" class="mt-4 space-y-3">
        <div class="max-h-72 space-y-2 overflow-y-auto">
          <label
            v-for="q in bankQuestions"
            :key="q.id"
            class="flex cursor-pointer items-start gap-3 rounded-xl border border-t-line/10 bg-t-s1/30 px-3 py-2.5 transition hover:border-t-accent/25"
          >
            <input v-model="selectedBankIds" type="checkbox" :value="q.id" class="t-check mt-0.5 rounded" />
            <div class="min-w-0">
              <p class="text-xs text-t-1">{{ q.stem }}</p>
              <p class="mt-0.5 text-[10px] text-t-3">{{ q.kind }} · {{ q.difficulty }}<template v-if="q.answer"> · 答案：{{ q.answer }}</template></p>
            </div>
          </label>
          <TeacherEmptyState v-if="!bankQuestions.length" title="题库为空" description="请先在「题库管理」中沉淀题目" />
        </div>
        <button type="button" class="t-btn t-btn--soft t-btn--md" :disabled="!selectedBankIds.length" @click="addSelectedFromBank">
          加入所选题目（{{ selectedBankIds.length }}）
        </button>
      </div>

      <p v-if="extractMsg" class="mt-2 text-xs text-t-accent2">{{ extractMsg }}</p>

      <div v-if="questions.length" class="mt-4 space-y-2">
        <h4 class="text-sm font-semibold text-t-1">已提取题目（{{ questions.length }}）· 可编辑后发布</h4>
        <div v-for="(q, idx) in questions" :key="idx" class="t-card--flat rounded-xl border border-t-line/10 px-3 py-3">
          <div class="flex items-start justify-between gap-2">
            <span class="t-badge t-badge--neutral shrink-0">#{{ q.index || idx + 1 }} · {{ q.kind || 'short' }}</span>
            <button type="button" class="text-[11px] text-t-danger transition hover:opacity-75" @click="removeQuestion(idx)">移除</button>
          </div>
          <textarea
            :value="q.stem"
            rows="2"
            class="t-input mt-2 text-xs"
            @input="updateStem(idx, ($event.target as HTMLTextAreaElement).value)"
          />
          <ul v-if="q.options?.length" class="mt-1 space-y-0.5 text-[11px] text-t-3">
            <li v-for="(opt, oi) in q.options" :key="oi">{{ opt }}</li>
          </ul>
          <p v-if="q.answer" class="mt-1 text-[11px] text-t-ok/90">参考答案：{{ q.answer }}</p>
        </div>
      </div>

      <button
        type="button"
        class="t-btn t-btn--primary t-btn--md mt-4"
        :disabled="!title.trim() || !classId"
        @click="handleCreate"
      >
        发布作业
      </button>
      <p v-if="msg" class="mt-2 text-xs text-t-accent">{{ msg }}</p>
    </section>

    <TeacherLoading v-if="loading" :rows="4" />
    <p v-else-if="error" class="text-sm text-t-danger">{{ error }}</p>

    <section v-else class="t-card glass-edge p-5">
      <div class="flex items-baseline justify-between gap-2">
        <h3 class="text-[15px] font-semibold text-t-1">作业列表</h3>
        <span class="t-kicker">{{ assignments.length }} Items</span>
      </div>
      <div class="mt-3 space-y-2">
        <div
          v-for="a in assignments"
          :key="a.id"
          class="flex flex-wrap items-center justify-between gap-3 rounded-xl border px-4 py-3 transition"
          :class="selectedId === a.id ? 'border-t-accent/40 bg-t-accent/6' : 'border-t-line/10 bg-t-s1/30 hover:border-t-accent/25'"
        >
          <div>
            <div class="flex flex-wrap items-center gap-2">
              <p class="text-sm font-medium text-t-1">{{ a.title }}</p>
              <span v-if="isOverdue(a)" class="t-badge t-badge--danger">已过期</span>
              <span v-if="a.questions?.length" class="t-badge t-badge--info">{{ a.questions.length }} 题</span>
            </div>
            <p class="mt-1 text-[11px] text-t-3">
              <template v-if="a.galaxy_slug">{{ galaxyNameMap[a.galaxy_slug] || a.galaxy_slug }} · </template>
              提交 {{ a.submission_count }} ·
              {{ a.due_at ? `截止 ${a.due_at.slice(0, 16).replace('T', ' ')}` : `创建 ${a.created_at?.slice(0, 16)?.replace('T', ' ')}` }}
            </p>
          </div>
          <button type="button" class="t-btn t-btn--soft t-btn--sm" @click="openSubmissions(a.id)">查看提交</button>
        </div>
        <TeacherEmptyState v-if="!assignments.length" title="暂无作业" />
      </div>
    </section>

    <section v-if="selectedId" class="t-card glass-edge p-5">
      <h3 class="text-[15px] font-semibold text-t-1">提交批改</h3>
      <div class="mt-3 space-y-3">
        <div v-for="s in submissions" :key="s.id" class="rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-3">
          <div class="flex flex-wrap items-center justify-between gap-2">
            <p class="text-sm font-medium text-t-1">{{ s.student_name }}</p>
            <span class="text-[11px] text-t-3">{{ s.status }} · {{ s.submitted_at?.slice(0, 16)?.replace('T', ' ') || '—' }}</span>
          </div>
          <button type="button" class="mt-2 text-[11px] text-t-accent transition hover:opacity-80" @click="expandedId = expandedId === s.id ? '' : s.id">
            {{ expandedId === s.id ? '收起' : '展开内容' }}
          </button>
          <div v-if="expandedId === s.id" class="mt-2 space-y-2">
            <p class="whitespace-pre-wrap text-xs text-t-2">{{ s.content }}</p>
            <a v-if="s.attachment_url" :href="s.attachment_url" target="_blank" class="text-xs text-t-accent">附件</a>
          </div>
          <div class="mt-3 flex flex-wrap items-end gap-2">
            <label class="flex items-center gap-1 text-[11px] text-t-3">
              分数
              <input
                v-model.number="gradeDrafts[s.id].score"
                type="number"
                min="0"
                max="100"
                class="t-input w-20 py-1"
              />
            </label>
            <input v-model="gradeDrafts[s.id].feedback" placeholder="评语" class="t-input min-w-[180px] flex-1 py-1" />
            <button
              type="button"
              class="t-btn t-btn--sm border-t-ok/40 bg-t-ok/12 text-t-ok hover:bg-t-ok/20"
              @click="handleGrade(s)"
            >
              提交批改
            </button>
          </div>
        </div>
        <TeacherEmptyState v-if="!submissions.length" title="暂无提交" />
      </div>
    </section>
  </div>
</template>
