import * as THREE from 'three';
import { disposeObject3D } from './dispose';
import { nebulaParticleFragment, nebulaParticleVertex } from './shaders/nebula-particles.glsl';
import type { ParallaxLayer, ParallaxStarfield } from './parallax-starfield';
import { SKY_BAND_NORMAL } from './sky-dome';

const PALETTE = [0x0ea5e9, 0x38bdf8, 0x6366f1, 0x818cf8, 0xc084fc, 0xec4899, 0xf472b6, 0xa78bfa];
const COLOR_BAND = [0x0ea5e9, 0x6366f1, 0xc084fc, 0xec4899];

function randomSpherePoint(rMin: number, rMax: number): THREE.Vector3 {
  const r = rMin + Math.random() * (rMax - rMin);
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  return new THREE.Vector3(
    r * Math.sin(phi) * Math.cos(theta),
    r * Math.sin(phi) * Math.sin(theta),
    r * Math.cos(phi),
  );
}

function buildShaderPoints(
  count: number,
  positions: Float32Array,
  colors: Float32Array,
  sizes: Float32Array,
  phases: Float32Array,
  softness: Float32Array,
): THREE.Points {
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geo.setAttribute('aSoftness', new THREE.BufferAttribute(softness, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    },
    vertexShader: nebulaParticleVertex,
    fragmentShader: nebulaParticleFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexColors: true,
  });

  return new THREE.Points(geo, mat);
}

function buildBokehLayer(count: number, rMin: number, rMax: number, sizeMin: number, sizeMax: number, soft = 0.2): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const softness = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const p = randomSpherePoint(rMin, rMax);
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
    const c = new THREE.Color(PALETTE[Math.floor(Math.random() * PALETTE.length)]);
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
    sizes[i] = sizeMin + Math.random() * (sizeMax - sizeMin);
    phases[i] = Math.random() * Math.PI * 2;
    softness[i] = soft;
  }

  return buildShaderPoints(count, positions, colors, sizes, phases, softness);
}

/** Large soft cloud particles for nebula volume */
function buildNebulaCloudLayer(count: number, rMin: number, rMax: number): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const softness = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const p = randomSpherePoint(rMin, rMax);
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y * 0.6;
    positions[i * 3 + 2] = p.z;
    const bandIdx = Math.floor((i / count) * COLOR_BAND.length) % COLOR_BAND.length;
    const c = new THREE.Color(COLOR_BAND[bandIdx]);
    c.lerp(new THREE.Color(PALETTE[Math.floor(Math.random() * PALETTE.length)]), 0.35);
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
    sizes[i] = 8 + Math.random() * 14;
    phases[i] = Math.random() * Math.PI * 2;
    softness[i] = 0.85;
  }

  return buildShaderPoints(count, positions, colors, sizes, phases, softness);
}

/** Blue→purple→pink color band along galactic plane */
function buildColorBandLayer(count: number): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const softness = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const r = 60 + Math.random() * 180;
    positions[i * 3] = Math.cos(angle) * r;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 25;
    positions[i * 3 + 2] = Math.sin(angle) * r;

    const t = (Math.sin(angle) + 1) * 0.5;
    const c1 = new THREE.Color(COLOR_BAND[0]);
    const c2 = new THREE.Color(COLOR_BAND[2]);
    const c3 = new THREE.Color(COLOR_BAND[3]);
    const c = t < 0.5 ? c1.clone().lerp(c2, t * 2) : c2.clone().lerp(c3, (t - 0.5) * 2);
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
    sizes[i] = 3.5 + Math.random() * 6;
    phases[i] = Math.random() * Math.PI * 2;
    softness[i] = 0.55;
  }

  return buildShaderPoints(count, positions, colors, sizes, phases, softness);
}

/** 光谱色近似：蓝白（O/B 型）居多，暖白与橙（G/K 型）点缀 */
const SPECTRAL_COLORS = [0xb8ccff, 0xb8ccff, 0xdde6ff, 0xfff2dd, 0xfff2dd, 0xffcf9e];

function buildFarStars(count: number): THREE.Points {
  const positions = new Float32Array(count * 3);
  const starColors = new Float32Array(count * 3);
  // 银河带正交基：60% 星星沿带高斯偏置（银河带处星星密集，结构感来自密度而非亮度）
  const n = SKY_BAND_NORMAL.clone();
  const t1 = new THREE.Vector3(0, 0, 1).cross(n).normalize();
  const t2 = n.clone().cross(t1);
  const gauss = () => (Math.random() + Math.random() + Math.random() + Math.random() - 2) / 2;
  const dir = new THREE.Vector3();
  for (let i = 0; i < count; i++) {
    let p: THREE.Vector3;
    if (i < count * 0.6) {
      const phi = Math.random() * Math.PI * 2;
      dir
        .copy(t1)
        .multiplyScalar(Math.cos(phi))
        .addScaledVector(t2, Math.sin(phi))
        .addScaledVector(n, gauss() * 0.22)
        .normalize();
      p = dir.clone().multiplyScalar(180 + Math.random() * 240);
    } else {
      p = randomSpherePoint(180, 420);
    }
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
    const tint = new THREE.Color(SPECTRAL_COLORS[Math.floor(Math.random() * SPECTRAL_COLORS.length)])
      .lerp(new THREE.Color(0xffffff), Math.random() * 0.35);
    starColors[i * 3] = tint.r;
    starColors[i * 3 + 1] = tint.g;
    starColors[i * 3 + 2] = tint.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(starColors, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.4,
    vertexColors: true,
    transparent: true,
    opacity: 0.65,
    sizeAttenuation: true,
  });
  return new THREE.Points(geo, mat);
}

export interface NebulaBackground extends ParallaxStarfield {
  tick: (time: number) => void;
}

export function buildNebulaBackground(scene: THREE.Scene, lowPower = false): NebulaBackground {
  const root = new THREE.Group();
  scene.add(root);
  const layers: ParallaxLayer[] = [];
  const scale = lowPower ? 0.35 : 1;

  // 天空穹（sky-dome）已提供银河带与星云结构，这里的体积云/远星适当减量，把粒子预算让给星系
  const cloudGroup = new THREE.Group();
  cloudGroup.add(buildNebulaCloudLayer(Math.floor(120 * scale), 50, 280));
  root.add(cloudGroup);
  layers.push({ group: cloudGroup, speed: 0.00015 });

  const bandGroup = new THREE.Group();
  bandGroup.add(buildColorBandLayer(Math.floor(500 * scale)));
  root.add(bandGroup);
  layers.push({ group: bandGroup, speed: 0.00035 });

  const farGroup = new THREE.Group();
  farGroup.add(buildFarStars(Math.floor(1200 * scale)));
  root.add(farGroup);
  // 远星层转速调到接近静止：带内密集星要与天空穹的银河带保持对齐
  layers.push({ group: farGroup, speed: 0.00004 });

  const midGroup = new THREE.Group();
  midGroup.add(buildBokehLayer(Math.floor(800 * scale), 80, 200, 2.0, 5.0, 0.25));
  root.add(midGroup);
  layers.push({ group: midGroup, speed: 0.0009 });

  const nearGroup = new THREE.Group();
  nearGroup.add(buildBokehLayer(Math.floor(400 * scale), 35, 90, 2.8, 6.5, 0.15));
  root.add(nearGroup);
  layers.push({ group: nearGroup, speed: 0.0028 });

  return {
    root,
    layers,
    tick(time: number) {
      const t = time * 0.001;
      cloudGroup.rotation.y = t * 0.012;
      bandGroup.rotation.y = t * 0.008;
      root.traverse((obj) => {
        if (obj instanceof THREE.Points) {
          const mat = obj.material as THREE.ShaderMaterial | THREE.PointsMaterial;
          if ('uniforms' in mat && mat.uniforms?.uTime) {
            mat.uniforms.uTime.value = t;
          }
        }
      });
    },
  };
}

export function disposeNebulaBackground(field: NebulaBackground | null): void {
  if (!field) return;
  disposeObject3D(field.root);
  field.root.parent?.remove(field.root);
}
