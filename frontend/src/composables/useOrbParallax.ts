import gsap from 'gsap';
import { onBeforeUnmount, onMounted, type Ref } from 'vue';

/**
 * 背景光球鼠标视差：让布局层内的 .console-orb 以不同深度系数缓动跟随光标。
 * 漂移动画使用 CSS translate/scale 独立属性，与 GSAP 的 transform 视差互不冲突。
 */
export function useOrbParallax(rootRef: Ref<HTMLElement | null>) {
  onMounted(() => {
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) return;
    const root = rootRef.value;
    if (!root) return;

    const orbs = Array.from(root.querySelectorAll<HTMLElement>('.console-orb'));
    if (!orbs.length) return;

    const depths = [0.045, 0.03, 0.06];
    const movers = orbs.map((el, i) => ({
      x: gsap.quickTo(el, 'x', { duration: 1.4, ease: 'power3.out' }),
      y: gsap.quickTo(el, 'y', { duration: 1.4, ease: 'power3.out' }),
      depth: depths[i % depths.length],
    }));

    const onMove = (e: PointerEvent) => {
      const dx = e.clientX - window.innerWidth / 2;
      const dy = e.clientY - window.innerHeight / 2;
      for (const m of movers) {
        m.x(dx * m.depth);
        m.y(dy * m.depth);
      }
    };

    window.addEventListener('pointermove', onMove, { passive: true });

    onBeforeUnmount(() => {
      window.removeEventListener('pointermove', onMove);
      for (const el of orbs) gsap.killTweensOf(el);
    });
  });
}
