<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { fetchGalaxies } from '../../api/orbit';
import { fetchTeacherAssignments, type AssignmentItem } from '../../api/teacher';
import {
  aiGenerateBankQuestions,
  bulkCreateBankQuestions,
  createBankQuestion,
  deleteBankQuestion,
  fetchBankQuestions,
  importBankFromAssignment,
  type BankQuestion,
  type BankQuestionDraft,
} from '../../api/teacherSuite';
import { parseApiError } from '../../api/errors';
import TeacherEmptyState from './TeacherEmptyState.vue';
import TeacherLoading from './TeacherLoading.vue';
import TeacherPageHeader from './TeacherPageHeader.vue';
import { useTeacherClassStore } from '../../stores/teacherClass';

const classStore = useTeacherClassStore();
const { classId } = storeToRefs(classStore);

const questions = ref<BankQuestion[]>([]);
const galaxies = ref<{ slug: string; name: string }[]>([]);
const assignments = ref<AssignmentItem[]>([]);
const loading = ref(false);
const msg = ref('');
const error = ref('');

const filterGalaxy = ref('');
const filterDifficulty = ref('');
const search = ref('');

const addMode = ref<'manual' | 'ai' | 'assignment'>('ai');

// 手动添加
const manualStem = ref('');
const manualKind = ref('short');
const manualAnswer = ref('');
const manualOptions = ref('');
const manualDifficulty = ref('medium');
const manualGalaxy = ref('');

// AI 生成
const aiTopic = ref('');
const aiCount = ref(5);
const aiDifficulty = ref('medium');
const aiGalaxy = ref('');
const aiGenerating = ref(false);
const aiCandidates = ref<BankQuestionDraft[]>([]);
const aiMsg = ref('');

// 从作业收藏
const importAssignmentId = ref('');
const importing = ref(false);

const galaxyNameMap = computed(() => Object.fromEntries(galaxies.value.map((g) => [g.slug, g.name])));

const difficultyLabel: Record<string, string> = { easy: '简单', medium: '中等', hard: '困难' };

async function load() {
  loading.value = true;
  error.value = '';
  try {
    questions.value = await fetchBankQuestions({
      galaxy_slug: filterGalaxy.value,
      difficulty: filterDifficulty.value,
      q: search.value.trim(),
    });
  } catch (e) {
    error.value = parseApiError(e, '加载题库失败');
  } finally {
    loading.value = false;
  }
}

async function handleManualCreate() {
  if (!manualStem.value.trim()) return;
  msg.value = '';
  try {
    await createBankQuestion({
      stem: manualStem.value,
      kind: manualKind.value,
      answer: manualAnswer.value,
      options: manualOptions.value
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      difficulty: manualDifficulty.value,
      galaxy_slug: manualGalaxy.value,
      class_id: classId.value,
      source: 'manual',
    });
    manualStem.value = '';
    manualAnswer.value = '';
    manualOptions.value = '';
    msg.value = '题目已入库';
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '入库失败');
  }
}

async function handleAiGenerate() {
  if (!aiTopic.value.trim()) return;
  aiGenerating.value = true;
  aiMsg.value = '';
  aiCandidates.value = [];
  try {
    const res = await aiGenerateBankQuestions({
      topic: aiTopic.value,
      count: aiCount.value,
      difficulty: aiDifficulty.value,
      galaxy_slug: aiGalaxy.value,
    });
    aiCandidates.value = res.questions || [];
    aiMsg.value = res.message;
  } catch (e) {
    aiMsg.value = parseApiError(e, 'AI 生成失败');
  } finally {
    aiGenerating.value = false;
  }
}

function removeCandidate(idx: number) {
  aiCandidates.value = aiCandidates.value.filter((_, i) => i !== idx);
}

async function handleSaveCandidates() {
  if (!aiCandidates.value.length) return;
  msg.value = '';
  try {
    const res = await bulkCreateBankQuestions({
      questions: aiCandidates.value,
      class_id: classId.value,
      galaxy_slug: aiGalaxy.value,
      source: 'ai',
    });
    msg.value = `已入库 ${res.created} 道题目`;
    aiCandidates.value = [];
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '批量入库失败');
  }
}

async function handleImportFromAssignment() {
  if (!importAssignmentId.value) return;
  importing.value = true;
  msg.value = '';
  try {
    const res = await importBankFromAssignment(importAssignmentId.value, classId.value);
    msg.value = `已从作业收藏 ${res.created} 道题目`;
    await load();
  } catch (e) {
    msg.value = parseApiError(e, '收藏失败');
  } finally {
    importing.value = false;
  }
}

async function handleDelete(id: string) {
  try {
    await deleteBankQuestion(id);
    questions.value = questions.value.filter((q) => q.id !== id);
  } catch (e) {
    msg.value = parseApiError(e, '删除失败');
  }
}

async function loadAssignments() {
  if (!classId.value) {
    assignments.value = [];
    return;
  }
  try {
    assignments.value = (await fetchTeacherAssignments(classId.value)).filter((a) => a.questions?.length);
  } catch {
    assignments.value = [];
  }
}

watch(classId, () => void loadAssignments());
watch([filterGalaxy, filterDifficulty], () => void load());

onMounted(async () => {
  galaxies.value = (await fetchGalaxies()).map((g) => ({ slug: g.slug, name: g.name }));
  await Promise.all([load(), loadAssignments()]);
});
</script>

<template>
  <div class="space-y-4">
    <TeacherPageHeader title="题库管理" subtitle="沉淀可复用题目 · AI 生成 · 作业收藏 · 发布作业时可直接选题">
      <template #actions>
        <input v-model="search" placeholder="搜索题干 / 答案" class="t-input w-48" @keyup.enter="load" />
        <button type="button" class="t-btn t-btn--ghost t-btn--sm" @click="load">搜索</button>
      </template>
    </TeacherPageHeader>

    <!-- 入库区 -->
    <section class="t-card glass-edge p-5">
      <div class="flex items-center justify-between gap-2">
        <div class="t-tabs">
          <button
            v-for="m in [
              { key: 'ai', label: 'AI 生成' },
              { key: 'assignment', label: '从作业收藏' },
              { key: 'manual', label: '手动添加' },
            ]"
            :key="m.key"
            type="button"
            class="t-tab"
            :class="{ 'is-active': addMode === m.key }"
            @click="addMode = m.key as 'manual' | 'ai' | 'assignment'"
          >
            {{ m.label }}
          </button>
        </div>
        <span class="t-kicker hidden sm:inline">Add Questions</span>
      </div>

      <div v-if="addMode === 'ai'" class="mt-4 space-y-3">
        <div class="grid gap-3 md:grid-cols-4">
          <input v-model="aiTopic" placeholder="出题主题，如：二叉树遍历" class="t-input md:col-span-2" />
          <select v-model="aiDifficulty" class="t-input cursor-pointer">
            <option value="easy">简单</option>
            <option value="medium">中等</option>
            <option value="hard">困难</option>
          </select>
          <div class="flex items-center gap-2">
            <input v-model.number="aiCount" type="number" min="1" max="20" class="t-input w-20" />
            <span class="text-xs text-t-3">道</span>
            <select v-model="aiGalaxy" class="t-input flex-1 cursor-pointer">
              <option value="">关联星系</option>
              <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
            </select>
          </div>
        </div>
        <button
          type="button"
          class="t-btn t-btn--primary t-btn--md"
          :disabled="aiGenerating || !aiTopic.trim()"
          @click="handleAiGenerate"
        >
          {{ aiGenerating ? 'AI 生成中…' : 'AI 生成候选题' }}
        </button>
        <p v-if="aiMsg" class="text-xs text-t-accent2">{{ aiMsg }}</p>

        <div v-if="aiCandidates.length" class="space-y-2">
          <h4 class="text-sm font-semibold text-t-1">候选题目（{{ aiCandidates.length }}）· 确认后入库</h4>
          <div v-for="(q, idx) in aiCandidates" :key="idx" class="t-card--flat rounded-xl border border-t-line/10 px-3 py-3">
            <div class="flex items-start justify-between gap-2">
              <span class="t-badge t-badge--neutral shrink-0">#{{ idx + 1 }} · {{ q.kind || 'short' }}</span>
              <button type="button" class="text-[11px] text-t-danger transition hover:opacity-75" @click="removeCandidate(idx)">移除</button>
            </div>
            <p class="mt-2 text-xs text-t-1">{{ q.stem }}</p>
            <ul v-if="q.options?.length" class="mt-1 space-y-0.5 text-[11px] text-t-3">
              <li v-for="(opt, oi) in q.options" :key="oi">{{ opt }}</li>
            </ul>
            <p v-if="q.answer" class="mt-1 text-[11px] text-t-ok/90">参考答案：{{ q.answer }}</p>
            <p v-if="q.explanation" class="mt-1 text-[11px] text-t-3">解析：{{ q.explanation }}</p>
          </div>
          <button type="button" class="t-btn t-btn--primary t-btn--md" @click="handleSaveCandidates">
            全部入库（{{ aiCandidates.length }}）
          </button>
        </div>
      </div>

      <div v-else-if="addMode === 'assignment'" class="mt-4 space-y-3">
        <select v-model="importAssignmentId" class="t-input cursor-pointer">
          <option value="">选择含结构化题目的历史作业</option>
          <option v-for="a in assignments" :key="a.id" :value="a.id">
            {{ a.title }}（{{ a.questions?.length || 0 }} 题）
          </option>
        </select>
        <button
          type="button"
          class="t-btn t-btn--soft t-btn--md"
          :disabled="importing || !importAssignmentId"
          @click="handleImportFromAssignment"
        >
          {{ importing ? '收藏中…' : '收藏进题库' }}
        </button>
        <TeacherEmptyState v-if="!assignments.length" title="暂无含题目的作业" description="先在作业管理中用 AI 抽题发布作业" />
      </div>

      <div v-else class="mt-4 space-y-3">
        <div class="grid gap-3 md:grid-cols-3">
          <select v-model="manualKind" class="t-input cursor-pointer">
            <option value="choice">选择题</option>
            <option value="short">简答题</option>
            <option value="judge">判断题</option>
          </select>
          <select v-model="manualDifficulty" class="t-input cursor-pointer">
            <option value="easy">简单</option>
            <option value="medium">中等</option>
            <option value="hard">困难</option>
          </select>
          <select v-model="manualGalaxy" class="t-input cursor-pointer">
            <option value="">关联星系（可选）</option>
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
        </div>
        <textarea v-model="manualStem" rows="3" placeholder="题干" class="t-input" />
        <textarea
          v-if="manualKind === 'choice'"
          v-model="manualOptions"
          rows="4"
          placeholder="选项（每行一个，如：A. 栈）"
          class="t-input"
        />
        <input v-model="manualAnswer" placeholder="参考答案" class="t-input" />
        <button type="button" class="t-btn t-btn--primary t-btn--md" :disabled="!manualStem.trim()" @click="handleManualCreate">
          添加进题库
        </button>
      </div>

      <p v-if="msg" class="mt-2 text-xs" :class="msg.includes('失败') ? 'text-t-danger' : 'text-t-ok'">{{ msg }}</p>
    </section>

    <!-- 题库列表 -->
    <section class="t-card glass-edge p-5">
      <div class="flex flex-wrap items-center justify-between gap-2">
        <h3 class="text-[15px] font-semibold text-t-1">题库列表</h3>
        <div class="flex items-center gap-2">
          <select v-model="filterGalaxy" class="t-input t-input--fit cursor-pointer">
            <option value="">全部星系</option>
            <option v-for="g in galaxies" :key="g.slug" :value="g.slug">{{ g.name }}</option>
          </select>
          <select v-model="filterDifficulty" class="t-input t-input--fit cursor-pointer">
            <option value="">全部难度</option>
            <option value="easy">简单</option>
            <option value="medium">中等</option>
            <option value="hard">困难</option>
          </select>
          <span class="t-kicker">{{ questions.length }} Items</span>
        </div>
      </div>

      <TeacherLoading v-if="loading" class="mt-3" :rows="4" />
      <p v-else-if="error" class="mt-3 text-sm text-t-danger">{{ error }}</p>
      <div v-else class="mt-3 space-y-2">
        <div v-for="q in questions" :key="q.id" class="rounded-xl border border-t-line/10 bg-t-s1/30 px-4 py-3">
          <div class="flex items-start justify-between gap-2">
            <div class="flex flex-wrap items-center gap-1.5">
              <span class="t-badge t-badge--neutral">{{ q.kind }}</span>
              <span
                class="t-badge"
                :class="q.difficulty === 'hard' ? 't-badge--danger' : q.difficulty === 'easy' ? 't-badge--ok' : 't-badge--warn'"
              >
                {{ difficultyLabel[q.difficulty] || q.difficulty }}
              </span>
              <span v-if="q.galaxy_slug" class="t-badge t-badge--info">{{ galaxyNameMap[q.galaxy_slug] || q.galaxy_slug }}</span>
              <span class="text-[10px] text-t-3">{{ q.source === 'ai' ? 'AI 生成' : q.source === 'assignment' ? '作业收藏' : '手动' }}</span>
            </div>
            <button type="button" class="shrink-0 text-[11px] text-t-danger transition hover:opacity-75" @click="handleDelete(q.id)">
              删除
            </button>
          </div>
          <p class="mt-2 text-sm text-t-1">{{ q.stem }}</p>
          <ul v-if="q.options?.length" class="mt-1 space-y-0.5 text-[11px] text-t-3">
            <li v-for="(opt, oi) in q.options" :key="oi">{{ opt }}</li>
          </ul>
          <p v-if="q.answer" class="mt-1 text-[11px] text-t-ok/90">参考答案：{{ q.answer }}</p>
          <p v-if="q.explanation" class="mt-1 text-[11px] text-t-3">解析：{{ q.explanation }}</p>
          <div v-if="q.tags?.length" class="mt-1 flex flex-wrap gap-1">
            <span v-for="t in q.tags" :key="t" class="rounded bg-t-line/10 px-1.5 py-0.5 text-[10px] text-t-3">{{ t }}</span>
          </div>
        </div>
        <TeacherEmptyState v-if="!questions.length" title="题库为空" description="用 AI 生成或从历史作业收藏题目" />
      </div>
    </section>
  </div>
</template>
