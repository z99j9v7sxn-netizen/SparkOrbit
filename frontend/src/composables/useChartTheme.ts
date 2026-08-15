import { computed } from 'vue';
import { useTeacherTheme } from './useTeacherTheme';

export interface ChartTheme {
  /** 坐标轴刻度文字 */
  axisLabel: string;
  /** 分类轴文字（略亮） */
  axisLabelStrong: string;
  /** 分割线 */
  splitLine: string;
  /** 主强调色 */
  accent: string;
  /** 强调色柔和填充（面积/渐变起点） */
  accentSoft: string;
  /** 次强调色 */
  accent2: string;
  /** 系列色板 */
  palette: string[];
  /** 提示框 */
  tooltip: { backgroundColor: string; borderColor: string; textColor: string };
}

const DARK: ChartTheme = {
  axisLabel: '#94a3b8',
  axisLabelStrong: '#cbd5e1',
  splitLine: 'rgba(148, 163, 184, 0.14)',
  accent: '#7dd3fc',
  accentSoft: 'rgba(125, 211, 252, 0.25)',
  accent2: '#a78bfa',
  palette: ['#38bdf8', '#a78bfa', '#f59e0b', '#34d399', '#fb7185', '#22d3ee'],
  tooltip: {
    backgroundColor: 'rgba(8, 13, 32, 0.92)',
    borderColor: 'rgba(148, 197, 255, 0.2)',
    textColor: '#e0f2fe',
  },
};

const LIGHT: ChartTheme = {
  axisLabel: '#64748b',
  axisLabelStrong: '#334155',
  splitLine: 'rgba(100, 116, 139, 0.16)',
  accent: '#0284c7',
  accentSoft: 'rgba(2, 132, 199, 0.16)',
  accent2: '#7c3aed',
  palette: ['#0284c7', '#7c3aed', '#d97706', '#059669', '#e11d48', '#0891b2'],
  tooltip: {
    backgroundColor: 'rgba(255, 255, 255, 0.96)',
    borderColor: 'rgba(15, 23, 42, 0.1)',
    textColor: '#0f172a',
  },
};

/**
 * ECharts 双主题配色。页面在 watch(chart, ...) 中重调 setOption 即可跟随主题切换。
 */
export function useChartTheme() {
  const { theme } = useTeacherTheme();
  const chart = computed<ChartTheme>(() => (theme.value === 'light' ? LIGHT : DARK));
  return { theme, chart };
}
