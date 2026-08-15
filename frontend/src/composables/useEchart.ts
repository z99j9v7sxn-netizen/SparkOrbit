import * as echarts from 'echarts';
import { onBeforeUnmount, type Ref } from 'vue';

/**
 * ECharts 容器管理：容器可见（宽高 > 0）时才 init/setOption，
 * 并用 ResizeObserver 跟随尺寸变化，解决 Tab 切换 / 转场中初始化为 0 宽导致的空白图。
 */
export function useEchart(containerRef: Ref<HTMLDivElement | null>) {
  let chart: echarts.ECharts | null = null;
  let observer: ResizeObserver | null = null;
  let pendingOption: echarts.EChartsCoreOption | null = null;

  function tryRender() {
    const el = containerRef.value;
    if (!el || !pendingOption) return;
    if (el.clientWidth <= 0 || el.clientHeight <= 0) return;
    if (!chart) chart = echarts.init(el);
    chart.setOption(pendingOption);
    chart.resize();
  }

  function ensureObserver() {
    if (observer || !containerRef.value) return;
    observer = new ResizeObserver(() => {
      if (!containerRef.value) return;
      if (chart) {
        chart.resize();
        return;
      }
      tryRender();
    });
    observer.observe(containerRef.value);
  }

  function setOption(option: echarts.EChartsCoreOption) {
    pendingOption = option;
    ensureObserver();
    tryRender();
  }

  function clear() {
    pendingOption = null;
    chart?.clear();
  }

  onBeforeUnmount(() => {
    observer?.disconnect();
    observer = null;
    chart?.dispose();
    chart = null;
  });

  return { setOption, clear };
}
