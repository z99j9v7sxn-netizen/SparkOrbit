<script setup lang="ts">
import * as echarts from 'echarts';
import { nextTick, onBeforeUnmount, ref, watch } from 'vue';
import type { VaultBacklinks, VaultGraph } from '../../../api/vault';
import VaultCanvas from '../VaultCanvas.vue';

const props = defineProps<{
  graph: VaultGraph | null;
  backlinks: VaultBacklinks | null;
  graphMode: 'local' | 'global';
  graphDepth: number;
  timelapseOn: boolean;
  collapsed?: boolean;
}>();

const emit = defineEmits<{
  (e: 'update:graphMode', v: 'local' | 'global'): void;
  (e: 'update:graphDepth', v: number): void;
  (e: 'toggle-timelapse'): void;
  (e: 'open-file', path: string): void;
  (e: 'status', msg: string): void;
  (e: 'update:collapsed', v: boolean): void;
}>();

const rightTab = ref<'graph' | 'canvas'>('graph');
const linksOpen = ref(false);
const graphRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;

function renderGraph(filterBefore?: string) {
  if (!graphRef.value || !props.graph) return;
  if (!chart) chart = echarts.init(graphRef.value);
  const catMap = Object.fromEntries((props.graph.categories || []).map((c, i) => [c.name, i]));
  const colors: Record<string, string> = {
    planet: '#7c5cff',
    clip: '#38bdf8',
    habit: '#f59e0b',
    daily: '#34d399',
    note: '#94a3b8',
    ghost: '#64748b',
  };
  let nodes = props.graph.nodes;
  if (filterBefore) {
    nodes = nodes.filter((n) => !n.created_at || n.created_at <= filterBefore);
  }
  const ids = new Set(nodes.map((n) => n.id));
  const links = props.graph.edges.filter((e) => ids.has(e.source) && ids.has(e.target));
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: {
      formatter: (p: { data?: { path?: string }; name?: string }) => p.data?.path || p.name || '',
    },
    series: [
      {
        type: 'graph',
        layout: 'force',
        roam: true,
        draggable: true,
        label: { show: true, color: '#e2e8f0', fontSize: 12 },
        force: { repulsion: 180, edgeLength: [60, 160] },
        data: nodes.map((n) => ({
          ...n,
          category: catMap[n.category] ?? 0,
          itemStyle: { color: colors[n.category] || '#94a3b8' },
        })),
        links: links.map((e) => ({ source: e.source, target: e.target })),
        categories: props.graph.categories,
        lineStyle: { color: 'rgba(148,163,184,0.45)', curveness: 0.08 },
        emphasis: { focus: 'adjacency' },
      },
    ],
  });
  chart.off('click');
  chart.on('click', (params: unknown) => {
    const p = params as { data?: { path?: string; id?: string } };
    const path = p?.data?.path || p?.data?.id;
    if (path && String(path).endsWith('.md')) emit('open-file', String(path));
  });
}

watch(
  () => props.graph,
  async () => {
    await nextTick();
    renderGraph();
    chart?.resize();
  },
  { deep: true },
);

watch(
  () => props.collapsed,
  async (c) => {
    if (!c) {
      await nextTick();
      renderGraph();
      chart?.resize();
    }
  },
);

watch(rightTab, async (tab) => {
  if (tab === 'graph') {
    await nextTick();
    renderGraph();
    chart?.resize();
  }
});

watch(linksOpen, async () => {
  await nextTick();
  chart?.resize();
});

onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});

defineExpose({
  renderGraph,
  resize: () => chart?.resize(),
  openCanvas: () => {
    rightTab.value = 'canvas';
  },
});
</script>

<template>
  <aside
    class="flex h-full min-h-0 flex-col overflow-hidden transition-all"
    :class="collapsed ? 'w-10' : 'w-[min(480px,40vw)]'"
  >
    <button
      v-if="collapsed"
      type="button"
      class="flex h-full flex-col items-center gap-2 rounded-2xl border border-white/10 bg-slate-950/50 px-1 py-3 text-[10px] text-slate-400 hover:bg-white/5"
      @click="emit('update:collapsed', false)"
    >
      <span class="writing-vertical">展开图谱</span>
    </button>
    <div v-else class="flex h-full min-h-0 flex-col gap-2">
      <div class="flex items-center gap-1 text-[10px]">
        <button
          type="button"
          class="rounded-lg px-2 py-1"
          :class="rightTab === 'graph' ? 'bg-[rgb(var(--lz-accent)/0.25)] text-white' : 'text-slate-500'"
          @click="rightTab = 'graph'"
        >
          关系图谱
        </button>
        <button
          type="button"
          class="rounded-lg px-2 py-1"
          :class="rightTab === 'canvas' ? 'bg-[rgb(var(--lz-accent)/0.25)] text-white' : 'text-slate-500'"
          @click="rightTab = 'canvas'"
        >
          画布
        </button>
        <button
          type="button"
          class="ml-auto rounded-lg px-2 py-1 text-slate-500 hover:bg-white/5 hover:text-slate-300"
          @click="emit('update:collapsed', true)"
        >
          收起
        </button>
      </div>

      <div
        v-show="rightTab === 'graph'"
        class="flex min-h-0 flex-1 flex-col overflow-hidden rounded-2xl border border-white/10 bg-slate-950/50"
      >
        <div class="flex flex-wrap items-center gap-2 border-b border-white/5 px-2 py-1.5 text-[10px]">
          <button
            type="button"
            class="rounded px-1.5 py-0.5"
            :class="graphMode === 'local' ? 'bg-[rgb(var(--lz-accent)/0.25)] text-[rgb(var(--lz-accent-bright))]' : 'text-slate-500'"
            @click="emit('update:graphMode', 'local')"
          >
            局部
          </button>
          <button
            type="button"
            class="rounded px-1.5 py-0.5"
            :class="graphMode === 'global' ? 'bg-[rgb(var(--lz-accent)/0.25)] text-[rgb(var(--lz-accent-bright))]' : 'text-slate-500'"
            @click="emit('update:graphMode', 'global')"
          >
            全局
          </button>
          <button
            type="button"
            class="rounded px-1.5 py-0.5"
            :class="timelapseOn ? 'bg-emerald-500/25 text-emerald-100' : 'text-slate-500'"
            @click="emit('toggle-timelapse')"
          >
            {{ timelapseOn ? '停止时间线' : '时间线' }}
          </button>
          <label v-if="graphMode === 'local'" class="ml-auto flex items-center gap-1 text-slate-500">
            深度
            <input
              :value="graphDepth"
              type="range"
              min="1"
              max="3"
              class="w-16"
              @input="emit('update:graphDepth', Number(($event.target as HTMLInputElement).value))"
            />
            {{ graphDepth }}
          </label>
        </div>
        <div ref="graphRef" class="min-h-[280px] flex-1" />
      </div>

      <div
        v-show="rightTab === 'canvas'"
        class="min-h-0 flex-1 overflow-hidden rounded-2xl border border-white/10 bg-slate-950/50 p-2"
      >
        <VaultCanvas @open-file="(p) => emit('open-file', p)" @status="(m) => emit('status', m)" />
      </div>

      <div class="rounded-2xl border border-white/10 bg-slate-950/50 text-[11px]">
        <button
          type="button"
          class="flex w-full items-center justify-between px-2 py-1.5 text-left text-[10px] uppercase tracking-wider text-slate-500 hover:bg-white/5"
          @click="linksOpen = !linksOpen"
        >
          <span>反向链接 / 出链</span>
          <span class="normal-case tracking-normal text-slate-600">{{ linksOpen ? '收起' : '展开' }}</span>
        </button>
        <div v-show="linksOpen" class="max-h-36 overflow-auto border-t border-white/5 p-2">
          <p class="mb-1 text-[10px] uppercase tracking-wider text-slate-500">反向链接</p>
          <button
            v-for="b in backlinks?.backlinks || []"
            :key="'b-' + b.path"
            type="button"
            class="block w-full truncate rounded px-1 py-0.5 text-left text-sky-200/90 hover:bg-white/5"
            @click="emit('open-file', b.path)"
          >
            ← {{ b.title }}
          </button>
          <p v-if="!(backlinks?.backlinks || []).length" class="text-slate-600">暂无反向链接</p>
          <p class="mb-1 mt-2 text-[10px] uppercase tracking-wider text-slate-500">出链</p>
          <button
            v-for="o in backlinks?.outgoing || []"
            :key="'o-' + o.path"
            type="button"
            class="block w-full truncate rounded px-1 py-0.5 text-left text-violet-200/90 hover:bg-white/5"
            @click="o.exists ? emit('open-file', o.path) : undefined"
          >
            → {{ o.title }}{{ o.exists ? '' : '（未创建）' }}
          </button>
        </div>
      </div>
    </div>
  </aside>
</template>

<style scoped>
.writing-vertical {
  writing-mode: vertical-rl;
  letter-spacing: 0.15em;
}
</style>
