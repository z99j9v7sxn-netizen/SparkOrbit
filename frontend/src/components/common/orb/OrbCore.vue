<script lang="ts">
/**
 * OrbCore：Three.js shader 状态球（重型，全站同屏 ≤ 2 个）。
 * 状态通过 GSAP 补间 uniform 平滑过渡；离屏 / 后台自动暂停渲染；
 * prefers-reduced-motion 时降级为静态 CSS 球。
 */
export type OrbState = 'idle' | 'thinking' | 'success' | 'alert' | 'error';
export type OrbPalette = 'cyan' | 'violet' | 'neon';
</script>

<script setup lang="ts">
import * as THREE from 'three';
import gsap from 'gsap';
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue';

const props = withDefaults(
  defineProps<{
    state?: OrbState;
    palette?: OrbPalette;
    size?: number;
    label?: string;
  }>(),
  { state: 'idle', palette: 'cyan', size: 96, label: '' },
);

const PALETTES: Record<OrbPalette, [string, string]> = {
  cyan: ['#38bdf8', '#22d3ee'],
  violet: ['#a78bfa', '#8b5cf6'],
  neon: ['#00ff9d', '#34d399'],
};

/** 语义状态（success/alert/error）会覆盖 palette 颜色 */
const STATE_TARGETS: Record<
  OrbState,
  { speed: number; amp: number; glow: number; colors?: [string, string] }
> = {
  idle: { speed: 0.55, amp: 0.14, glow: 1 },
  thinking: { speed: 2.4, amp: 0.34, glow: 1.4 },
  success: { speed: 0.8, amp: 0.1, glow: 1.2, colors: ['#34d399', '#00ff9d'] },
  alert: { speed: 1.7, amp: 0.26, glow: 1.35, colors: ['#fbbf24', '#fb7185'] },
  error: { speed: 1.2, amp: 0.2, glow: 1.3, colors: ['#fb7185', '#f43f5e'] },
};

const host = ref<HTMLDivElement | null>(null);
const reducedMotion =
  typeof window !== 'undefined' && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

function targetColors(state: OrbState, palette: OrbPalette): [string, string] {
  return STATE_TARGETS[state].colors ?? PALETTES[palette];
}

const staticStyle = computed(() => {
  const [a, b] = targetColors(props.state, props.palette);
  return {
    width: `${props.size}px`,
    height: `${props.size}px`,
    background: `radial-gradient(circle at 32% 30%, ${b}cc, ${a}66 55%, transparent 78%)`,
    boxShadow: `0 0 ${Math.round(props.size / 3)}px ${a}55`,
  };
});

const VERT = /* glsl */ `
uniform float uTime;
uniform float uAmp;
varying vec3 vNormal;
varying vec3 vPos;
float wob(vec3 p, float t) {
  return sin(p.x * 3.1 + t) * sin(p.y * 2.7 + t * 1.3) * sin(p.z * 3.7 + t * 0.7);
}
void main() {
  float d = wob(position, uTime) * 0.6 + wob(position * 2.3, uTime * 1.6) * 0.4;
  vec3 p = position + normal * d * uAmp;
  vNormal = normalize(normalMatrix * normal);
  vec4 mv = modelViewMatrix * vec4(p, 1.0);
  vPos = mv.xyz;
  gl_Position = projectionMatrix * mv;
}
`;

const FRAG = /* glsl */ `
uniform vec3 uColorA;
uniform vec3 uColorB;
uniform float uGlow;
uniform float uTime;
varying vec3 vNormal;
varying vec3 vPos;
void main() {
  vec3 viewDir = normalize(-vPos);
  float fres = pow(1.0 - max(dot(normalize(vNormal), viewDir), 0.0), 1.8);
  float band = 0.5 + 0.5 * sin(uTime * 0.8 + vPos.y * 4.0);
  vec3 col = mix(uColorA, uColorB, clamp(fres * 1.1 + band * 0.25, 0.0, 1.0));
  float alpha = clamp(0.4 + fres * 0.85, 0.0, 1.0);
  gl_FragColor = vec4(col * (0.75 + uGlow * fres), alpha);
}
`;

function makeRadialTexture(inner = 'rgba(255,255,255,0.9)') {
  const c = document.createElement('canvas');
  c.width = c.height = 64;
  const ctx = c.getContext('2d')!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, inner);
  g.addColorStop(0.4, 'rgba(255,255,255,0.35)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 64, 64);
  const tex = new THREE.CanvasTexture(c);
  tex.needsUpdate = true;
  return tex;
}

onMounted(() => {
  if (reducedMotion || !host.value) return;

  const el = host.value;
  const size = props.size;
  const dpr = Math.min(window.devicePixelRatio || 1, 2);

  const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
  renderer.setPixelRatio(dpr);
  renderer.setSize(size, size);
  renderer.domElement.style.display = 'block';
  el.appendChild(renderer.domElement);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 20);
  camera.position.z = 3.4;

  const [a0, b0] = targetColors(props.state, props.palette);
  const uniforms = {
    uTime: { value: 0 },
    uAmp: { value: STATE_TARGETS[props.state].amp },
    uGlow: { value: STATE_TARGETS[props.state].glow },
    uColorA: { value: new THREE.Color(a0) },
    uColorB: { value: new THREE.Color(b0) },
  };

  const sphere = new THREE.Mesh(
    new THREE.IcosahedronGeometry(1, 32),
    new THREE.ShaderMaterial({
      uniforms,
      vertexShader: VERT,
      fragmentShader: FRAG,
      transparent: true,
    }),
  );
  scene.add(sphere);

  const haloTex = makeRadialTexture();
  const haloMat = new THREE.SpriteMaterial({
    map: haloTex,
    color: new THREE.Color(a0),
    transparent: true,
    opacity: 0.3,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const halo = new THREE.Sprite(haloMat);
  halo.scale.setScalar(3.6);
  scene.add(halo);

  const particleCount = 130;
  const positions = new Float32Array(particleCount * 3);
  for (let i = 0; i < particleCount; i++) {
    const r = 1.45 + Math.random() * 0.5;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
    positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta) * 0.55;
    positions[i * 3 + 2] = r * Math.cos(phi);
  }
  const particleGeo = new THREE.BufferGeometry();
  particleGeo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const particleTex = makeRadialTexture('rgba(255,255,255,1)');
  const particleMat = new THREE.PointsMaterial({
    size: 0.05,
    map: particleTex,
    color: new THREE.Color(b0),
    transparent: true,
    opacity: 0.75,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const particles = new THREE.Points(particleGeo, particleMat);
  scene.add(particles);

  const motion = { speed: STATE_TARGETS[props.state].speed };
  const clock = new THREE.Clock();
  let rafId = 0;
  let visible = true;
  let hidden = document.hidden;

  function frame() {
    rafId = 0;
    if (!visible || hidden) return;
    const delta = Math.min(clock.getDelta(), 0.05);
    uniforms.uTime.value += delta * motion.speed;
    sphere.rotation.y += delta * 0.12 * motion.speed;
    particles.rotation.y += delta * 0.25 * motion.speed;
    renderer.render(scene, camera);
    rafId = requestAnimationFrame(frame);
  }

  function resume() {
    if (!rafId && visible && !hidden) {
      clock.getDelta();
      rafId = requestAnimationFrame(frame);
    }
  }

  const io = new IntersectionObserver((entries) => {
    visible = entries[0]?.isIntersecting ?? true;
    resume();
  });
  io.observe(el);

  const onVisibility = () => {
    hidden = document.hidden;
    resume();
  };
  document.addEventListener('visibilitychange', onVisibility);

  const applyState = () => {
    const t = STATE_TARGETS[props.state];
    const [ca, cb] = targetColors(props.state, props.palette);
    const tweenOpts = { duration: 0.9, ease: 'power2.out', overwrite: 'auto' as const };
    gsap.to(motion, { speed: t.speed, ...tweenOpts });
    gsap.to(uniforms.uAmp, { value: t.amp, ...tweenOpts });
    gsap.to(uniforms.uGlow, { value: t.glow, ...tweenOpts });
    const colorA = new THREE.Color(ca);
    const colorB = new THREE.Color(cb);
    gsap.to(uniforms.uColorA.value, { r: colorA.r, g: colorA.g, b: colorA.b, ...tweenOpts });
    gsap.to(uniforms.uColorB.value, { r: colorB.r, g: colorB.g, b: colorB.b, ...tweenOpts });
    gsap.to(haloMat.color, { r: colorA.r, g: colorA.g, b: colorA.b, ...tweenOpts });
    gsap.to(particleMat.color, { r: colorB.r, g: colorB.g, b: colorB.b, ...tweenOpts });
  };

  const stopWatch = watch(() => [props.state, props.palette], applyState);

  resume();

  onBeforeUnmount(() => {
    stopWatch();
    io.disconnect();
    document.removeEventListener('visibilitychange', onVisibility);
    if (rafId) cancelAnimationFrame(rafId);
    gsap.killTweensOf([motion, uniforms.uAmp, uniforms.uGlow, uniforms.uColorA.value, uniforms.uColorB.value, haloMat.color, particleMat.color]);
    sphere.geometry.dispose();
    (sphere.material as THREE.ShaderMaterial).dispose();
    particleGeo.dispose();
    particleMat.dispose();
    haloMat.dispose();
    haloTex.dispose();
    particleTex.dispose();
    renderer.dispose();
    renderer.domElement.remove();
  });
});
</script>

<template>
  <div
    v-if="!reducedMotion"
    ref="host"
    class="orb-core"
    :style="{ width: `${size}px`, height: `${size}px` }"
    role="img"
    :aria-label="label || `状态球：${state}`"
  />
  <div v-else class="orb-core orb-core--static" :style="staticStyle" role="img" :aria-label="label || `状态球：${state}`" />
</template>

<style scoped>
.orb-core {
  position: relative;
  flex-shrink: 0;
  pointer-events: none;
}

.orb-core--static {
  border-radius: 9999px;
}
</style>
