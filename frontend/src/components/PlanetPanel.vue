<script setup lang="ts">
import { computed, nextTick, onMounted, onUnmounted, ref, watch } from 'vue';
import {
  emitSos,
  fetchFragments,
  fetchPlanetMasteryTrend,
  generateLessonPlan,
  reviewPlanet,
  startChallenge,
  submitChallenge,
  type Challenge,
  type FragmentProgress,
  type LessonPlan,
  type Planet,
  type SubmitResult,
} from '../api/orbit';
import { createMistake } from '../api/zone';
import type { MistakeTutorPayload } from '../api/digitalTutor';
import { fetchGates, passExplainGate, recordLearnGate, type GateId, type GateSnapshot } from '../api/challengeSprint';
import { useOrbitStore } from '../stores/orbit';
import MiniChart from './MiniChart.vue';
import MultiverseConsole from './MultiverseConsole.vue';
import GateSection from './learning/planet/GateSection.vue';
import { LzBadge, LzButton, LzProgress, LzSkeleton } from './learning/ui';
const props = defineProps<{ planet: Planet | null; galaxyName: string }>();
const emit = defineEmits<{
  (e: 'collapse'): void;
  (e: 'exit'): void;
  (e: 'lit', planet: Planet): void;
  (e: 'points', points: number): void;
  (e: 'simulate', payload: string | { topic: string; planetSlug?: string }): void;
  (e: 'supernova-review', planet: Planet): void;
  (e: 'open-dock', id: string): void;
  (e: 'open-mistake-tutor', payload: MistakeTutorPayload): void;
  (e: 'open-planet-tutor', payload: { planetSlug: string; planetName: string }): void;
}>();

type ActiveGate = GateId;

const GATE_META: Array<{ id: ActiveGate; label: string; title: string; hint: string }> = [
  { id: 'learn', label: '学', title: '学闸 · 建立直觉', hint: '打开星库 / 演武舱 / 生成资源后解锁练习' },
  { id: 'practice', label: '练', title: '练闸 · 综合小测', hint: '答对达标后进入讲解闸' },
  { id: 'explain', label: '讲', title: '讲闸 · 费曼讲解', hint: '用自己的话讲清知识点' },
  { id: 'apply', label: '用', title: '用闸 · 代码实操', hint: '代码舱测例全绿（概念课可豁免）' },
];

const orbit = useOrbitStore();
const galaxySlug = computed(() => orbit.currentGalaxy?.slug || '');

/** teach → 教导摘要；quiz → 答题；result → 单题反馈（可进下一题） */
const challengePhase = ref<'teach' | 'quiz' | 'result'>('teach');
const gateSnap = ref<GateSnapshot | null>(null);
const gateMsg = ref('');
const activeGate = ref<ActiveGate>('learn');
const challenge = ref<Challenge | null>(null);
const selected = ref('');
const result = ref<SubmitResult | null>(null);
const loading = ref(false);
const error = ref('');
const fragments = ref<FragmentProgress | null>(null);
const showMultiverse = ref(false);
const multiverseRef = ref<InstanceType<typeof MultiverseConsole> | null>(null);
const reviewMode = ref(false);
const challengeSectionRef = ref<InstanceType<typeof GateSection> | null>(null);
const sosMsg = ref('');
const gateFlash = ref(false);
const panelScrollRef = ref<HTMLElement | null>(null);
let gateFlashTimer: number | undefined;

const forceHumanReview = ref(false);
const selfConfidence = ref<'sure' | 'hesitant' | 'unknown' | ''>('');

const mistakeTutorBusy = ref(false);

const lessonPlan = ref<LessonPlan | null>(null);
const lessonLoading = ref(false);
const lessonError = ref('');

const masteryTrend = ref<number[]>([20, 35, 45, 55, 60, 70, 80]);
const trendLabels = ref<string[]>(['T-6', 'T-5', 'T-4', 'T-3', 'T-2', 'T-1', '当前']);

const totalQuestions = computed(() => challenge.value?.total_questions ?? 5);
const minCorrect = computed(() => challenge.value?.min_correct_to_lit ?? 4);
const questionIndex = computed(() => challenge.value?.question_index ?? 1);
const sessionCorrect = computed(() => result.value?.session_correct ?? 0);
const sessionDone = computed(() => !!result.value?.session_done);

function phaseToGate(phase?: string | null, snap?: GateSnapshot | null): ActiveGate {
  if (snap?.next_gate) return snap.next_gate;
  if (snap?.lit || phase === 'lit') return 'apply';
  switch (phase) {
    case 'practicing':
      return 'practice';
    case 'explaining':
      return 'explain';
    case 'applying':
      return 'apply';
    case 'exploring':
    case 'dim':
    default:
      return 'learn';
  }
}

function applyGateSnapshot(snap: GateSnapshot, opts?: { announce?: boolean; prev?: GateSnapshot | null }) {
  const prev = opts?.prev ?? gateSnap.value;
  const prevGate = prev ? phaseToGate(prev.mastery_phase, prev) : null;
  gateSnap.value = snap;
  const next = phaseToGate(snap.mastery_phase, snap);
  const switched = !prevGate || prevGate !== next;
  activeGate.value = next;
  if (switched) {
    void nextTick(() => focusGateSection(next));
  }
  if (!opts?.announce) return;
  if (snap.lit) {
    gateMsg.value = '四闸齐备，行星已点亮！可回「学习路径」打卡下一步，或打开画像查看随学随新。';
    return;
  }
  if (prevGate && prevGate !== next) {
    const titles: Record<ActiveGate, string> = {
      learn: '学',
      practice: '练',
      explain: '讲',
      apply: '用',
    };
    gateMsg.value = `「${titles[prevGate]}」闸已通过 → 已解锁「${titles[next]}」闸（完成后可回路径打卡）`;
  }
}

function focusGateSection(id: ActiveGate) {
  const root = panelScrollRef.value;
  if (!root) return;
  const el = root.querySelector(`[data-gate="${id}"]`) as HTMLElement | null;
  if (!el) return;
  el.scrollIntoView({ behavior: 'smooth', block: 'start' });
  gateFlash.value = true;
  if (gateFlashTimer) window.clearTimeout(gateFlashTimer);
  gateFlashTimer = window.setTimeout(() => {
    gateFlash.value = false;
  }, 1200);
}

function isGateDone(id: ActiveGate): boolean {
  if (!gateSnap.value) return false;
  if (id === 'apply' && !gateSnap.value.apply_required) return !!gateSnap.value.gates.explain;
  return !!gateSnap.value.gates[id];
}

function isGateUnlocked(id: ActiveGate): boolean {
  if (id === 'learn') return true;
  if (id === 'practice') return isGateDone('learn');
  if (id === 'explain') return isGateDone('practice');
  if (id === 'apply') return isGateDone('explain');
  return false;
}

function selectGate(id: ActiveGate) {
  if (!isGateUnlocked(id) && !isGateDone(id)) {
    gateMsg.value = '请先完成上一道闸门';
    return;
  }
  activeGate.value = id;
  if (id === 'practice' && gateSnap.value?.can_challenge) {
    void loadChallenge(reviewMode.value);
  }
}

async function markLearnQuick() {
  if (!props.planet) return;
  try {
    const prev = gateSnap.value;
    const snap = await recordLearnGate(props.planet.slug, 'panel_quick', '行星面板快速学闸证据');
    applyGateSnapshot(snap, { announce: true, prev });
  } catch (e) {
    gateMsg.value = e instanceof Error ? e.message : '学闸记录失败';
  }
}

async function loadMasteryTrend() {
  if (!props.planet) return;
  try {
    const trend = await fetchPlanetMasteryTrend(props.planet.slug);
    masteryTrend.value = trend.scores;
    trendLabels.value = trend.labels;
  } catch {
    masteryTrend.value = [20, 35, 45, 55, 60, 70, 80];
    trendLabels.value = ['T-6', 'T-5', 'T-4', 'T-3', 'T-2', 'T-1', '当前'];
  }
}

async function loadFragments() {
  if (!props.planet) return;
  try {
    fragments.value = await fetchFragments(props.planet.slug);
  } catch {
    fragments.value = null;
  }
}

async function refreshGates(announce = false) {
  if (!props.planet) return;
  try {
    const prev = gateSnap.value;
    const snap = await fetchGates(props.planet.slug);
    applyGateSnapshot(snap, { announce, prev });
  } catch {
    gateSnap.value = null;
  }
}

async function loadChallenge(asReview = false) {
  if (!props.planet) return;
  loading.value = true;
  error.value = '';
  result.value = null;
  selected.value = '';
  challenge.value = null;
  challengePhase.value = 'teach';
  reviewMode.value = asReview;
  try {
    await refreshGates();
    challenge.value = await startChallenge(props.planet.slug, asReview);
    if (challenge.value && challenge.value.can_challenge === false) {
      error.value = challenge.value.teaching_summary || '请先完成「学」闸';
    }
    if (asReview) {
      await nextTick();
      challengeSectionRef.value?.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
  } catch (e) {
    error.value = e instanceof Error ? e.message : '出题失败';
  } finally {
    loading.value = false;
  }
}

async function markExplainGate() {
  if (!props.planet) return;
  const slug = props.planet.slug;
  let score = 0.7;
  if (orbit.lastExplainPlanetSlug === slug && typeof orbit.lastExplainScore === 'number') {
    score = orbit.lastExplainScore;
  } else {
    gateMsg.value = '请先在伴学舱用「费曼讲解」完成一轮自评，再提交讲闸。';
    emit('open-dock', 'tutor');
    return;
  }
  if (score < 0.75) {
    gateMsg.value = `费曼评分 ${(score * 100).toFixed(0)} 分未达 75，请补充讲解后再试。`;
    emit('open-dock', 'tutor');
    return;
  }
  try {
    const prev = gateSnap.value;
    const snap = await passExplainGate(slug, score);
    applyGateSnapshot(snap, { announce: true, prev });
    if (snap.lit) {
      orbit.triggerMaterialChange(slug, 'lit');
      emit('lit', props.planet);
    } else if (snap.apply_required && snap.gates.explain) {
      activeGate.value = 'apply';
      gateMsg.value = `讲闸已通过（评分 ${(score * 100).toFixed(0)}）→ 请前往代码舱完成「用」闸`;
    } else {
      gateMsg.value = `讲闸已通过（评分 ${(score * 100).toFixed(0)}）`;
    }
  } catch (e) {
    gateMsg.value = e instanceof Error ? e.message : '讲闸提交失败';
  }
}

async function finalizeSupernovaIfReady(submitResult: SubmitResult) {
  if (!reviewMode.value || !props.planet || !submitResult.session_done) return;
  const passed = submitResult.lit || (submitResult.session_correct ?? 0) >= minCorrect.value;
  if (!passed) {
    sosMsg.value = `复习未通过（答对 ${submitResult.session_correct ?? 0}/${totalQuestions.value}），陨石危机仍在持续。`;
    return;
  }
  try {
    const res = await reviewPlanet(props.planet.slug, true);
    if (res.supernova) {
      orbit.triggerMaterialChange(props.planet.slug, 'lit');
      emit('supernova-review', props.planet);
      sosMsg.value = res.message;
      reviewMode.value = false;
    } else {
      sosMsg.value = res.message || '复习固化失败';
    }
  } catch (e) {
    sosMsg.value = e instanceof Error ? e.message : '超新星固化失败';
  }
}

function startQuiz() {
  if (!challenge.value?.challenge_id) return;
  if (challenge.value.can_challenge === false) return;
  challengePhase.value = 'quiz';
  result.value = null;
  selected.value = '';
  selfConfidence.value = '';
}

async function submit() {
  if (!challenge.value || !selected.value) return;
  loading.value = true;
  try {
    result.value = await submitChallenge(
      challenge.value.challenge_id,
      selected.value,
      forceHumanReview.value,
      selfConfidence.value,
    );
    emit('points', result.value.points);
    // 同步后端闸门快照，驱动步骤条前进
    if (result.value.gates || result.value.mastery_phase) {
      const prev = gateSnap.value;
      const merged: GateSnapshot = {
        mastery_phase: result.value.mastery_phase || prev?.mastery_phase || 'practicing',
        status: result.value.planet_status || prev?.status || 'dim',
        gates: {
          learn: result.value.gates?.learn ?? prev?.gates.learn ?? false,
          practice: result.value.gates?.practice ?? prev?.gates.practice ?? false,
          explain: result.value.gates?.explain ?? prev?.gates.explain ?? false,
          apply: result.value.gates?.apply ?? prev?.gates.apply ?? false,
        },
        apply_required: prev?.apply_required ?? true,
        learn_evidence_count: prev?.learn_evidence_count ?? 0,
        practice_questions: result.value.total_questions ?? prev?.practice_questions ?? 5,
        practice_min_correct: result.value.min_correct_to_lit ?? prev?.practice_min_correct ?? 4,
        can_challenge: true,
        lit_ready: !!result.value.lit_ready,
        lit: !!result.value.lit,
        next_gate: result.value.practice_passed
          ? (result.value.lit ? null : 'explain')
          : 'practice',
      };
      applyGateSnapshot(merged, { announce: !!result.value.session_done, prev });
    }
    if (result.value.session_done && result.value.practice_passed && !result.value.lit) {
      activeGate.value = 'explain';
      gateMsg.value = '练闸已通过 → 已解锁「讲」闸，请在伴学舱完成费曼讲解';
    }
    if (result.value.lit && props.planet && !reviewMode.value) {
      orbit.triggerMaterialChange(props.planet.slug, 'lit');
      emit('lit', props.planet);
    } else if (!result.value.correct && props.planet) {
      orbit.triggerMaterialChange(props.planet.slug, 'fading');
    }
    challengePhase.value = 'result';
    void loadMasteryTrend();
    if (result.value.session_done) await refreshGates(true);
    await finalizeSupernovaIfReady(result.value);
  } catch (e) {
    error.value = e instanceof Error ? e.message : '提交失败';
  } finally {
    loading.value = false;
  }
}

function continueNextQuestion() {
  if (!result.value?.next_challenge) return;
  challenge.value = result.value.next_challenge;
  result.value = null;
  selected.value = '';
  challengePhase.value = 'quiz';
}

async function openMistakeTutorFromPractice() {
  if (!props.planet || !challenge.value || !result.value || result.value.correct) return;
  mistakeTutorBusy.value = true;
  try {
    const studentText =
      challenge.value.options.find((o) => o.key === selected.value)?.text || selected.value || '未作答';
    const correctText =
      challenge.value.options.find((o) => o.key === result.value!.answer_key)?.text || result.value.answer_key;
    const saved = await createMistake({
      question: challenge.value.question,
      student_answer: studentText,
      correct_answer: correctText,
      subject: props.planet.name,
      note: result.value.explanation || '',
    });
    emit('open-mistake-tutor', {
      mistake_id: saved.id,
      question: saved.question,
      student_answer: saved.student_answer,
      correct_answer: saved.correct_answer,
      note: saved.note,
      subject: saved.subject,
      planet_slug: props.planet.slug,
    });
  } catch {
    emit('open-mistake-tutor', {
      question: challenge.value.question,
      student_answer:
        challenge.value.options.find((o) => o.key === selected.value)?.text || selected.value || '未作答',
      correct_answer:
        challenge.value.options.find((o) => o.key === result.value!.answer_key)?.text || result.value.answer_key,
      note: result.value.explanation || '',
      subject: props.planet.name,
      planet_slug: props.planet.slug,
    });
  } finally {
    mistakeTutorBusy.value = false;
  }
}

async function loadLessonPlan() {
  if (!props.planet) return;
  lessonLoading.value = true;
  lessonError.value = '';
  try {
    lessonPlan.value = await generateLessonPlan(props.planet.slug);
  } catch (e) {
    lessonError.value = e instanceof Error ? e.message : '教案生成失败，请稍后重试';
    lessonPlan.value = null;
  } finally {
    lessonLoading.value = false;
  }
}

async function handleSos() {
  if (!props.planet) return;
  sosMsg.value = '';
  try {
    const res = await emitSos(props.planet.slug);
    sosMsg.value = res.message;
  } catch {
    sosMsg.value = '发射失败';
  }
}

async function handleReview() {
  if (!props.planet) return;
  sosMsg.value = '';
  error.value = '';
  await loadChallenge(true);
}

function openMultiverse() {
  if (!props.planet) return;
  showMultiverse.value = true;
  void nextTick(() => multiverseRef.value?.run(props.planet!.name));
}

watch(() => props.planet, (p) => {
  lessonPlan.value = null;
  lessonError.value = '';
  reviewMode.value = false;
  sosMsg.value = '';
  gateMsg.value = '';
  activeGate.value = 'learn';
  gateSnap.value = null;
  if (p) {
    void refreshGates(false).then(() => {
      if (gateSnap.value?.can_challenge && activeGate.value === 'practice') {
        void loadChallenge(false);
      } else if (!gateSnap.value?.can_challenge) {
        activeGate.value = 'learn';
      } else {
        void loadChallenge(false);
      }
    });
    void loadFragments();
    void loadMasteryTrend();
  }
}, { immediate: true });

onMounted(() => {
  if (props.planet) void refreshGates(false);
  document.addEventListener('visibilitychange', onPanelVisible);
});

onUnmounted(() => {
  document.removeEventListener('visibilitychange', onPanelVisible);
  if (gateFlashTimer) window.clearTimeout(gateFlashTimer);
});

function onPanelVisible() {
  if (document.visibilityState === 'visible' && props.planet) void refreshGates(false);
}
</script>

<template>
  <aside v-if="planet" class="lz-accent-sky cosmic-drawer relative flex h-full w-full flex-col border-l border-[rgb(var(--lz-accent)/0.2)]">
    <header class="border-b border-[var(--border-soft)] px-6 py-5">
      <div class="flex items-start justify-between gap-3">
        <div class="min-w-0 flex-1">
          <p class="lz-caption lz-accent-text uppercase tracking-[0.4em]">{{ galaxyName }}</p>
          <div class="mt-1.5 flex flex-wrap items-center gap-2">
            <span class="h-2.5 w-2.5 rounded-full bg-[rgb(var(--lz-accent))] shadow-[0_0_12px_rgb(var(--lz-accent))]"></span>
            <h2 class="text-xl font-semibold tracking-wide text-white text-glow">{{ planet.name }}</h2>
            <LzBadge tone="accent">难度 {{ planet.difficulty.toUpperCase() }}</LzBadge>
          </div>
          <p class="lz-body mt-1.5">{{ planet.description }}</p>
        </div>
        <div class="flex shrink-0 flex-col gap-1.5">
          <LzButton variant="soft" size="sm" @click="emit('collapse')">收起</LzButton>
          <LzButton variant="ghost" size="sm" @click="emit('exit')">退出星球</LzButton>
        </div>
      </div>
      <div class="lz-card lz-card--flat mt-4 p-3">
        <p class="lz-caption mb-1 uppercase tracking-[0.2em]">掌握趋势</p>
        <MiniChart v-if="masteryTrend.length" type="line" :data="masteryTrend" :labels="trendLabels" height="56px" color="#38bdf8" />
        <p v-else class="lz-caption py-4 text-center">暂无掌握数据 · 完成一轮小测后即可看到趋势曲线</p>
      </div>
    </header>

    <div ref="panelScrollRef" class="flex-1 space-y-4 overflow-auto px-6 py-5">
      <!-- 线性闸门步骤条 -->
      <section class="lz-card lz-card--active p-4">
        <div class="flex items-center justify-between gap-2">
          <div>
            <p class="lz-caption lz-accent-text uppercase tracking-[0.3em]">Mastery Gates</p>
            <p class="lz-title mt-1">点亮四闸 · {{ gateSnap?.mastery_phase || 'dim' }}</p>
          </div>
          <LzButton variant="ghost" size="sm" @click="refreshGates(false)">刷新</LzButton>
        </div>
        <div class="relative mt-4">
          <div class="pointer left-4 right-4 top-[1.35rem] z-0 flex h-0.5">
            <div
              v-for="(g, idx) in GATE_META.slice(0, 3)"
              :key="`line-${g.id}`"
              class="h-full flex-1 transition"
              :class="isGateDone(g.id) ? 'bg-emerald-400/70' : idx < GATE_META.findIndex((x) => x.id === activeGate) ? 'bg-[rgb(var(--lz-accent)/0.5)]' : 'bg-white/10'"
            />
          </div>
          <div class="relative z-10 grid grid-cols-4 gap-2">
            <button
              v-for="(g, idx) in GATE_META"
              :key="g.id"
              type="button"
              class="relative rounded-[var(--radius-card)] border px-2 py-3 text-center transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
              :class="[
                activeGate === g.id
                  ? 'gate-step-active border-[rgb(var(--lz-accent)/0.7)] bg-[rgb(var(--lz-accent)/0.2)] text-white'
                  : isGateDone(g.id)
                    ? 'gate-step-done border-emerald-400/50 bg-emerald-500/15 text-emerald-100'
                    : isGateUnlocked(g.id)
                      ? 'border-white/20 bg-white/5 text-slate-200 hover:border-[rgb(var(--lz-accent)/0.4)]'
                      : 'border-white/5 bg-black/20 text-slate-600 cursor-not-allowed',
              ]"
              :disabled="!isGateUnlocked(g.id) && !isGateDone(g.id)"
              @click="selectGate(g.id)"
            >
              <span class="mx-auto flex h-9 w-9 items-center justify-center rounded-full border text-sm font-bold"
                :class="isGateDone(g.id) ? 'border-emerald-300/60 bg-emerald-400/20' : activeGate === g.id ? 'border-[rgb(var(--lz-accent)/0.7)] bg-[rgb(var(--lz-accent)/0.25)]' : 'border-white/15'"
              >{{ isGateDone(g.id) ? '✓' : g.label }}</span>
              <p class="mt-1.5 text-[11px] font-semibold">{{ g.title.split('·')[0].trim() }}</p>
              <p class="mt-0.5 text-[9px] opacity-70">{{ idx + 1 }}/4</p>
            </button>
          </div>
        </div>
        <p v-if="gateMsg" class="mt-3 rounded-[var(--radius-ctl)] border border-emerald-400/30 bg-emerald-500/10 px-3 py-2 text-xs text-emerald-100">{{ gateMsg }}</p>
        <p class="lz-caption mt-2">{{ GATE_META.find((x) => x.id === activeGate)?.hint }}</p>
      </section>

      <!-- 当前闸内容 -->
      <GateSection
        v-if="activeGate === 'learn'"
        gate-id="learn"
        title="学闸 · 先建立直觉"
        hint="任选一项有效学习后自动解锁「练」闸。推荐答辩路径：演武舱完整步进。"
        :flash="gateFlash && activeGate === 'learn'"
      >
        <div class="mt-3 grid grid-cols-2 gap-2">
          <LzButton variant="primary" size="lg" @click="emit('open-dock', 'starlib')">打开星库</LzButton>
          <LzButton variant="primary" size="lg" @click="emit('open-dock', 'viz')">进入演武舱</LzButton>
          <LzButton variant="primary" size="lg" @click="emit('open-dock', 'resources')">资源工坊</LzButton>
          <LzButton variant="soft" size="lg" @click="emit('open-dock', 'tutor')">打开伴学舱</LzButton>
          <LzButton
            variant="soft"
            size="lg"
            @click="emit('open-planet-tutor', { planetSlug: planet.slug, planetName: planet.name })"
          >
            请虚拟人讲一遍
          </LzButton>
          <LzButton variant="ghost" size="lg" @click="markLearnQuick">标记已学习</LzButton>
        </div>
        <p class="lz-caption mt-2">已收集学习证据 {{ gateSnap?.learn_evidence_count ?? 0 }} 条</p>
      </GateSection>

      <button
        type="button"
        class="lz-card lz-card--hover group flex w-full items-center justify-between px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
        @click="emit('simulate', { topic: planet.name, planetSlug: planet.slug })"
      >
        <div class="min-w-0">
          <p class="lz-subtitle">让数字替身先预演这颗行星</p>
          <p class="lz-caption mt-0.5">Teacher · Mirror · Evaluator 多智能体协同试错</p>
        </div>
        <span class="lz-accent-text text-lg transition group-hover:translate-x-0.5">↗</span>
      </button>

      <button
        type="button"
        class="lz-card lz-card--hover flex w-full items-center justify-between px-4 py-3 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
        @click="openMultiverse"
      >
        <div class="min-w-0">
          <p class="lz-subtitle">平行宇宙推演</p>
          <p class="lz-caption mt-0.5">激进 / 均衡 / 保守 三策略对比</p>
        </div>
        <span class="lz-accent-text text-lg">∞</span>
      </button>

      <section v-if="fragments" class="lz-card p-4">
        <h3 class="lz-subtitle">知识碎片收集</h3>
        <p class="lz-caption mt-0.5">与伴学 Agent 聊天闯关，集齐碎片爆发光晕</p>
        <div class="mt-2 flex flex-wrap gap-2">
          <LzBadge v-for="f in fragments.fragments" :key="f.id" :tone="f.collected ? 'accent' : 'neutral'">
            {{ f.icon }} {{ f.name }}
          </LzBadge>
        </div>
        <div class="mt-2.5">
          <LzProgress :value="(fragments.collected_count / fragments.total) * 100" />
        </div>
      </section>

      <div v-if="planet.status === 'meteor' || planet.status === 'fading'" class="rounded-[var(--radius-card)] border border-amber-400/30 bg-amber-500/10 p-4">
        <div class="flex items-start gap-3">
          <img src="/icons/meteor.svg" alt="" class="mt-0.5 h-8 w-8 shrink-0 opacity-90" />
          <div class="min-w-0 flex-1">
            <p class="text-sm font-semibold text-amber-100">陨石危机！该行星需要复习</p>
            <p class="mt-1 text-[11px] leading-5 text-amber-200/70">
              点击后进入教导与测验；答对达到标准后才会触发超新星、永久点亮。不会一键跳过答题。
            </p>
            <button
              type="button"
              class="lz-btn lz-btn--md mt-3 w-full bg-amber-500/20 text-amber-50 hover:bg-amber-500/30"
              :disabled="loading"
              @click="handleReview"
            >
              {{ loading && reviewMode ? '正在准备复习题…' : '进入超新星复习测验' }}
            </button>
            <p v-if="sosMsg && (planet.status === 'meteor' || planet.status === 'fading')" class="mt-2 text-[11px] text-amber-100/90">{{ sosMsg }}</p>
          </div>
        </div>
      </div>

      <div v-if="result?.can_emit_sos" class="rounded-[var(--radius-card)] border border-rose-400/30 bg-rose-500/10 p-3">
        <LzButton variant="danger" block @click="handleSos">🆘 向全宇宙发射求救信号</LzButton>
        <p v-if="sosMsg" class="mt-1.5 text-[11px] text-rose-200">{{ sosMsg }}</p>
      </div>

      <div v-if="result?.constellation" class="rounded-[var(--radius-card)] border border-amber-400/30 bg-amber-500/10 p-3 text-sm text-amber-100">
        {{ result.constellation.badge_icon }} {{ result.constellation.message }}
      </div>

      <GateSection
        v-if="activeGate === 'practice' || reviewMode"
        ref="challengeSectionRef"
        gate-id="practice"
        :title="reviewMode ? '超新星复习测验' : '练闸 · Teacher 综合小测'"
        :hint="reviewMode
          ? `先回顾要点，再答 ${totalQuestions} 题；答对 ≥${minCorrect} 题后才会永久点亮`
          : `先教导复习，再答 ${totalQuestions} 题；答对 ≥${minCorrect} 题通过「练」闸（不会直接点亮）`"
        :flash="gateFlash && activeGate === 'practice'"
        :class="reviewMode ? 'ring-1 ring-amber-400/40' : ''"
      >
        <template #actions>
          <LzButton variant="ghost" size="sm" :disabled="loading" @click="loadChallenge(reviewMode)">重新挑战</LzButton>
        </template>

        <LzSkeleton v-if="loading && !challenge" preset="text" :rows="3" class="mt-3" />
        <p v-if="error" class="mt-3 rounded-[var(--radius-ctl)] border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{{ error }}</p>

        <template v-if="challenge">
          <!-- 教导步骤 -->
          <div v-if="challengePhase === 'teach'" class="mt-3 space-y-3">
            <div class="lz-card lz-card--flat px-3 py-3">
              <p class="lz-caption lz-accent-text font-semibold uppercase tracking-wider">教导</p>
              <p class="mt-1.5 text-sm leading-6 text-slate-100">
                {{ challenge.teaching_summary || planet.description || '先回顾核心概念，再进入小测。' }}
              </p>
            </div>
            <LzButton variant="primary" block @click="startQuiz">
              开始答题（共 {{ totalQuestions }} 题）
            </LzButton>
          </div>

          <!-- 答题 / 单题结果 -->
          <template v-else>
            <p class="lz-caption lz-accent-text mt-3">
              第 {{ questionIndex }} / {{ totalQuestions }} 题
              <span v-if="result"> · 本轮已对 {{ sessionCorrect }} 题</span>
            </p>
            <p class="mt-2 text-sm leading-6 text-slate-100">{{ challenge.question }}</p>
            <div class="mt-3 space-y-2">
              <label
                v-for="opt in challenge.options"
                :key="opt.key"
                class="flex cursor-pointer items-start gap-2 rounded-[var(--radius-ctl)] border px-3 py-2 text-sm transition"
                :class="[
                  selected === opt.key ? 'border-[rgb(var(--lz-accent)/0.6)] bg-[rgb(var(--lz-accent)/0.1)]' : 'border-white/10 bg-white/[0.03] hover:border-white/20',
                  result && opt.key === result.answer_key ? 'border-emerald-400/70 bg-emerald-400/10' : '',
                  result && selected === opt.key && !result.correct ? 'border-rose-400/70 bg-rose-400/10' : '',
                ]"
              >
                <input v-model="selected" type="radio" :value="opt.key" :disabled="!!result" class="mt-1" />
                <span class="text-slate-100"><b class="lz-accent-text">{{ opt.key }}.</b> {{ opt.text }}</span>
              </label>
            </div>

            <div v-if="!result" class="mt-3 flex flex-wrap gap-1.5">
              <button
                v-for="opt in ([
                  { id: 'sure', label: '确定' },
                  { id: 'hesitant', label: '有点犹豫' },
                  { id: 'unknown', label: '不会' },
                ] as const)"
                :key="opt.id"
                type="button"
                class="rounded-[var(--radius-ctl)] px-2.5 py-1 text-[11px] transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[rgb(var(--lz-accent)/0.4)]"
                :class="
                  selfConfidence === opt.id
                    ? 'bg-[rgb(var(--lz-accent)/0.2)] text-white ring-1 ring-[rgb(var(--lz-accent)/0.4)]'
                    : 'border border-white/10 text-slate-400 hover:bg-white/5'
                "
                @click="selfConfidence = selfConfidence === opt.id ? '' : opt.id"
              >
                {{ opt.label }}
              </button>
            </div>
            <label v-if="!result" class="lz-caption mt-3 flex items-center gap-2">
              <input v-model="forceHumanReview" type="checkbox" class="rounded" />
              演示：强制低置信 → 教师待人审工单
            </label>
            <LzButton
              v-if="!result"
              variant="primary"
              block
              class="mt-2"
              :disabled="!selected"
              :loading="loading"
              @click="submit"
            >
              {{ loading ? '判定中…' : '提交答案' }}
            </LzButton>

            <div v-if="result" class="mt-4 space-y-3">
              <div
                class="rounded-[var(--radius-ctl)] px-4 py-3 text-sm font-semibold"
                :class="result.correct ? 'bg-emerald-500/15 text-emerald-200' : 'bg-rose-500/15 text-rose-200'"
              >
                <template v-if="sessionDone">
                  {{ reviewMode
                    ? ((result.lit || sessionCorrect >= minCorrect)
                      ? `复习达标（${sessionCorrect}/${totalQuestions}），正在触发超新星固化…`
                      : `本轮答对 ${sessionCorrect}/${totalQuestions}，未达 ${minCorrect} 题，无法固化`)
                    : (result.practice_passed || result.gates?.practice
                      ? `练闸通过（${sessionCorrect}/${totalQuestions}）！已解锁「讲」闸`
                      : result.lit
                        ? `四闸齐备，行星已点亮 +10 积分`
                        : `本轮答对 ${sessionCorrect}/${totalQuestions}，未达 ${minCorrect} 题，练闸未过`) }}
                </template>
                <template v-else>
                  {{ result.correct ? '回答正确' : '回答错误，已记入错题本' }}
                </template>
              </div>
              <div class="lz-card lz-card--flat p-3 text-xs leading-6 text-slate-300">
                <p class="mb-1 font-semibold text-white">解析（Evaluator Agent）</p>
                {{ result.explanation }}
              </div>
              <LzButton
                v-if="!result.correct"
                variant="soft"
                block
                :loading="mistakeTutorBusy"
                @click="openMistakeTutorFromPractice"
              >
                {{ mistakeTutorBusy ? '准备中…' : '虚拟人讲错因' }}
              </LzButton>
              <div class="lz-card lz-card--flat px-2.5 py-2 text-[10px] text-slate-300">
                <p>
                  依据知识点：
                  <span class="lz-accent-text font-mono">{{ result.cited_knowledge_point_id || result.knowledge_point_id || planet?.slug || '—' }}</span>
                  · 置信度
                  <span class="lz-accent-text">{{ ((result.confidence ?? 1) * 100).toFixed(0) }}%</span>
                </p>
                <p v-if="result.source_refs?.length" class="mt-1 text-slate-500">来源：{{ result.source_refs.join(' · ') }}</p>
                <p v-if="result.human_review_required" class="mt-1 text-rose-300">
                  已转教师待人审工单{{ result.review_ticket_id ? `（${result.review_ticket_id.slice(0, 8)}…）` : '' }}
                </p>
              </div>
              <LzButton
                v-if="!sessionDone && result.next_challenge"
                variant="primary"
                block
                @click="continueNextQuestion"
              >
                下一题（{{ (result.next_challenge.question_index ?? questionIndex + 1) }} / {{ totalQuestions }}）
              </LzButton>
              <LzButton
                v-else
                variant="primary"
                block
                @click="loadChallenge(reviewMode)"
              >
                {{ result.lit ? '再练一轮' : '重新挑战' }}
              </LzButton>
            </div>
          </template>
        </template>
      </GateSection>

      <section class="lz-card p-4">
        <div class="flex items-start justify-between gap-3">
          <div class="min-w-0">
            <p class="lz-caption lz-accent-text uppercase tracking-[0.22em]">Star Vault</p>
            <h3 class="lz-subtitle">星轨知识库</h3>
            <p class="lz-caption mt-1">
              在全屏工作台中打开本行星笔记，支持双链、图谱与 Obsidian 同步。
            </p>
          </div>
          <LzButton variant="soft" size="sm" class="shrink-0" @click="emit('open-dock', 'notes')">
            在知识库中打开
          </LzButton>
        </div>
      </section>

      <section class="lz-card p-4">
        <div class="flex items-center justify-between gap-2">
          <h3 class="lz-subtitle">教案生成</h3>
          <LzButton variant="ghost" size="sm" :disabled="lessonLoading" @click="loadLessonPlan">
            {{ lessonPlan ? '重新生成' : '生成教案' }}
          </LzButton>
        </div>
        <p class="lz-caption mt-1">生成该知识点的自学路径：目标、讲解思路、例题、易错点与自测清单。</p>
        <LzButton
          v-if="!lessonPlan"
          variant="primary"
          block
          class="mt-3"
          :loading="lessonLoading"
          @click="loadLessonPlan"
        >
          {{ lessonLoading ? '正在生成教案…' : '一键生成教案' }}
        </LzButton>
        <LzSkeleton v-if="lessonLoading && !lessonPlan" preset="text" :rows="4" class="mt-3" />
        <p v-if="lessonError" class="mt-3 rounded-[var(--radius-ctl)] border border-rose-300/20 bg-rose-500/10 px-3 py-2 text-xs text-rose-100">{{ lessonError }}</p>
        <div v-if="lessonPlan" class="mt-3 space-y-3">
          <div class="lz-card lz-card--active px-3 py-3">
            <p class="lz-caption lz-accent-text font-semibold uppercase tracking-wider">讲解思路</p>
            <p class="mt-1.5 text-sm leading-6 text-slate-100">{{ lessonPlan.teaching_approach }}</p>
          </div>
          <div class="lz-card lz-card--flat px-3 py-3">
            <p class="lz-caption lz-accent-text font-semibold">学习目标</p>
            <ul class="lz-desc mt-2 space-y-1.5">
              <li v-for="(item, i) in lessonPlan.learning_goals" :key="`goal-${i}`">{{ i + 1 }}. {{ item }}</li>
            </ul>
          </div>
          <div class="lz-card lz-card--flat px-3 py-3">
            <p class="lz-caption lz-accent-text font-semibold">典型例题</p>
            <ul class="lz-desc mt-2 space-y-1.5">
              <li v-for="(item, i) in lessonPlan.example_problems" :key="`ex-${i}`">{{ i + 1 }}. {{ item }}</li>
            </ul>
          </div>
          <div class="lz-card lz-card--flat px-3 py-3">
            <p class="text-[11px] font-semibold text-amber-200">易错点</p>
            <ul class="lz-desc mt-2 space-y-1.5">
              <li v-for="(item, i) in lessonPlan.common_mistakes" :key="`mis-${i}`">{{ i + 1 }}. {{ item }}</li>
            </ul>
          </div>
          <div class="lz-card lz-card--flat px-3 py-3">
            <p class="lz-caption lz-accent-text font-semibold">练习安排</p>
            <ul class="lz-desc mt-2 space-y-1.5">
              <li v-for="(item, i) in lessonPlan.practice_plan" :key="`pr-${i}`">{{ i + 1 }}. {{ item }}</li>
            </ul>
          </div>
          <div class="lz-card lz-card--flat px-3 py-3">
            <p class="lz-caption lz-accent-text font-semibold">自测清单</p>
            <ul class="lz-desc mt-2 space-y-1.5">
              <li v-for="(item, i) in lessonPlan.self_check" :key="`ck-${i}`">{{ i + 1 }}. {{ item }}</li>
            </ul>
          </div>
        </div>
      </section>

      <GateSection
        v-if="activeGate === 'apply'"
        gate-id="apply"
        title="用闸 · 代码实操"
        :hint="gateSnap?.apply_required === false ? '本行星无需代码实操，讲闸通过即可点亮。' : '在代码舱完成至少 1 道微习题测例全绿，即可点亮行星。'"
        :flash="gateFlash && activeGate === 'apply'"
      >
        <LzButton variant="primary" size="lg" block class="mt-3" @click="emit('open-dock', 'codelab')">打开代码舱</LzButton>
        <LzButton variant="ghost" size="sm" block class="mt-2" @click="refreshGates(true)">我已跑通，刷新闸门</LzButton>
      </GateSection>

      <GateSection
        v-if="activeGate === 'explain' || activeGate === 'learn' || activeGate === 'practice'"
        gate-id="explain"
        :title="activeGate === 'explain' ? '讲闸 · 费曼讲解' : '伴学舱入口'"
        :hint="activeGate === 'explain'
          ? `在伴学舱用自己的话讲解「${planet.name}」，完成后点下方通过讲闸。`
          : '苏格拉底 / 费曼多轮引导与语音提问已迁至独立伴学舱。'"
        :highlight="activeGate === 'explain'"
        :flash="gateFlash && activeGate === 'explain'"
      >
        <LzButton variant="primary" block class="mt-3" @click="emit('open-dock', 'tutor')">
          打开伴学舱
        </LzButton>
        <LzButton
          variant="soft"
          block
          class="mt-2"
          @click="emit('open-planet-tutor', { planetSlug: planet.slug, planetName: planet.name })"
        >
          请虚拟人讲一遍
        </LzButton>
        <LzButton
          v-if="activeGate === 'explain'"
          variant="soft"
          block
          class="mt-2"
          @click="markExplainGate"
        >
          费曼评分达标 · 通过「讲」闸
        </LzButton>
      </GateSection>
    </div>

    <div v-if="showMultiverse" class="absolute inset-0 z-10 p-4">
      <MultiverseConsole ref="multiverseRef" @close="showMultiverse = false" />
    </div>
  </aside>
</template>
