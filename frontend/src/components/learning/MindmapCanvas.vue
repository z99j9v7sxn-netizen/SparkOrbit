<script setup lang="ts">
import * as echarts from 'echarts';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

type MindNode = {
  name: string;
  children?: MindNode[];
  planet_slug?: string;
  mastery?: 'dim' | 'lit' | 'fading' | string;
  summary?: string;
};

const props = defineProps<{
  tree: MindNode;
  heightClass?: string;
  /** 可选：行星 slug → 掌握状态，用于节点着色 */
  masteryMap?: Record<string, string>;
}>();

const emit = defineEmits<{
  (e: 'node-click', name: string, meta?: MindNode): void;
}>();

const el = ref<HTMLDivElement | null>(null);
const hoverCard = ref<{ name: string; summary: string; mastery: string; x: number; y: number } | null>(null);
let chart: echarts.ECharts | null = null;

const depthColors = ['#38bdf8', '#818cf8', '#c084fc', '#f472b6', '#34d399', '#fbbf24'];

function enrich(node: MindNode, depth = 0): Record<string, unknown> {
  const status =
    (node.planet_slug && props.masteryMap?.[node.planet_slug]) ||
    node.mastery ||
    (depth === 0 ? 'root' : 'dim');
  const color =
    status === 'lit'
      ? '#34d399'
      : status === 'fading' || status === 'meteor'
        ? '#fb923c'
        : status === 'dim'
          ? '#64748b'
          : depthColors[Math.min(depth, depthColors.length - 1)];
  const badge =
    status === 'lit' ? '●已掌握' : status === 'fading' || status === 'meteor' ? '◐需复习' : status === 'dim' ? '○未点亮' : '';
  return {
    name: node.name,
    planet_slug: node.planet_slug,
    summary: node.summary || `${node.name} · 点击展开动作`,
    mastery: status,
    itemStyle: {
      color,
      borderColor: 'rgba(255,255,255,0.65)',
      borderWidth: depth === 0 ? 2.5 : 1.5,
      shadowBlur: status === 'lit' ? 22 : depth === 0 ? 16 : 10,
      shadowColor: color,
    },
    label: {
      color: '#f8fafc',
      fontSize: depth === 0 ? 15 : depth === 1 ? 13 : 11,
      fontWeight: depth <= 1 ? 700 : 500,
      backgroundColor: 'rgba(15, 23, 42, 0.88)',
      borderColor: `${color}aa`,
      borderWidth: 1.2,
      borderRadius: 12,
      padding: [8, 12],
      shadowBlur: 14,
      shadowColor: 'rgba(0,0,0,0.4)',
      formatter: badge ? `{name|${node.name}}\n{badge|${badge}}` : `{name|${node.name}}`,
      rich: {
        name: { color: '#f8fafc', fontSize: depth === 0 ? 15 : 12, fontWeight: 600, lineHeight: 18 },
        badge: { color, fontSize: 10, lineHeight: 14, padding: [2, 0, 0, 0] },
      },
    },
    symbolSize: depth === 0 ? [22, 22] : depth === 1 ? [16, 16] : [12, 12],
    children: (node.children || []).map((c) => enrich(c, depth + 1)),
  };
}

const enrichedRoot = computed(() => enrich(props.tree || { name: '思维导图', children: [] }));

function render() {
  if (!el.value) return;
  if (!chart) chart = echarts.init(el.value, undefined, { renderer: 'canvas' });
  chart.setOption(
    {
      backgroundColor: 'transparent',
      tooltip: {
        trigger: 'item',
        triggerOn: 'mousemove',
        backgroundColor: 'rgba(15,23,42,0.94)',
        borderColor: 'rgba(56,189,248,0.5)',
        textStyle: { color: '#e2e8f0', fontSize: 12 },
        formatter: (p: unknown) => {
          const d = (p as { data?: MindNode & { mastery?: string } })?.data;
          if (!d) return '';
          const m = d.mastery ? `<br/><span style="color:#7dd3fc">掌握度：${d.mastery}</span>` : '';
          return `<div style="max-width:240px"><b>${d.name}</b>${m}<br/><span style="opacity:.75">${d.summary || '知识点节点'}</span></div>`;
        },
      },
      series: [
        {
          type: 'tree',
          data: [enrichedRoot.value],
          top: '5%',
          left: '3%',
          bottom: '5%',
          right: '24%',
          symbol: 'roundRect',
          symbolSize: 14,
          orient: 'LR',
          expandAndCollapse: true,
          initialTreeDepth: 4,
          edgeShape: 'curve',
          edgeForkPosition: '63%',
          roam: true,
          scaleLimit: { min: 0.4, max: 2.6 },
          lineStyle: {
            color: {
              type: 'linear',
              x: 0,
              y: 0,
              x2: 1,
              y2: 1,
              colorStops: [
                { offset: 0, color: 'rgba(56,189,248,0.75)' },
                { offset: 0.55, color: 'rgba(167,139,250,0.65)' },
                { offset: 1, color: 'rgba(244,114,182,0.45)' },
              ],
            },
            width: 2.4,
            curveness: 0.62,
            shadowBlur: 10,
            shadowColor: 'rgba(56,189,248,0.3)',
          },
          leaves: {
            label: {
              color: '#e0e7ff',
              backgroundColor: 'rgba(30, 27, 75, 0.82)',
              borderColor: 'rgba(167,139,250,0.5)',
            },
          },
          emphasis: {
            focus: 'descendant',
            itemStyle: { borderWidth: 2.5, shadowBlur: 28 },
            lineStyle: { width: 3.5 },
          },
          animationDuration: 560,
          animationDurationUpdate: 420,
          animationEasing: 'cubicOut',
        },
      ],
    },
    true,
  );
  chart.off('click');
  chart.on('click', (p) => {
    const data = p.data as MindNode;
    const name = String(data?.name || '');
    if (name) emit('node-click', name, data);
  });
  chart.off('mouseover');
  chart.on('mouseover', (p) => {
    const data = p.data as MindNode & { mastery?: string };
    if (!data?.name || !el.value) return;
    const rect = el.value.getBoundingClientRect();
    const ev = p.event?.event as MouseEvent | undefined;
    hoverCard.value = {
      name: data.name,
      summary: data.summary || '点击节点可追问 / 跳转行星',
      mastery: String(data.mastery || ''),
      x: (ev?.clientX || rect.left + 40) - rect.left + 12,
      y: (ev?.clientY || rect.top + 40) - rect.top + 12,
    };
  });
  chart.off('mouseout');
  chart.on('mouseout', () => {
    hoverCard.value = null;
  });
}

function fullscreen() {
  el.value?.parentElement?.requestFullscreen?.() || el.value?.requestFullscreen?.();
}

function exportPng() {
  if (!chart) return;
  const url = chart.getDataURL({ type: 'png', pixelRatio: 2, backgroundColor: '#0b1220' });
  const a = document.createElement('a');
  a.href = url;
  a.download = `mindmap_${Date.now()}.png`;
  a.click();
}

onMounted(() => {
  render();
  window.addEventListener('resize', () => chart?.resize());
});
watch(() => [props.tree, props.masteryMap], () => render(), { deep: true });
onBeforeUnmount(() => {
  chart?.dispose();
  chart = null;
});

defineExpose({ fullscreen, render, exportPng });
</script>

<template>
  <div class="relative space-y-2">
    <div class="flex flex-wrap items-center justify-between gap-2 text-[11px]">
      <p class="text-slate-400">拖拽平移 · 滚轮缩放 · 点击折叠/展开 · 节点按掌握度着色</p>
      <div class="flex gap-2">
        <button class="rounded-full border border-white/15 bg-white/5 px-2.5 py-1 text-slate-200 hover:bg-white/10" @click="render">刷新</button>
        <button class="rounded-full border border-emerald-400/40 bg-emerald-500/15 px-2.5 py-1 text-emerald-50 hover:bg-emerald-500/25" @click="exportPng">导出 PNG</button>
        <button class="rounded-full border border-[rgb(var(--lz-accent)/0.4)] bg-[rgb(var(--lz-accent)/0.15)] px-2.5 py-1 font-semibold text-white hover:bg-[rgb(var(--lz-accent)/0.25)]" @click="fullscreen">全屏</button>
      </div>
    </div>
    <div class="relative overflow-hidden rounded-2xl border border-[rgb(var(--lz-accent)/0.25)] bg-[radial-gradient(ellipse_at_top,_rgb(var(--lz-accent)/0.12),_transparent_55%),linear-gradient(160deg,#020617_0%,#0f172a_45%,#1e1b4b_100%)] shadow-[0_0_48px_rgb(var(--lz-accent)/0.12)]">
      <div ref="el" :class="heightClass || 'h-[34rem] w-full'" />
      <div
        v-if="hoverCard"
        class="pointer-events-none absolute z-10 max-w-[260px] rounded-xl border border-[rgb(var(--lz-accent)/0.4)] bg-slate-950/95 px-3 py-2 shadow-2xl backdrop-blur"
        :style="{ left: `${hoverCard.x}px`, top: `${hoverCard.y}px` }"
      >
        <p class="text-xs font-semibold text-white">{{ hoverCard.name }}</p>
        <p v-if="hoverCard.mastery" class="mt-1 text-[10px] uppercase tracking-wide text-[rgb(var(--lz-accent-bright))]">{{ hoverCard.mastery }}</p>
        <p class="mt-1 text-[11px] leading-4 text-slate-300">{{ hoverCard.summary }}</p>
      </div>
    </div>
  </div>
</template>
