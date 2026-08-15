import * as THREE from 'three';
import { GPUComputationRenderer, type Variable } from 'three/examples/jsm/misc/GPUComputationRenderer.js';
import { generateParticleData } from '../galaxy/cluster-layout';
import { nebulaPositionShader, nebulaVelocityShader } from './shaders/nebula-sim.glsl';
import { nebulaRenderFragment, nebulaRenderVertex } from './shaders/nebula-render.glsl';

export interface NebulaSimulation {
  points: THREE.Points;
  /** 直接暴露 uniform 引用，供 GSAP 补间 { value } */
  formation: THREE.IUniform<number>;
  warp: THREE.IUniform<number>;
  warpDir: THREE.IUniform<THREE.Vector3>;
  globalFade: THREE.IUniform<number>;
  pointerStrength: THREE.IUniform<number>;
  swirl: THREE.IUniform<number>;
  flow: THREE.IUniform<number>;
  setPointer: (world: THREE.Vector3) => void;
  setHoverCluster: (id: number) => void;
  update: (nowMs: number) => void;
  dispose: () => void;
}

/**
 * 创建 GPGPU 星云模拟。textureSize² = 粒子总数。
 * 初始化失败（浮点纹理不可用等）返回 null，由调用方走降级链。
 */
export function createNebulaSimulation(
  renderer: THREE.WebGLRenderer,
  textureSize: number,
): NebulaSimulation | null {
  let gpu: GPUComputationRenderer;
  try {
    gpu = new GPUComputationRenderer(textureSize, textureSize, renderer);
  } catch {
    return null;
  }

  const count = textureSize * textureSize;
  const data = generateParticleData(count);

  const posTex = gpu.createTexture();
  const velTex = gpu.createTexture();
  (posTex.image.data as Float32Array).set(data.scatter);
  // 速度初始为 0（createTexture 已清零）

  const homeTex = new THREE.DataTexture(data.home, textureSize, textureSize, THREE.RGBAFormat, THREE.FloatType);
  homeTex.needsUpdate = true;

  const velVar: Variable = gpu.addVariable('textureVelocity', nebulaVelocityShader, velTex);
  const posVar: Variable = gpu.addVariable('texturePosition', nebulaPositionShader, posTex);
  gpu.setVariableDependencies(velVar, [velVar, posVar]);
  gpu.setVariableDependencies(posVar, [velVar, posVar]);

  const formation: THREE.IUniform<number> = { value: 0 };
  const warp: THREE.IUniform<number> = { value: 0 };
  const warpDir: THREE.IUniform<THREE.Vector3> = { value: new THREE.Vector3(0, 0, 1) };
  const pointerStrength: THREE.IUniform<number> = { value: 0 };
  const swirl: THREE.IUniform<number> = { value: 0.55 };
  const flow: THREE.IUniform<number> = { value: 1.35 };
  const pointerUniform: THREE.IUniform<THREE.Vector3> = { value: new THREE.Vector3(0, 0, 0) };
  const hoverUniform: THREE.IUniform<number> = { value: -1 };

  Object.assign(velVar.material.uniforms, {
    uTime: { value: 0 },
    uDelta: { value: 0.016 },
    uHome: { value: homeTex },
    uFormation: formation,
    uSwirl: swirl,
    uFlow: flow,
    uPointer: pointerUniform,
    uPointerStrength: pointerStrength,
    uHoverCluster: hoverUniform,
    uWarp: warp,
    uWarpDir: warpDir,
  });
  Object.assign(posVar.material.uniforms, {
    uDelta: { value: 0.016 },
  });

  const initError = gpu.init();
  if (initError !== null) {
    gpu.dispose();
    homeTex.dispose();
    return null;
  }

  // 渲染几何：position 属性仅占位，真实位置来自 FBO 纹理
  const geo = new THREE.BufferGeometry();
  const placeholder = new Float32Array(count * 3);
  const uvs = new Float32Array(count * 2);
  for (let i = 0; i < count; i++) {
    uvs[i * 2] = ((i % textureSize) + 0.5) / textureSize;
    uvs[i * 2 + 1] = (Math.floor(i / textureSize) + 0.5) / textureSize;
  }
  geo.setAttribute('position', new THREE.BufferAttribute(placeholder, 3));
  geo.setAttribute('aUv', new THREE.BufferAttribute(uvs, 2));
  geo.setAttribute('aColor', new THREE.BufferAttribute(data.color, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(data.size, 1));
  geo.setAttribute('aCluster', new THREE.BufferAttribute(data.clusterId, 1));
  geo.setAttribute('aSoftness', new THREE.BufferAttribute(data.softness, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(data.phase, 1));

  const globalFade: THREE.IUniform<number> = { value: 0 };
  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uPositions: { value: gpu.getCurrentRenderTarget(posVar).texture },
      uVelocities: { value: gpu.getCurrentRenderTarget(velVar).texture },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
      uTime: { value: 0 },
      uHoverCluster: hoverUniform,
      uGlobalFade: globalFade,
    },
    vertexShader: nebulaRenderVertex,
    fragmentShader: nebulaRenderFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;

  let lastMs = 0;

  return {
    points,
    formation,
    warp,
    warpDir,
    globalFade,
    pointerStrength,
    swirl,
    flow,
    setPointer(world: THREE.Vector3) {
      pointerUniform.value.copy(world);
    },
    setHoverCluster(id: number) {
      hoverUniform.value = id;
    },
    update(nowMs: number) {
      if (lastMs === 0) lastMs = nowMs;
      // 卡顿/切后台恢复时钳制步长，避免积分爆炸
      const dt = Math.min((nowMs - lastMs) / 1000, 1 / 30);
      lastMs = nowMs;
      const t = nowMs * 0.001;

      velVar.material.uniforms.uTime.value = t;
      velVar.material.uniforms.uDelta.value = dt;
      posVar.material.uniforms.uDelta.value = dt;
      gpu.compute();

      mat.uniforms.uPositions.value = gpu.getCurrentRenderTarget(posVar).texture;
      mat.uniforms.uVelocities.value = gpu.getCurrentRenderTarget(velVar).texture;
      mat.uniforms.uTime.value = t;
    },
    dispose() {
      points.parent?.remove(points);
      geo.dispose();
      mat.dispose();
      homeTex.dispose();
      gpu.dispose();
    },
  };
}
