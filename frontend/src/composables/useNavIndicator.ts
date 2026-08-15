import gsap from 'gsap';
import { nextTick, onBeforeUnmount, onMounted, watch, type Ref } from 'vue';
import { useRoute } from 'vue-router';

/**
 * 侧边栏共享滑动指示条：路由变化时，一个指示条在 .console-nav-item 之间
 * GSAP 滑动跟随（FLIP 式），替代每项各自的静态指示条。
 */
export function useNavIndicator(
  navRef: Ref<HTMLElement | null>,
  indicatorRef: Ref<HTMLElement | null>,
) {
  const route = useRoute();
  const reducedMotion =
    typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let first = true;

  async function sync() {
    await nextTick();
    const nav = navRef.value;
    const indicator = indicatorRef.value;
    if (!nav || !indicator) return;

    const active = nav.querySelector<HTMLElement>('.console-nav-item.is-active');
    if (!active) {
      gsap.set(indicator, { autoAlpha: 0 });
      return;
    }

    nav.classList.add('has-nav-indicator');
    const top = active.offsetTop + active.offsetHeight * 0.2;
    const height = active.offsetHeight * 0.6;

    if (first || reducedMotion) {
      gsap.set(indicator, { top, height, autoAlpha: 1 });
      first = false;
      return;
    }
    gsap.to(indicator, {
      top,
      height,
      autoAlpha: 1,
      duration: 0.45,
      ease: 'power3.out',
      overwrite: 'auto',
    });
  }

  onMounted(sync);
  const stop = watch(() => route.path, sync);
  onBeforeUnmount(() => {
    stop();
    if (indicatorRef.value) gsap.killTweensOf(indicatorRef.value);
  });
}
