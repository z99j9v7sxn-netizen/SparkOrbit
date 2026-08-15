<script setup lang="ts">
import gsap from 'gsap';
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue';
import { CLUSTERS, type ZoneAnchor } from '../three/galaxy/cluster-layout';

type ZoneKey = 'chat' | 'learn' | 'study' | 'leisure' | 'domain' | 'treehole' | 'interview';

const props = withDefaults(
  defineProps<{
    /** 星云簇屏幕投影锚点；为 null 时走传统散落布局（降级模式） */
    anchors?: ZoneAnchor[] | null;
  }>(),
  { anchors: null },
);

const emit = defineEmits<{
  (e: 'enter', zone: ZoneKey): void;
  (e: 'hover', zone: ZoneKey | null): void;
}>();

interface ZoneNode {
  key: ZoneKey;
  /** BlueYard 式序号 */
  index: string;
  kicker: string;
  title: string;
  /** 传统布局的散落定位（百分比） */
  x: number;
  y: number;
  delay: number;
}

const ZONE_NODES: ZoneNode[] = [
  { key: 'learn', index: '01', kicker: 'EXPLORATION', title: '学习区', x: 50, y: 49, delay: 0 },
  { key: 'domain', index: '02', kicker: 'IDENTITY', title: '我的星域', x: 50, y: 16, delay: 0.5 },
  { key: 'treehole', index: '03', kicker: 'SANCTUARY', title: '星语树洞', x: 77, y: 28, delay: 1.1 },
  { key: 'chat', index: '04', kicker: 'CONNECTION', title: '聊天区', x: 72, y: 60, delay: 1.4 },
  { key: 'study', index: '05', kicker: 'FOCUS', title: '自习区', x: 20, y: 72, delay: 2.6 },
  { key: 'leisure', index: '06', kicker: 'RECHARGE', title: '休闲区', x: 50, y: 82, delay: 0.8 },
  { key: 'interview', index: '07', kicker: 'AUDITION', title: '模拟面试区', x: 24, y: 30, delay: 1.8 },
];

/** 标签强调色与三维簇色同源，保证 DOM 高亮与簇辉光一致 */
const ZONE_ACCENTS = Object.fromEntries(
  CLUSTERS.map((c) => [c.key, `#${c.color.getHexString()}`]),
) as Record<ZoneKey, string>;

const galaxyMode = computed(() => Boolean(props.anchors));

const stageRef = ref<HTMLDivElement | null>(null);
const parallax = reactive({ x: 0, y: 0 });
const warping = ref(false);
const blackhole = reactive({ x: 0, y: 0, active: false });

function anchorFor(key: ZoneKey): ZoneAnchor | null {
  return props.anchors?.find((a) => a.key === key) ?? null;
}

function isNodeVisible(node: ZoneNode): boolean {
  if (!galaxyMode.value) return true;
  return anchorFor(node.key)?.visible ?? false;
}

function isNodeHovered(node: ZoneNode): boolean {
  if (!galaxyMode.value) return false;
  return anchorFor(node.key)?.hovered ?? false;
}

/** 当前被星云邻近悬停命中的节点（整簇圆圈范围可点击的依据） */
const hoveredNode = computed(() =>
  galaxyMode.value ? (ZONE_NODES.find((n) => isNodeHovered(n)) ?? null) : null,
);

/** 星云模式下点击簇圆圈内任意位置即进入；标签按钮点击冒泡到此处时被 warping 守卫拦下 */
function onStageClick(ev: MouseEvent) {
  if (!galaxyMode.value) return;
  const node = hoveredNode.value;
  if (node) enterZone(node, ev);
}

function onPointerMove(ev: PointerEvent) {
  if (galaxyMode.value) return;
  if (!stageRef.value || warping.value) return;
  const rect = stageRef.value.getBoundingClientRect();
  parallax.x = (ev.clientX - rect.left) / rect.width - 0.5;
  parallax.y = (ev.clientY - rect.top) / rect.height - 0.5;
}

function onNodeEnter(ev: MouseEvent, node: ZoneNode) {
  emit('hover', node.key);
  if (galaxyMode.value) return;
  gsap.to(ev.currentTarget as HTMLElement, { scale: 1.05, duration: 0.4, ease: 'power2.out' });
}

function onNodeLeave(ev: MouseEvent) {
  emit('hover', null);
  if (galaxyMode.value) return;
  gsap.to(ev.currentTarget as HTMLElement, { scale: 1, x: 0, y: 0, duration: 0.6, ease: 'elastic.out(1, 0.3)' });
}

function onNodeMove(ev: MouseEvent) {
  if (galaxyMode.value) return;
  const target = ev.currentTarget as HTMLElement;
  const rect = target.getBoundingClientRect();
  gsap.to(target, {
    x: (ev.clientX - (rect.left + rect.width / 2)) * 0.3,
    y: (ev.clientY - (rect.top + rect.height / 2)) * 0.3,
    duration: 0.4,
    ease: 'power2.out',
  });
}

function nodeStyle(node: ZoneNode) {
  const accent = { '--zone-accent': ZONE_ACCENTS[node.key] };
  const anchor = galaxyMode.value ? anchorFor(node.key) : null;
  if (anchor) {
    // 锚定星云簇投影坐标；depth 越远标签略缩小，营造景深
    // 垂直上移让底部光点落在簇上缘、文字避开簇心最亮区域
    const scale = 1.12 - anchor.depth * 0.22 + (anchor.hovered ? 0.1 : 0);
    return {
      ...accent,
      left: `${anchor.x}px`,
      top: `${anchor.y}px`,
      transform: `translate(-50%, -135%) scale(${scale.toFixed(3)})`,
    };
  }
  const depth = 1 + Math.abs(node.x - 50) / 60;
  const dx = -parallax.x * 20 * depth;
  const dy = -parallax.y * 20 * depth;
  return {
    ...accent,
    left: `${node.x}%`,
    top: `${node.y}%`,
    transform: `translate(-50%, -50%) translate(${dx}px, ${dy}px)`,
    animationDelay: `${node.delay}s`,
  };
}

function enterZone(node: ZoneNode, ev: MouseEvent) {
  if (warping.value) return;
  warping.value = true;

  if (galaxyMode.value) {
    // 星云模式：标签淡出，镜头飞入由父级（StudentPortal → NebulaGalaxy）编排
    gsap.to('.zh-node', { opacity: 0, scale: 0.7, duration: 0.5, ease: 'power2.in' });
    gsap.to('.zh-deco', { opacity: 0, duration: 0.4, ease: 'power1.in' });
    emit('enter', node.key);
    return;
  }

  // 降级模式：保留原黑洞塌缩转场
  const stage = stageRef.value;
  if (!stage) {
    emit('enter', node.key);
    return;
  }
  const rect = stage.getBoundingClientRect();
  blackhole.x = ev.clientX - rect.left;
  blackhole.y = ev.clientY - rect.top;
  blackhole.active = true;

  const tl = gsap.timeline({ onComplete: () => emit('enter', node.key) });
  tl.fromTo(
    '.zh-blackhole',
    { scale: 0, opacity: 0, rotate: 0 },
    { scale: 1, opacity: 1, rotate: 180, duration: 0.55, ease: 'power2.in' },
  );
  tl.to('.zh-blackhole', { scale: 1.6, rotate: 320, duration: 0.35, ease: 'power2.in' }, '-=0.1');
  tl.to('.zh-stage', { scale: 1.12, duration: 0.7, ease: 'power2.in' }, 0);
  tl.to('.zh-node', { opacity: 0, scale: 0.6, duration: 0.4, ease: 'power1.in' }, 0);
}

onMounted(() => {
  window.addEventListener('pointermove', onPointerMove);
});
onBeforeUnmount(() => {
  window.removeEventListener('pointermove', onPointerMove);
});
</script>

<template>
  <div class="absolute inset-0">
    <!-- 无界画框 -->
    <div
      ref="stageRef"
      class="zh-stage absolute inset-0 overflow-hidden"
      :class="{ 'cursor-pointer': hoveredNode }"
      @click="onStageClick"
    >
      <!-- 分区标签：星云模式锚定簇投影，降级模式散落漂浮 -->
      <button
        v-for="node in ZONE_NODES"
        v-show="isNodeVisible(node)"
        :key="node.key"
        class="zh-node absolute z-10 flex flex-col items-center text-center"
        :class="{ 'zh-anchored': galaxyMode, 'zh-active': isNodeHovered(node) }"
        :style="nodeStyle(node)"
        @click="enterZone(node, $event)"
        @mouseenter="onNodeEnter($event, node)"
        @mouseleave="onNodeLeave"
        @mousemove="onNodeMove"
      >
        <span
          class="flex flex-col items-center gap-2.5"
          :class="galaxyMode ? '' : 'zh-float'"
          :style="galaxyMode ? undefined : { animationDelay: `${node.delay}s` }"
        >
          <span class="zh-kicker text-[10px] uppercase tracking-[0.5em] text-slate-400/70 font-light">{{ node.index }} · {{ node.kicker }}</span>
          <span class="zh-title text-xl font-light tracking-widest text-white/90 md:text-2xl">{{ node.title }}</span>
          <span class="zh-dot mt-2" aria-hidden="true"></span>
        </span>
      </button>

      <!-- 点击黑洞塌缩（仅降级模式） -->
      <div
        v-if="blackhole.active"
        class="zh-blackhole pointer-events-none absolute z-20 h-40 w-40 -translate-x-1/2 -translate-y-1/2 rounded-full"
        :style="{ left: `${blackhole.x}px`, top: `${blackhole.y}px` }"
      ></div>

      <!-- 四角 UI 装饰：与 kicker 同排版语言的极简细体小字 -->
      <div class="zh-deco pointer-events-none absolute left-8 top-8 text-[10px] uppercase tracking-[0.5em] text-slate-300/70 font-light">SPARKORBIT · 星轨领航台</div>
      <div class="zh-deco pointer-events-none absolute right-8 top-8 text-[10px] tracking-[0.4em] text-slate-500/60 font-light">✦</div>
      <div class="zh-deco pointer-events-none absolute bottom-8 left-8 text-[10px] tracking-[0.4em] text-slate-500/60 font-light">◐</div>
      <p class="zh-deco pointer-events-none absolute bottom-8 right-8 text-[10px] tracking-[0.4em] text-slate-500/70 font-light">SELECT · A ZONE</p>

    </div>
  </div>
</template>

<style scoped>
.zh-node {
  transition: transform 0.25s cubic-bezier(0.22, 1, 0.36, 1);
}
/* 锚定模式下位置每帧更新，取消 transition 避免拖影 */
.zh-node.zh-anchored {
  transition: none;
}
.zh-float {
  animation: zh-drift 7s ease-in-out infinite;
}
@keyframes zh-drift {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-10px);
  }
}
.zh-kicker,
.zh-title {
  transition: color 0.3s ease, text-shadow 0.3s ease;
}
/* 簇心光点：以簇色柔光融进星云，替代原图标圆片 */
.zh-dot {
  width: 6px;
  height: 6px;
  border-radius: 9999px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.95) 0%, var(--zone-accent) 45%, transparent 78%);
  box-shadow: 0 0 12px 2px color-mix(in srgb, var(--zone-accent) 55%, transparent);
  opacity: 0.75;
  transition: transform 0.3s ease, opacity 0.3s ease, box-shadow 0.3s ease;
}
/* DOM hover 与星云簇邻近悬停（.zh-active）视觉一致：辉光跟随簇色 */
.zh-node:hover .zh-kicker,
.zh-active .zh-kicker {
  color: color-mix(in srgb, var(--zone-accent) 75%, #fff);
}
.zh-node:hover .zh-title,
.zh-active .zh-title {
  color: #fff;
  text-shadow: 0 0 20px color-mix(in srgb, var(--zone-accent) 80%, transparent);
}
.zh-node:hover .zh-dot,
.zh-active .zh-dot {
  opacity: 1;
  transform: scale(1.5);
  box-shadow: 0 0 18px 4px color-mix(in srgb, var(--zone-accent) 70%, transparent);
}
.zh-blackhole {
  background: radial-gradient(circle, #000 0%, #05010f 34%, rgba(56, 189, 248, 0.5) 52%, rgba(168, 85, 247, 0.35) 66%, transparent 78%);
  box-shadow: 0 0 60px 20px rgba(56, 189, 248, 0.35), inset 0 0 40px 10px rgba(0, 0, 0, 0.9);
}
@media (max-width: 768px) {
  .zh-node {
    font-size: 0.9em;
  }
}
</style>
