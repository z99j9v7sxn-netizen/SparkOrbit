<script setup lang="ts">
import * as echarts from 'echarts';
import { onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    type: 'bar' | 'line' | 'pie';
    data: number[] | { name: string; value: number }[];
    labels?: string[];
    height?: string;
    color?: string;
  }>(),
  {
    height: '48px',
    color: '#7dd3fc',
  },
);

const chartRef = ref<HTMLDivElement | null>(null);
let chart: echarts.ECharts | null = null;
let resizeObserver: ResizeObserver | null = null;

const darkTheme = {
  backgroundColor: 'transparent',
  textStyle: { color: '#94a3b8', fontSize: 9 },
};

function buildOption(): echarts.EChartsOption {
  const color = props.color;

  if (props.type === 'pie') {
    const pieData = Array.isArray(props.data) && typeof props.data[0] === 'number'
      ? [{ name: '进度', value: props.data[0] as number }, { name: '剩余', value: 100 - (props.data[0] as number) }]
      : (props.data as { name: string; value: number }[]);
    return {
      ...darkTheme,
      series: [{
        type: 'pie',
        radius: ['55%', '80%'],
        center: ['50%', '50%'],
        silent: true,
        label: { show: false },
        data: pieData,
        itemStyle: {
          borderRadius: 2,
          borderColor: 'transparent',
        },
        color: [color, 'rgba(148,163,184,0.15)'],
      }],
    };
  }

  const values = props.data as number[];
  const labels = props.labels ?? values.map((_, i) => `${i + 1}`);

  if (props.type === 'bar') {
    return {
      ...darkTheme,
      grid: { left: 4, right: 4, top: 4, bottom: 4 },
      xAxis: {
        type: 'category',
        data: labels,
        show: false,
      },
      yAxis: { type: 'value', show: false },
      series: [{
        type: 'bar',
        data: values,
        barWidth: '60%',
        itemStyle: {
          color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
            { offset: 0, color },
            { offset: 1, color: `${color}44` },
          ]),
          borderRadius: [2, 2, 0, 0],
        },
      }],
    };
  }

  return {
    ...darkTheme,
    grid: { left: 4, right: 4, top: 6, bottom: 4 },
    xAxis: {
      type: 'category',
      data: labels,
      show: false,
      boundaryGap: false,
    },
    yAxis: { type: 'value', show: false, min: 0, max: 100 },
    series: [{
      type: 'line',
      data: values,
      smooth: true,
      symbol: 'none',
      lineStyle: { color, width: 2 },
      areaStyle: {
        color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
          { offset: 0, color: `${color}55` },
          { offset: 1, color: 'transparent' },
        ]),
      },
    }],
  };
}

function renderChart() {
  if (!chart) return;
  chart.setOption(buildOption(), true);
}

onMounted(() => {
  if (!chartRef.value) return;
  chart = echarts.init(chartRef.value, undefined, { renderer: 'canvas' });
  renderChart();
  resizeObserver = new ResizeObserver(() => chart?.resize());
  resizeObserver.observe(chartRef.value);
});

watch(() => [props.data, props.labels, props.type, props.color], renderChart, { deep: true });

onBeforeUnmount(() => {
  resizeObserver?.disconnect();
  chart?.dispose();
  chart = null;
});
</script>

<template>
  <div ref="chartRef" class="w-full" :style="{ height }" />
</template>
