<script setup lang="ts">
import * as THREE from 'three';
import { onBeforeUnmount, onMounted, ref } from 'vue';
import { createRenderPipeline, disposeRenderPipeline, resizeRenderPipeline, type RenderPipeline } from '../three/create-renderer';
import { buildParticleField, disposeParticleField, type ParticleField } from '../three/particle-field';
import { buildNebulaBackground, disposeNebulaBackground, type NebulaBackground } from '../three/nebula-background';
import { buildNebulaCore, disposeNebulaCore, type NebulaCore } from '../three/nebula-core';

const props = withDefaults(defineProps<{ active?: boolean }>(), { active: true });

const container = ref<HTMLDivElement | null>(null);

let pipeline: RenderPipeline | null = null;
let scene: THREE.Scene;
let camera: THREE.PerspectiveCamera;
let nebulaBg: NebulaBackground | null = null;
let nebulaCore: NebulaCore | null = null;
let particleField: ParticleField | null = null;
let frameId = 0;
let lowPower = false;
let parallax = { x: 0, y: 0 };

function onPointerMove(ev: PointerEvent): void {
  if (!container.value) return;
  const rect = container.value.getBoundingClientRect();
  parallax.x = ((ev.clientX - rect.left) / rect.width - 0.5) * 2 * 0.35;
  parallax.y = -((ev.clientY - rect.top) / rect.height - 0.5) * 2 * 0.25;
}

function animate(): void {
  frameId = requestAnimationFrame(animate);
  if (!props.active || document.hidden || !pipeline) return;
  const now = performance.now();
  nebulaBg?.layers.forEach(({ group, speed }) => { group.rotation.y += speed * 0.6; });
  nebulaBg?.tick(now);
  nebulaCore?.tick(now);
  particleField?.tick(now, parallax);
  if (nebulaCore) nebulaCore.root.rotation.y += 0.0004;
  pipeline.composer.render();
}

function onResize(): void {
  if (!container.value || !pipeline) return;
  resizeRenderPipeline(pipeline, camera, container.value.clientWidth, container.value.clientHeight);
}

onMounted(() => {
  if (!container.value) return;
  scene = new THREE.Scene();
  scene.background = new THREE.Color(0x050818);
  camera = new THREE.PerspectiveCamera(50, container.value.clientWidth / container.value.clientHeight, 0.1, 800);
  camera.position.set(0, 6, 22);
  camera.lookAt(0, 0, 0);

  lowPower = window.devicePixelRatio > 1.5 || container.value.clientWidth < 900;
  pipeline = createRenderPipeline(container.value, scene, camera, { lowPower, enableFilmGrain: !lowPower });
  scene.add(new THREE.AmbientLight(0x445577, 0.35));
  scene.add(new THREE.HemisphereLight(0x6366f1, 0x050818, 0.2));

  nebulaBg = buildNebulaBackground(scene, lowPower);
  particleField = buildParticleField(scene, lowPower);
  nebulaCore = buildNebulaCore(0x38bdf8, lowPower);
  scene.add(nebulaCore.root);

  window.addEventListener('resize', onResize);
  window.addEventListener('pointermove', onPointerMove);
  animate();
});

onBeforeUnmount(() => {
  cancelAnimationFrame(frameId);
  window.removeEventListener('resize', onResize);
  window.removeEventListener('pointermove', onPointerMove);
  disposeNebulaBackground(nebulaBg);
  disposeParticleField(particleField);
  disposeNebulaCore(nebulaCore);
  disposeRenderPipeline(pipeline);
  pipeline = null;
});
</script>

<template>
  <div ref="container" class="absolute inset-0 z-0"></div>
</template>
