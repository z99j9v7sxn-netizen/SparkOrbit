<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref } from 'vue';
import {
  completePathStep,
  completeSprintStep,
  fetchLearningPath,
  fetchRecommendations,
  fetchSprintPath,
  generateLearningPath,
  generateSprintPath,
  mountPathStep,
  type LearningPath,
  type RecommendationItem,
} from '../../api/learnExtras';
import { parseApiError } from '../../api/errors';
import { fetchGalaxies, fetchGalaxyDetail } from '../../api/orbit';
import { LzBadge, LzButton, LzEmptyState, LzInput, LzProgress, LzSection, LzTabs, type LzTabItem } from './ui';

const emit = defineEmits<{
  (e: 'navigate', target: { galaxySlug: string; galaxyName: string; planetSlug: string; planetName: string }): void;
  (e: 'open-dock', dock: string): void;
}>();

const path = ref<LearningPath | null>(null);
const recs = ref<RecommendationItem[]>([]);
const goal = ref('');
const loading = ref(false);
const msg = ref('');
const mountDraft = ref<Record<number, { kind: string; id: string; title: string }>>({});

// ---- 冲刺模式 ----
const TAB_ITEMS: LzTabItem[] = [
  { key: 'standard', label: '学习路径' },
  { key: 'sprint', label: '考试冲刺' },
];
const tab = ref('standard');
const sprint = ref<LearningPath | null>(null);
const sprintExamName = ref('');
const sprintExamDate = ref('');
const sprintLoading = ref(false);

const sprintDaysLeft = computed(() => {
  const d = sprint.value?.meta?.exam_date;
  if (!d) return 0;
  return Math.max(0, Math.ceil((new Date(d).getTime() - Date.now()) / 86400000));
});
const todayIso = new Date().toISOString().slice(0, 10);

async function loadSprint() {
  sprint.value = await fetchSprintPath().catch(() => null);
}

async function handleGenerateSprint() {
  if (!sprintExamDate.value) {
    msg.value = '请先选择考试日期';
    return;
  }
  sprintLoading.value = true;
  msg.value = '';
  try {
    sprint.value = await generateSprintPath(sprintExamName.value.trim(), sprintExamDate.value);
    msg.value = '冲刺计划已生成，按天推进即可';
  } catch (err) {
    msg.value = parseApiError(err, '冲刺计划生成失败');
  } finally {
    sprintLoading.value = false;
  }
}

async function completeSprint(idx: number) {
  if (!sprint.value) return;
  try {
    sprint.value = await completeSprintStep(sprint.value.id, idx);
    msg.value = `冲刺任务已打卡`;
  } catch (err) {
    msg.value = parseApiError(err, '打卡失败');
  }
}

const doneCount = computed(() => path.value?.steps.filter((s) => s.completed).length ?? 0);
const totalSteps = computed(() => path.value?.steps.length ?? 0);

function draftFor(idx: number) {
  if (!mountDraft.value[idx]) {
    mountDraft.value[idx] = { kind: 'resource', id: '', title: '' };
  }
  return mountDraft.value[idx];
}

function focusResource(resourceId: string, kind?: string) {
  emit('open-dock', 'resources');
  window.dispatchEvent(
    new CustomEvent('sparkorbit:focus-resource', {
      detail: { resourceId, kind },
    }),
  );
}

function goLearn(r: RecommendationItem) {
  const kind = (r.kind || '').toLowerCase();
  if (kind === 'planet' && r.planet_slug) {
    void jumpToPlanet(r.planet_slug, r.planet_name || r.title);
    return;
  }
  if (r.resource_id) {
    focusResource(r.resource_id, r.kind);
    msg.value = `正在打开资源：${r.title}`;
    return;
  }
  if (r.planet_slug) {
    void jumpToPlanet(r.planet_slug, r.planet_name || r.title);
    return;
  }
  emit('open-dock', 'resources');
  msg.value = `请在资源舱查看：${r.title}`;
}

async function load() {
  path.value = await fetchLearningPath().catch(() => null);
  recs.value = await fetchRecommendations().catch(() => []);
}

async function handleGenerate() {
  loading.value = true;
  msg.value = '';
  try {
    path.value = await generateLearningPath(goal.value, true);
    msg.value = '学习路径已生成';
    await load();
  } catch (err) {
    msg.value = parseApiError(err, '生成失败');
  } finally {
    loading.value = false;
  }
}

async function completeStep(idx: number) {
  try {
    path.value = await completePathStep(idx);
    msg.value = `步骤 ${idx + 1} 已打卡（已写入随学随新事件）。可继续四闸练习巩固。`;
  } catch (err) {
    msg.value = parseApiError(err, '打卡失败');
  }
}

async function mountRec(stepIndex: number, r: RecommendationItem) {
  try {
    path.value = await mountPathStep(stepIndex, {
      kind: r.kind || 'planet',
      id: r.resource_id || r.planet_slug || r.title,
      title: r.title,
      reason: r.reason,
    });
    msg.value = `已挂载「${r.title}」到步骤 ${stepIndex + 1}`;
  } catch (err) {
    msg.value = parseApiError(err, '挂载失败');
  }
}

async function mountManual(idx: number) {
  const d = draftFor(idx);
  if (!d.id.trim()) {
    msg.value = '请填写挂载资源 id';
    return;
  }
  try {
    path.value = await mountPathStep(idx, {
      kind: d.kind || 'resource',
      id: d.id.trim(),
      title: d.title.trim() || d.id.trim(),
    });
    d.id = '';
    d.title = '';
    msg.value = `步骤 ${idx + 1} 已挂载资源`;
  } catch (err) {
    msg.value = parseApiError(err, '挂载失败');
  }
}

async function unmountItem(stepIndex: number, kind: string, id: string) {
  try {
    path.value = await mountPathStep(stepIndex, { kind, id, title: '', unmount: true });
    msg.value = '已取消挂载';
  } catch (err) {
    msg.value = parseApiError(err, '取消挂载失败');
  }
}

function openMounted(m: { kind: string; id: string; title: string; reason?: string }, stepPlanetSlug?: string) {
  const k = (m.kind || '').toLowerCase();
  if (k === 'planet') {
    void jumpToPlanet(m.id, m.title);
    return;
  }
  if (['doc', 'mindmap', 'quiz', 'reading', 'media', 'deck', 'code', 'resource'].includes(k) && m.id) {
    focusResource(m.id, m.kind);
    msg.value = `正在打开：${m.title}`;
    return;
  }
  if (stepPlanetSlug) {
    void jumpToPlanet(stepPlanetSlug, m.title);
    return;
  }
  if (['starlib', 'video_local', 'video', 'pdf', 'book', 'video_bilibili'].includes(k)) {
    emit('open-dock', 'starlib');
    msg.value = `请在星库中打开：${m.title}`;
    return;
  }
  if (['viz', 'algo_viz', 'algo-viz'].includes(k)) {
    emit('open-dock', 'viz');
    msg.value = '已打开演武舱，完成学闸后可回路径打卡';
    return;
  }
  if (['codelab', 'code_lab'].includes(k)) {
    emit('open-dock', 'codelab');
    msg.value = '已打开代码舱，完成用闸后可回路径打卡';
    return;
  }
  emit('open-dock', 'resources');
  msg.value = `已尝试打开：${m.title}`;
}

async function jumpToPlanet(planetSlug: string, planetName: string) {
  if (!planetSlug) return;
  try {
    const galaxies = await fetchGalaxies();
    for (const galaxy of galaxies) {
      const detail = await fetchGalaxyDetail(galaxy.slug);
      const planet = detail.planets.find((item) => item.slug === planetSlug);
      if (planet) {
        emit('navigate', {
          galaxySlug: galaxy.slug,
          galaxyName: galaxy.name,
          planetSlug: planet.slug,
          planetName: planet.name || planetName,
        });
        msg.value = `已跃迁至 ${planet.name || planetName}。可在行星面板完成四闸后回路径打卡。`;
        return;
      }
    }
    msg.value = '未找到对应行星';
  } catch (err) {
    msg.value = parseApiError(err, '跃迁失败');
  }
}

onMounted(() => {
  void load();
  void loadSprint();
  const onOpen = (ev: Event) => {
    const detail = (ev as CustomEvent).detail as { dock?: string } | undefined;
    if (detail?.dock === 'path') void load();
  };
  window.addEventListener('sparkorbit:open-dock', onOpen as EventListener);
  onBeforeUnmount(() => window.removeEventListener('sparkorbit:open-dock', onOpen as EventListener));
});

</script>

<template>
  <div class="dock-panel space-y-4">
    <div class="rounded-[var(--radius-panel)] border border-[rgb(var(--lz-accent)/0.18)] bg-gradient-to-br from-[rgb(var(--lz-accent)/0.09)] to-transparent p-4">
      <div class="flex items-start gap-3">
        <img src="/icons/path.svg" alt="" class="mt-0.5 h-7 w-7 shrink-0" />
        <div class="min-w-0">
          <p class="lz-caption lz-accent-text uppercase tracking-[0.35em] opacity-80">Path Planner</p>
          <h3 class="lz-title mt-1">个性化学习路径</h3>
          <p class="lz-desc mt-1">
            结合画像与掌握度生成可打卡计划；可把推荐资源挂载到步骤下。
          </p>
        </div>
      </div>
    </div>

    <LzTabs v-model="tab" :items="TAB_ITEMS" block />

    <p
      v-if="msg"
      class="text-xs"
      :class="msg.includes('失败') || msg.includes('未找到') ? 'text-rose-300' : 'lz-accent-text'"
    >
      {{ msg }}
    </p>

    <!-- ===== 考试冲刺 ===== -->
    <template v-if="tab === 'sprint'">
      <div v-if="!sprint" class="lz-card space-y-3 p-4">
        <p class="lz-desc">输入考试信息，AI 结合薄弱行星与错题分布倒排每日冲刺任务（最多 21 天）。</p>
        <LzInput v-model="sprintExamName" placeholder="考试名称（如：高数期末 / 英语四级）" />
        <input
          v-model="sprintExamDate"
          type="date"
          :min="todayIso"
          class="lz-input w-full px-3 py-2"
          aria-label="考试日期"
        />
        <LzButton variant="primary" block :loading="sprintLoading" @click="handleGenerateSprint">
          {{ sprintLoading ? '倒排冲刺计划中…' : '生成冲刺计划' }}
        </LzButton>
      </div>

      <template v-else>
        <div class="lz-card flex items-center justify-between gap-3 p-4">
          <div class="min-w-0">
            <p class="lz-subtitle truncate">{{ sprint.title }}</p>
            <p class="lz-caption mt-1">
              考试日 {{ sprint.meta?.exam_date }} · 完成 {{ sprint.steps.filter((s) => s.completed).length }} /
              {{ sprint.steps.length }} 项
            </p>
          </div>
          <div class="shrink-0 text-center">
            <p class="font-mono-tech text-2xl font-semibold text-amber-300">{{ sprintDaysLeft }}</p>
            <p class="lz-caption">天倒计时</p>
          </div>
        </div>
        <LzProgress :value="sprint.progress" />

        <ol class="space-y-2">
          <li
            v-for="(s, i) in sprint.steps"
            :key="i"
            class="p-3"
            :class="[
              s.completed
                ? 'rounded-[var(--radius-card)] border border-emerald-400/25 bg-emerald-500/5'
                : s.date === todayIso
                  ? 'rounded-[var(--radius-card)] border border-amber-400/40 bg-amber-500/10'
                  : 'lz-card',
            ]"
          >
            <div class="flex items-start gap-3">
              <div class="shrink-0 text-center">
                <p class="font-mono-tech text-xs font-bold" :class="s.date === todayIso ? 'text-amber-200' : 'text-slate-400'">
                  D{{ s.day }}
                </p>
                <p class="lz-caption">{{ (s.date || '').slice(5) }}</p>
              </div>
              <div class="min-w-0 flex-1">
                <p class="lz-subtitle" :class="s.completed ? 'line-through opacity-70' : ''">
                  {{ s.planet_name || '冲刺任务' }}
                  <LzBadge v-if="s.date === todayIso && !s.completed" tone="warning" class="ml-1">今天</LzBadge>
                </p>
                <p class="lz-desc mt-0.5">{{ s.action }}</p>
                <p v-if="s.reason" class="lz-caption mt-0.5 opacity-75">{{ s.reason }}</p>
              </div>
              <LzButton v-if="!s.completed" variant="primary" size="sm" class="shrink-0" @click="completeSprint(i)">
                打卡
              </LzButton>
              <LzBadge v-else tone="success" class="shrink-0">✓</LzBadge>
            </div>
          </li>
        </ol>
        <LzButton variant="ghost" size="sm" block @click="sprint = null">重新生成冲刺计划</LzButton>
      </template>
    </template>

    <!-- ===== 常规路径 ===== -->
    <div v-if="tab === 'standard'" class="lz-card space-y-3 p-4">
      <label class="lz-desc block">本周学习目标</label>
      <LzInput v-model="goal" placeholder="例如：本周掌握高等数学多元函数微分" @enter="handleGenerate" />
      <LzButton variant="primary" size="md" block :loading="loading" @click="handleGenerate">
        {{ loading ? '规划中…' : '生成 / 重排路径' }}
      </LzButton>
    </div>

    <div v-if="tab === 'standard' && path" class="lz-card p-4">
      <div class="flex items-center justify-between gap-3">
        <div class="min-w-0">
          <p class="lz-subtitle truncate">{{ path.title }}</p>
          <p class="lz-caption mt-1">已完成 {{ doneCount }} / {{ totalSteps }} 步</p>
        </div>
        <div
          class="lz-accent-text flex h-12 w-12 shrink-0 items-center justify-center rounded-full border border-[rgb(var(--lz-accent)/0.3)] bg-[rgb(var(--lz-accent)/0.1)] font-mono-tech text-sm font-semibold"
        >
          {{ Math.round(path.progress) }}%
        </div>
      </div>
      <LzProgress :value="path.progress" class="mt-3" />

      <ol class="mt-4 space-y-3">
        <li
          v-for="(s, i) in path.steps"
          :key="i"
          class="p-3"
          :class="s.completed ? 'rounded-[var(--radius-card)] border border-emerald-400/25 bg-emerald-500/5' : 'lz-card lz-card--hover'"
        >
          <div class="flex items-start gap-3">
            <span
              class="flex h-6 w-6 shrink-0 items-center justify-center rounded-full font-mono-tech text-[10px] font-bold"
              :class="s.completed ? 'bg-emerald-400/20 text-emerald-200' : 'bg-slate-700/80 text-slate-300'"
            >
              {{ String(i + 1).padStart(2, '0') }}
            </span>
            <div class="min-w-0 flex-1">
              <p class="lz-subtitle">{{ s.planet_name || s.planet_slug }}</p>
              <p class="lz-desc mt-0.5">{{ s.action }}</p>
              <div class="mt-1 flex flex-wrap items-center gap-1.5">
                <p class="lz-caption lz-accent-text opacity-80">{{ s.reason }}</p>
                <LzBadge v-for="dim in s.weak_dims || []" :key="dim" tone="warning">{{ dim }}</LzBadge>
              </div>
              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <LzBadge v-for="kind in s.resource_kinds || []" :key="kind" tone="neutral">{{ kind }}</LzBadge>
                <span class="lz-caption">约 {{ s.estimated_minutes }} 分钟</span>
              </div>

              <div v-if="(s.mounted || []).length" class="mt-2.5 space-y-1.5">
                <p class="lz-caption uppercase tracking-wider">已挂载</p>
                <div
                  v-for="m in s.mounted"
                  :key="`${m.kind}-${m.id}`"
                  class="lz-card lz-card--flat flex items-start justify-between gap-2 px-2.5 py-2"
                >
                  <div class="min-w-0">
                    <p class="lz-subtitle">{{ m.title }}</p>
                    <p class="lz-caption mt-0.5">{{ m.kind }} · {{ m.id }}</p>
                    <p v-if="m.reason" class="lz-caption mt-0.5">{{ m.reason }}</p>
                    <div v-if="(s.weak_dims || []).length" class="mt-1 flex flex-wrap gap-1">
                      <LzBadge v-for="dim in s.weak_dims || []" :key="`m-${m.id}-${dim}`" tone="warning">
                        {{ dim }}
                      </LzBadge>
                    </div>
                  </div>
                  <div class="flex shrink-0 flex-col items-end gap-1">
                    <LzButton variant="soft" size="sm" @click="openMounted(m, s.planet_slug)">打开</LzButton>
                    <LzButton variant="danger" size="sm" @click="unmountItem(i, m.kind, m.id)">移除</LzButton>
                  </div>
                </div>
              </div>

              <div class="mt-2.5 flex flex-wrap items-center gap-2">
                <LzButton
                  v-if="s.planet_slug"
                  variant="soft"
                  size="sm"
                  @click="jumpToPlanet(s.planet_slug, s.planet_name)"
                >
                  跃迁星图
                </LzButton>
                <LzButton v-if="!s.completed" variant="primary" size="sm" @click="completeStep(i)">
                  完成打卡
                </LzButton>
                <LzBadge v-else tone="success">已完成</LzBadge>
              </div>

              <div class="mt-2 flex flex-wrap items-center gap-1.5">
                <div class="w-20">
                  <LzInput v-model="draftFor(i).kind" size="sm" placeholder="类型" />
                </div>
                <div class="min-w-[6rem] flex-1">
                  <LzInput v-model="draftFor(i).id" size="sm" placeholder="资源 id" />
                </div>
                <div class="min-w-[5rem] flex-1">
                  <LzInput v-model="draftFor(i).title" size="sm" placeholder="标题" />
                </div>
                <LzButton variant="soft" size="sm" @click="mountManual(i)">挂载</LzButton>
              </div>
            </div>
          </div>
        </li>
      </ol>
    </div>

    <div v-else-if="tab === 'standard'" class="lz-card lz-card--flat">
      <LzEmptyState icon="🧭" title="尚未生成路径" desc="填写目标后点击生成，将得到分步学习计划" />
    </div>

    <LzSection v-if="tab === 'standard' && recs.length" title="精准推送">
      <div class="space-y-2">
        <div v-for="(r, i) in recs" :key="i" class="lz-card lz-card--hover px-3 py-2.5">
          <div class="flex items-start justify-between gap-2">
            <div class="min-w-0">
              <p class="lz-subtitle">{{ r.title }}</p>
              <p class="lz-caption mt-1">{{ r.reason }}</p>
            </div>
            <div class="flex shrink-0 flex-col items-end gap-1">
              <LzButton variant="soft" size="sm" @click="goLearn(r)">去学习</LzButton>
              <LzButton v-if="path && path.steps.length" variant="ghost" size="sm" @click="mountRec(0, r)">
                挂到第1步
              </LzButton>
            </div>
          </div>
        </div>
      </div>
    </LzSection>
  </div>
</template>
