<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';
import {
  clipNote,
  completeViz,
  generateViz,
  getVizTrace,
  listVizTraces,
  matchVizTrace,
  predictViz,
  rerunViz,
  type VizTrace,
} from '../../api/challengeSprint';
import { fetchLearningPath, mountPathStep } from '../../api/learnExtras';
import { useOrbitStore } from '../../stores/orbit';
import { LzButton, LzInput, LzTabs } from './ui';

const orbit = useOrbitStore();
const planetSlug = computed(() => orbit.selectedPlanet?.slug || '');
const planetName = computed(() => orbit.selectedPlanet?.name || '');
const traces = ref<Array<{ id: string; title: string; structure: string; step_count: number }>>([]);
const trace = ref<VizTrace | null>(null);
const stepIdx = ref(0);
const playing = ref(false);
const speedMs = ref(900);
const status = ref('');
const mode = ref<'play' | 'edit'>('play');
const aiTopic = ref('');
const aiLoading = ref(false);
const editBars = ref<number[]>([]);
const editSeq = ref('');
const editEdges = ref('');
const editStart = ref('A');
const predictAnswer = ref('');
const predictBusy = ref(false);
const mountingPath = ref(false);
let timer: number | null = null;

const step = computed(() => trace.value?.steps?.[stepIdx.value] || null);
const codeLines = computed(() => (trace.value?.code || '').split('\n'));
const predictMeta = computed(() => step.value?.predict || null);
const canPredict = computed(() => {
  const steps = trace.value?.steps;
  if (!steps?.length) return false;
  return stepIdx.value < steps.length - 1;
});
const predictQuestion = computed(() => predictMeta.value?.question || '请预测下一步会发生什么？');

function edgeKey(u: string, v: string) {
  return `${u}-${v}`;
}

function nodeAt(nodes: Array<{ id: string; x: number; y: number }>, id: string) {
  return nodes.find((n) => n.id === id);
}

function edgeHighlighted(e: Array<string | number>, highlight: Array<string | number> = []) {
  const u = String(e[0]);
  const v = String(e[1]);
  return highlight.includes(edgeKey(u, v)) || highlight.includes(edgeKey(v, u));
}

function nodeHighlighted(id: string, highlight: Array<string | number> = []) {
  return highlight.includes(id);
}

function edgeWeight(e: Array<string | number>) {
  return e.length >= 3 ? String(e[2]) : '';
}

async function load() {
  try {
    traces.value = await listVizTraces();
    aiTopic.value = planetName.value ? `演示一下${planetName.value}` : '冒泡排序';
    if (!planetSlug.value) {
      if (traces.value[0]) trace.value = await getVizTrace(traces.value[0].id);
      syncEditFromTrace();
      return;
    }
    try {
      trace.value = await matchVizTrace(planetSlug.value);
    } catch {
      if (traces.value[0]) trace.value = await getVizTrace(traces.value[0].id);
    }
    stepIdx.value = 0;
    syncEditFromTrace();
  } catch (e) {
    status.value = e instanceof Error ? e.message : '演武舱加载失败';
    if (!trace.value && traces.value[0]) {
      try {
        trace.value = await getVizTrace(traces.value[0].id);
        syncEditFromTrace();
      } catch {
        /* ignore */
      }
    }
  }
}

function syncEditFromTrace() {
  if (!trace.value) return;
  if (trace.value.structure === 'array') {
    const bars = (trace.value.steps?.[0]?.bars as number[]) || [5, 2, 9, 1, 6];
    editBars.value = bars.map((n) => Number(n));
  } else if (trace.value.structure === 'graph') {
    const init = (trace.value as VizTrace & { initial?: Record<string, unknown> }).initial || {};
    const edges = (init.edges as Array<Array<string | number>>) || (trace.value.steps?.[0]?.edges as Array<Array<string | number>>) || [];
    editEdges.value = edges
      .map((e) => (e.length >= 3 ? `${e[0]} ${e[1]} ${e[2]}` : `${e[0]} ${e[1]}`))
      .join('\n');
    editStart.value = String(init.start || 'A');
  } else {
    const vars = trace.value.steps?.[0]?.vars || {};
    const seq = (vars as { seq?: string }).seq || '[8, 3, 10, 1, 6]';
    editSeq.value = String(seq).replace(/[\[\]]/g, '');
  }
}

function stopPlay() {
  playing.value = false;
  if (timer) {
    window.clearInterval(timer);
    timer = null;
  }
}

function play() {
  if (!trace.value?.steps?.length) return;
  playing.value = true;
  timer = window.setInterval(() => {
    if (stepIdx.value >= (trace.value?.steps.length || 1) - 1) {
      stopPlay();
      void finish();
      return;
    }
    stepIdx.value += 1;
  }, speedMs.value);
}

function next() {
  if (!trace.value) return;
  stepIdx.value = Math.min(stepIdx.value + 1, trace.value.steps.length - 1);
  if (stepIdx.value === trace.value.steps.length - 1) void finish();
}

function prev() {
  stepIdx.value = Math.max(0, stepIdx.value - 1);
}

function reset() {
  stopPlay();
  stepIdx.value = 0;
}

async function finish() {
  if (!trace.value || !planetSlug.value) return;
  try {
    await completeViz(planetSlug.value, trace.value.id, stepIdx.value + 1, trace.value.steps.length);
    status.value = '已计入「学」闸证据';
  } catch (e) {
    status.value = String(e);
  }
}

async function clip() {
  if (!planetSlug.value) {
    status.value = '请先选择行星再剪藏';
    return;
  }
  if (!trace.value || !step.value) {
    status.value = '请先加载演示步骤再剪藏';
    return;
  }
  try {
    await clipNote(
      planetSlug.value,
      {
        kind: 'viz_clip',
        trace_id: trace.value.id,
        step: stepIdx.value,
        narrate: step.value.narrate,
        line: step.value.line,
      },
      `${trace.value.title} · 剪藏`,
    );
    status.value = '已写入星轨知识库 · 演武剪藏';
  } catch (e) {
    status.value = e instanceof Error ? e.message : '演武剪藏失败';
  }
}

async function submitPredict(answer?: string) {
  if (!trace.value || !canPredict.value) return;
  const ans = (answer ?? predictAnswer.value).trim();
  if (!ans) {
    status.value = '请选择或填写预测答案';
    return;
  }
  predictBusy.value = true;
  try {
    const res = await predictViz({
      trace_id: trace.value.id,
      step_index: stepIdx.value,
      answer: ans,
      planet_slug: planetSlug.value || undefined,
    });
    if (res.correct) {
      status.value = res.apply_credit
        ? `预测正确，已记入「用」闸${res.lit ? ' · 行星点亮！' : ''}`
        : '预测正确';
      predictAnswer.value = '';
    } else {
      status.value = `预测有误，正确答案参考：${res.expected || '见下一步'}`;
    }
  } catch (e) {
    status.value = e instanceof Error ? e.message : '预测提交失败';
  } finally {
    predictBusy.value = false;
  }
}

async function askAi() {
  const topic = aiTopic.value.trim();
  if (!topic) return;
  aiLoading.value = true;
  status.value = 'VizAgent（DeepSeek）生成中…';
  stopPlay();
  try {
    const t = await generateViz(topic, planetSlug.value);
    trace.value = t;
    stepIdx.value = 0;
    syncEditFromTrace();
    status.value = `已生成：${t.title}${(t as VizTrace & { source?: string }).source ? ` · ${(t as VizTrace & { source?: string }).source}` : ''}`;
  } catch (e) {
    status.value = e instanceof Error ? e.message : '生成失败';
  } finally {
    aiLoading.value = false;
  }
}

function bumpBar(i: number, delta: number) {
  const next = [...editBars.value];
  next[i] = Math.max(0, Math.min(20, (next[i] || 0) + delta));
  editBars.value = next;
}

function setBar(i: number, raw: string) {
  const n = Number(raw);
  if (Number.isNaN(n)) return;
  const next = [...editBars.value];
  next[i] = Math.max(0, Math.min(99, Math.round(n)));
  editBars.value = next;
}

async function rerunEdited() {
  if (!trace.value) return;
  stopPlay();
  status.value = '按新数据重新推演…';
  try {
    const structure = trace.value.structure || 'array';
    let initial: Record<string, unknown>;
    if (structure === 'tree') {
      initial = { seq: editSeq.value.split(/[,\s]+/).filter(Boolean).map((x) => Number(x)).filter((n) => !Number.isNaN(n)) };
    } else if (structure === 'graph') {
      const init = (trace.value as VizTrace & { initial?: Record<string, unknown>; algo?: string }).initial || {};
      const edges = editEdges.value
        .split('\n')
        .map((l) => l.trim())
        .filter(Boolean)
        .map((line) => {
          const parts = line.split(/\s+/);
          if (parts.length >= 3) return [parts[0], parts[1], Number(parts[2])];
          return [parts[0], parts[1]];
        });
      initial = {
        start: editStart.value.trim() || 'A',
        nodes: init.nodes || trace.value.steps?.[0]?.nodes,
        edges,
        algo: (trace.value as VizTrace & { algo?: string }).algo || init.algo,
      };
    } else {
      initial = { arr: [...editBars.value] };
    }
    const t = await rerunViz({
      structure,
      code: trace.value.code,
      initial,
      title: `${trace.value.title} · 重跑`,
    });
    trace.value = t;
    stepIdx.value = 0;
    mode.value = 'play';
    status.value = '已用新数据生成轨迹，可播放对比';
  } catch (e) {
    status.value = e instanceof Error ? e.message : '重跑失败';
  }
}

async function mountCurrentToPath() {
  if (!trace.value?.id || mountingPath.value) return;
  mountingPath.value = true;
  try {
    const path = await fetchLearningPath();
    if (!path?.steps?.length) {
      status.value = '请先在「学习路径」生成计划后再挂载';
      return;
    }
    const matchIdx = path.steps.findIndex((s) => s.planet_slug && s.planet_slug === planetSlug.value);
    const stepIndex = matchIdx >= 0 ? matchIdx : 0;
    await mountPathStep(stepIndex, {
      kind: 'viz',
      id: trace.value.id,
      title: trace.value.title || trace.value.id,
      reason: `演武舱 · ${trace.value.structure || 'trace'}`,
    });
    status.value = `已挂到路径第 ${stepIndex + 1} 步：${trace.value.title}`;
  } catch (e) {
    status.value = e instanceof Error ? e.message : '挂到路径失败';
  } finally {
    mountingPath.value = false;
  }
}

onMounted(() => void load());
watch(planetSlug, () => void load());
onBeforeUnmount(() => stopPlay());
</script>

<template>
  <div class="space-y-3 text-slate-200">
    <div class="flex flex-wrap items-center justify-between gap-2">
      <div>
        <p class="lz-caption uppercase tracking-[0.3em] lz-accent-text opacity-80">Algo Viz</p>
        <h3 class="lz-title">演武舱 · 逐步可视化</h3>
        <p class="lz-desc">{{ trace?.title || '加载中…' }} · AI 生成 + 可视化修改重跑</p>
      </div>
      <div class="flex flex-wrap items-center gap-2">
        <LzTabs
          :items="[
            { key: 'play', label: '步进演示' },
            { key: 'edit', label: '可视化修改' },
          ]"
          :model-value="mode"
          @update:model-value="(v) => { mode = v as 'play' | 'edit'; if (v === 'edit') stopPlay(); }"
        />
        <select
          v-if="traces.length"
          class="lz-input h-8 w-auto px-2 text-xs"
          :value="trace?.id"
          @change="getVizTrace(($event.target as HTMLSelectElement).value).then((t) => { trace = t; stepIdx = 0; syncEditFromTrace() })"
        >
          <option v-for="t in traces" :key="t.id" :value="t.id">{{ t.title }}</option>
        </select>
        <LzButton variant="soft" size="sm" :loading="mountingPath" :disabled="!trace?.id" @click="mountCurrentToPath">
          {{ mountingPath ? '挂载中…' : '挂到路径' }}
        </LzButton>
      </div>
    </div>

    <form class="flex flex-wrap gap-2" @submit.prevent="askAi">
      <div class="min-w-[220px] flex-1">
        <LzInput v-model="aiTopic" placeholder="想看什么？例如：红黑树旋转 / 快排一趟" />
      </div>
      <LzButton type="submit" variant="primary" :loading="aiLoading" :disabled="!aiTopic.trim()">
        {{ aiLoading ? '生成中…' : 'AI 生成演示' }}
      </LzButton>
    </form>

    <div v-if="canPredict" class="lz-card lz-card--active p-3">
      <p class="lz-caption uppercase tracking-wider lz-accent-text opacity-80">Predict Next</p>
      <p class="lz-body mt-1 text-white">{{ predictQuestion }}</p>
      <div v-if="predictMeta?.options?.length" class="mt-2 flex flex-wrap gap-2">
        <LzButton
          v-for="opt in predictMeta.options"
          :key="opt.key"
          variant="soft"
          size="sm"
          :disabled="predictBusy"
          @click="submitPredict(opt.key)"
        >
          {{ opt.key }}. {{ opt.text }}
        </LzButton>
      </div>
      <div v-else class="mt-2 flex flex-wrap gap-2">
        <div class="min-w-[160px] flex-1">
          <LzInput v-model="predictAnswer" placeholder="输入你的预测" @enter="submitPredict()" />
        </div>
        <LzButton variant="soft" :loading="predictBusy" @click="submitPredict()">提交预测</LzButton>
      </div>
    </div>

    <div v-if="mode === 'edit'" class="lz-card p-3">
      <p class="lz-subtitle">修改初始数据后点「重新推演」，动画会变</p>
      <div v-if="trace?.structure === 'array'" class="mt-3 flex flex-wrap items-end gap-3">
        <div v-for="(v, i) in editBars" :key="i" class="flex flex-col items-center gap-1">
          <button type="button" class="lz-btn lz-btn--ghost h-6 w-8 rounded-md px-0 text-xs" @click="bumpBar(i, 1)">+</button>
          <input
            class="lz-input w-10 py-1 text-center"
            :value="v"
            @change="setBar(i, ($event.target as HTMLInputElement).value)"
          />
          <button type="button" class="lz-btn lz-btn--ghost h-6 w-8 rounded-md px-0 text-xs" @click="bumpBar(i, -1)">−</button>
          <span class="lz-caption">[{{ i }}]</span>
        </div>
        <LzButton variant="ghost" size="sm" @click="editBars = [...editBars, 1]">+列</LzButton>
      </div>
      <div v-else-if="trace?.structure === 'tree'" class="mt-3">
        <label class="lz-caption">插入序列（逗号分隔）</label>
        <div class="mt-1">
          <LzInput v-model="editSeq" placeholder="8, 3, 10, 1, 6" />
        </div>
      </div>
      <div v-else-if="trace?.structure === 'graph'" class="mt-3 space-y-2">
        <div>
          <label class="lz-caption">边列表（每行 u v 或 u v w）</label>
          <textarea
            v-model="editEdges"
            rows="4"
            class="lz-input mt-1 px-3 py-2 font-mono-tech"
            placeholder="A B&#10;B C 3"
          />
        </div>
        <div>
          <label class="lz-caption">起点</label>
          <div class="mt-1 w-32">
            <LzInput v-model="editStart" placeholder="A" />
          </div>
        </div>
      </div>
      <LzButton variant="primary" class="mt-3" @click="rerunEdited">重新推演</LzButton>
    </div>

    <div class="flex flex-wrap items-center gap-2">
      <LzButton variant="ghost" size="sm" @click="reset">重置</LzButton>
      <LzButton variant="ghost" size="sm" @click="prev">上一步</LzButton>
      <LzButton variant="primary" size="sm" @click="playing ? stopPlay() : play()">
        {{ playing ? '暂停' : '播放' }}
      </LzButton>
      <LzButton variant="ghost" size="sm" @click="next">下一步</LzButton>
      <LzButton
        variant="soft"
        size="sm"
        :disabled="!planetSlug || !trace || !step"
        :title="!planetSlug ? '请先选择行星再剪藏' : !trace || !step ? '请先加载演示步骤' : '将当前步收入笔记'"
        @click="clip"
      >
        剪藏本步
      </LzButton>
      <label class="lz-caption ml-auto flex items-center gap-1">
        速度
        <select v-model.number="speedMs" class="lz-input h-7 w-auto px-1.5 text-xs">
          <option :value="1400">慢</option>
          <option :value="900">中</option>
          <option :value="450">快</option>
        </select>
      </label>
    </div>

    <div class="grid gap-3 md:grid-cols-2">
      <pre class="lz-card lz-card--flat max-h-72 overflow-auto p-3 font-mono-tech text-[11px] leading-5"><code><span
          v-for="(line, i) in codeLines"
          :key="i"
          class="block"
          :class="step?.line === i + 1 ? 'bg-[rgb(var(--lz-accent)/0.18)] text-white' : 'text-slate-300/85'"
        >{{ String(i + 1).padStart(2, ' ') }}  {{ line }}</span></code></pre>

      <div class="lz-card lz-card--flat relative h-72 overflow-hidden p-3">
        <svg v-if="trace?.structure === 'tree'" class="h-full w-full" viewBox="0 0 100 100">
          <line
            v-for="(e, i) in (step?.edges || [])"
            :key="'e' + i"
            :x1="((step?.nodes || []).find((n) => n.id === e[0])?.x || 0) * 100"
            :y1="((step?.nodes || []).find((n) => n.id === e[0])?.y || 0) * 100"
            :x2="((step?.nodes || []).find((n) => n.id === e[1])?.x || 0) * 100"
            :y2="((step?.nodes || []).find((n) => n.id === e[1])?.y || 0) * 100"
            stroke="url(#vizEdge)"
            stroke-width="0.8"
          />
          <defs>
            <linearGradient id="vizEdge" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#22d3ee" />
              <stop offset="100%" stop-color="#a78bfa" />
            </linearGradient>
          </defs>
          <g v-for="n in step?.nodes || []" :key="n.id">
            <circle
              :cx="n.x * 100"
              :cy="n.y * 100"
              r="5.5"
              :fill="(step?.highlight || []).includes(n.id) ? '#22d3ee' : '#1e293b'"
              stroke="#94a3b8"
              stroke-width="0.6"
            />
            <text :x="n.x * 100" :y="n.y * 100 + 1.5" text-anchor="middle" font-size="4" fill="#e2e8f0">{{ n.label }}</text>
          </g>
        </svg>
        <svg v-else-if="trace?.structure === 'graph'" class="h-full w-full" viewBox="0 0 100 100">
          <defs>
            <linearGradient id="vizGraphEdge" x1="0" y1="0" x2="1" y2="1">
              <stop offset="0%" stop-color="#22d3ee" />
              <stop offset="100%" stop-color="#a78bfa" />
            </linearGradient>
          </defs>
          <g v-for="(e, i) in (step?.edges || [])" :key="'ge' + i">
            <line
              :x1="(nodeAt(step?.nodes || [], String(e[0]))?.x || 0) * 100"
              :y1="(nodeAt(step?.nodes || [], String(e[0]))?.y || 0) * 100"
              :x2="(nodeAt(step?.nodes || [], String(e[1]))?.x || 0) * 100"
              :y2="(nodeAt(step?.nodes || [], String(e[1]))?.y || 0) * 100"
              stroke="url(#vizGraphEdge)"
              :stroke-width="edgeHighlighted(e, step?.highlight || []) ? 1.4 : 0.8"
              :opacity="edgeHighlighted(e, step?.highlight || []) ? 1 : 0.55"
            />
            <text
              v-if="edgeWeight(e)"
              :x="(((nodeAt(step?.nodes || [], String(e[0]))?.x || 0) + (nodeAt(step?.nodes || [], String(e[1]))?.x || 0)) / 2) * 100"
              :y="(((nodeAt(step?.nodes || [], String(e[0]))?.y || 0) + (nodeAt(step?.nodes || [], String(e[1]))?.y || 0)) / 2) * 100 - 1.5"
              text-anchor="middle"
              font-size="3.2"
              fill="#fbbf24"
            >{{ edgeWeight(e) }}</text>
          </g>
          <g v-for="n in step?.nodes || []" :key="n.id">
            <circle
              :cx="n.x * 100"
              :cy="n.y * 100"
              r="5.5"
              :fill="nodeHighlighted(n.id, step?.highlight || []) ? '#22d3ee' : '#1e293b'"
              stroke="#94a3b8"
              stroke-width="0.6"
            />
            <text :x="n.x * 100" :y="n.y * 100 + 1.5" text-anchor="middle" font-size="4" fill="#e2e8f0">{{ n.label }}</text>
          </g>
        </svg>
        <div v-else class="flex h-full items-end justify-center gap-2 px-4 pb-8">
          <div
            v-for="(v, i) in step?.bars || []"
            :key="i"
            class="flex w-10 flex-col items-center gap-1"
          >
            <div
              class="w-full rounded-t transition-all"
              :class="(step?.highlight || []).includes(i) ? 'bg-[rgb(var(--lz-accent-bright))] shadow-[0_0_12px_rgb(var(--lz-accent)/0.9)]' : 'bg-slate-500'"
              :style="{ height: `${Math.max(8, Number(v) * 12)}px` }"
            />
            <span class="lz-caption">{{ v }}</span>
          </div>
        </div>
        <p class="lz-desc absolute bottom-2 left-3 right-3">{{ step?.narrate }}</p>
      </div>
    </div>

    <div class="lz-caption grid gap-2 md:grid-cols-2">
      <p>变量：{{ JSON.stringify(step?.vars || {}) }}</p>
      <p>调用栈：{{ (step?.stack || []).join(' → ') }}</p>
    </div>
    <p v-if="status" class="lz-desc lz-accent-text">{{ status }}</p>
    <p class="lz-caption">步骤 {{ stepIdx + 1 }} / {{ trace?.steps?.length || 0 }}</p>
  </div>
</template>
