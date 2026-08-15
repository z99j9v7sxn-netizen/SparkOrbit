<script setup lang="ts">
import * as echarts from 'echarts';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { askKnowledge, explainKnowledge, fetchKnowledgeGraph } from '../../api/zone';
import { LzButton, LzCard, LzInput, LzSkeleton } from './ui';

const chartRef = ref<HTMLDivElement | null>(null);
const selectedSlug = ref('');
const selectedName = ref('');
const summary = ref('');
const tips = ref<string[]>([]);
const question = ref('');
const answer = ref('');
const loadingExplain = ref(false);
const loadingAsk = ref(false);
let chart: echarts.ECharts | null = null;

async function onNodeClick(slug: string, name: string) {
  selectedSlug.value = slug;
  selectedName.value = name;
  loadingExplain.value = true;
  answer.value = '';
  try {
    const data = await explainKnowledge(slug);
    summary.value = data.summary;
    tips.value = data.tips;
  } finally {
    loadingExplain.value = false;
  }
}

async function submitQuestion() {
  if (!selectedSlug.value || !question.value.trim()) return;
  loadingAsk.value = true;
  try {
    const data = await askKnowledge(selectedSlug.value, question.value.trim());
    answer.value = data.answer;
  } finally {
    loadingAsk.value = false;
  }
}

onMounted(async () => {
  const data = await fetchKnowledgeGraph().catch(() => ({ nodes: [], edges: [] }));
  if (!chartRef.value) return;
  chart = echarts.init(chartRef.value);
  const categories = [...new Set(data.nodes.map((n) => n.galaxy))].map((name) => ({ name }));
  const catIndex = Object.fromEntries(categories.map((c, i) => [c.name, i]));
  chart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: [{ data: categories.map((c) => c.name), textStyle: { color: '#94a3b8', fontSize: 11 }, bottom: 0 }],
    series: [{
      type: 'graph',
      layout: 'force',
      roam: true,
      draggable: true,
      label: { show: true, color: '#e2e8f0', fontSize: 12 },
      force: { repulsion: 260, edgeLength: [80, 140], gravity: 0.08 },
      lineStyle: { color: 'rgba(125,211,252,0.45)', width: 2 },
      categories,
      data: data.nodes.map((n) => ({
        id: n.id,
        name: n.name,
        category: catIndex[n.galaxy] ?? 0,
        symbolSize: n.status === 'lit' ? 42 : 28,
        itemStyle: {
          color: n.status === 'lit' ? '#38bdf8' : n.status === 'fading' ? '#fbbf24' : '#64748b',
          shadowBlur: n.status === 'lit' ? 18 : 8,
          shadowColor: 'rgba(56,189,248,0.45)',
        },
      })),
      links: data.edges.map((e) => ({ source: e.source, target: e.target })),
    }],
  });
  chart.on('click', (params) => {
    if (params.dataType === 'node' && params.data && typeof params.data === 'object' && 'id' in params.data) {
      void onNodeClick(String(params.data.id), String(params.name || params.data.id));
    }
  });
});

onBeforeUnmount(() => chart?.dispose());
</script>

<template>
  <div class="dock-panel space-y-3">
    <p class="lz-desc">点击节点查看知识解析，并在下方向教练提问</p>
    <div ref="chartRef" class="h-[22rem] w-full" />
    <LzCard v-if="selectedSlug">
      <p class="lz-subtitle">{{ selectedName }}</p>
      <LzSkeleton v-if="loadingExplain" preset="text" :rows="2" class="mt-2" />
      <p v-else class="lz-body mt-2">{{ summary }}</p>
      <ul v-if="tips.length" class="lz-desc mt-2 list-disc space-y-1 pl-5">
        <li v-for="tip in tips" :key="tip">{{ tip }}</li>
      </ul>
      <div class="mt-4 flex gap-2">
        <LzInput v-model="question" placeholder="针对该知识点提问…" class="flex-1" @enter="submitQuestion" />
        <LzButton variant="soft" class="shrink-0" :loading="loadingAsk" @click="submitQuestion">
          {{ loadingAsk ? '思考中…' : '智能答疑' }}
        </LzButton>
      </div>
      <p v-if="answer" class="lz-card lz-card--flat lz-body mt-3 p-3">{{ answer }}</p>
    </LzCard>
  </div>
</template>
