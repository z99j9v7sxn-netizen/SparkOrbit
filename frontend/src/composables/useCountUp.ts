import { ref, watch, type Ref } from 'vue';

/** KPI 数字滚动动画：值变化时从旧值补间到新值 */
export function useCountUp(source: Ref<number | null | undefined>, duration = 600): Ref<number> {
  const display = ref(0);
  let rafId = 0;

  const reduceMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  watch(
    source,
    (next) => {
      const target = typeof next === 'number' && Number.isFinite(next) ? next : 0;
      cancelAnimationFrame(rafId);
      if (reduceMotion || duration <= 0) {
        display.value = target;
        return;
      }
      const from = display.value;
      const start = performance.now();
      const step = (now: number) => {
        const t = Math.min(1, (now - start) / duration);
        const eased = 1 - Math.pow(1 - t, 3);
        display.value = Math.round(from + (target - from) * eased);
        if (t < 1) rafId = requestAnimationFrame(step);
      };
      rafId = requestAnimationFrame(step);
    },
    { immediate: true },
  );

  return display;
}
