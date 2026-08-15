import { computed, ref } from 'vue';

export type AdminTheme = 'dark' | 'light';

const STORAGE_KEY = 'sparkorbit.admin.theme';

function initialTheme(): AdminTheme {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === 'light' || saved === 'dark') return saved;
  } catch {
    /* localStorage 不可用时跟随系统 */
  }
  if (typeof window !== 'undefined' && window.matchMedia?.('(prefers-color-scheme: light)').matches) {
    return 'light';
  }
  return 'dark';
}

/** 模块级单例：管理端所有组件共享同一主题状态 */
const theme = ref<AdminTheme>(initialTheme());

export function useAdminTheme() {
  const isLight = computed(() => theme.value === 'light');

  function setTheme(next: AdminTheme) {
    theme.value = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      /* 忽略写入失败 */
    }
  }

  function toggleTheme() {
    setTheme(theme.value === 'dark' ? 'light' : 'dark');
  }

  return { theme, isLight, setTheme, toggleTheme };
}
