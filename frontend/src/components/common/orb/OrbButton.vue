<script setup lang="ts">
import { computed } from 'vue';

/** OrbButton：带辉光环的圆形按钮，hover 时光环加速旋转。 */
const props = withDefaults(
  defineProps<{
    palette?: 'cyan' | 'violet' | 'neon';
    size?: number;
    ariaLabel?: string;
  }>(),
  { palette: 'cyan', size: 40, ariaLabel: '' },
);

const COLORS: Record<string, [string, string]> = {
  cyan: ['#38bdf8', '#22d3ee'],
  violet: ['#a78bfa', '#8b5cf6'],
  neon: ['#00ff9d', '#34d399'],
};

const style = computed(() => {
  const [a, b] = COLORS[props.palette] ?? COLORS.cyan;
  return {
    width: `${props.size}px`,
    height: `${props.size}px`,
    '--orb-a': a,
    '--orb-b': b,
  };
});
</script>

<template>
  <button type="button" class="orb-btn press-fx" :style="style" :aria-label="ariaLabel || undefined">
    <span class="orb-btn__ring" aria-hidden="true" />
    <span class="orb-btn__inner">
      <slot />
    </span>
  </button>
</template>

<style scoped>
.orb-btn {
  position: relative;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  border-radius: 9999px;
  border: none;
  padding: 0;
  background: transparent;
  cursor: pointer;
}

.orb-btn__ring {
  position: absolute;
  inset: 0;
  border-radius: 9999px;
  background: conic-gradient(from 0deg, var(--orb-a), transparent 35%, var(--orb-b) 60%, transparent 85%, var(--orb-a));
  animation: orb-btn-spin 9s linear infinite;
  opacity: 0.65;
  -webkit-mask: radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 1.5px));
  mask: radial-gradient(farthest-side, transparent calc(100% - 2px), #000 calc(100% - 1.5px));
  transition: opacity 0.2s ease;
}

.orb-btn:hover .orb-btn__ring {
  animation-duration: 2.4s;
  opacity: 1;
}

.orb-btn__inner {
  position: absolute;
  inset: 3px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 9999px;
  background: rgba(8, 12, 28, 0.75);
  color: color-mix(in srgb, var(--orb-a) 80%, white);
  font-size: 0.8rem;
  transition: background 0.2s ease, box-shadow 0.2s ease;
}

.orb-btn:hover .orb-btn__inner {
  background: rgba(8, 12, 28, 0.55);
  box-shadow: 0 0 18px color-mix(in srgb, var(--orb-a) 45%, transparent);
}

@keyframes orb-btn-spin {
  to {
    transform: rotate(360deg);
  }
}

@media (prefers-reduced-motion: reduce) {
  .orb-btn__ring {
    animation: none;
  }
}
</style>
