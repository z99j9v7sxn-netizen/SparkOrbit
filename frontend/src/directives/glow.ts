import type { Directive } from 'vue';

interface GlowOptions {
  tilt?: boolean;
}

interface GlowElement extends HTMLElement {
  __glowCleanup?: () => void;
}

const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

/**
 * v-glow：hover 时卡片内高光跟随光标（写入 --gx/--gy CSS 变量），
 * 可选 { tilt: true } 增加轻微 3D 倾斜。样式见 style.css 的 .glass-card--reactive。
 */
export const glow: Directive<GlowElement, GlowOptions | undefined> = {
  mounted(el, binding) {
    el.classList.add('glass-card--reactive');
    if (reducedMotion) return;

    const tilt = binding.value?.tilt === true;

    const onMove = (e: PointerEvent) => {
      const rect = el.getBoundingClientRect();
      if (!rect.width || !rect.height) return;
      const x = (e.clientX - rect.left) / rect.width;
      const y = (e.clientY - rect.top) / rect.height;
      el.style.setProperty('--gx', `${(x * 100).toFixed(1)}%`);
      el.style.setProperty('--gy', `${(y * 100).toFixed(1)}%`);
      if (tilt) {
        el.style.setProperty('--tilt-x', `${((y - 0.5) * -2.4).toFixed(2)}deg`);
        el.style.setProperty('--tilt-y', `${((x - 0.5) * 2.4).toFixed(2)}deg`);
      }
    };

    const onLeave = () => {
      el.style.removeProperty('--gx');
      el.style.removeProperty('--gy');
      el.style.setProperty('--tilt-x', '0deg');
      el.style.setProperty('--tilt-y', '0deg');
    };

    el.addEventListener('pointermove', onMove, { passive: true });
    el.addEventListener('pointerleave', onLeave, { passive: true });
    el.__glowCleanup = () => {
      el.removeEventListener('pointermove', onMove);
      el.removeEventListener('pointerleave', onLeave);
    };
  },
  unmounted(el) {
    el.__glowCleanup?.();
    delete el.__glowCleanup;
  },
};
