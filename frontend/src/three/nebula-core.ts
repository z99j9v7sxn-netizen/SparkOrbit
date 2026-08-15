import * as THREE from 'three';
import { disposeObject3D } from './dispose';
import { nebulaParticleFragment, nebulaParticleVertex } from './shaders/nebula-particles.glsl';

export interface NebulaCore {
  root: THREE.Group;
  tick: (time: number) => void;
}

function buildDiskParticles(
  count: number,
  radius: number,
  spread: number,
  color: THREE.Color,
  size: number,
  softness: number,
): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const softArr = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const angle = Math.random() * Math.PI * 2;
    const r = radius + (Math.random() - 0.5) * spread;
    const y = (Math.random() - 0.5) * spread * 0.35;
    positions[i * 3] = Math.cos(angle) * r;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = Math.sin(angle) * r;
    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
    sizes[i] = size * (0.6 + Math.random() * 0.8);
    phases[i] = Math.random() * Math.PI * 2;
    softArr[i] = softness;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geo.setAttribute('aSoftness', new THREE.BufferAttribute(softArr, 1));

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

function buildSpiralArm(count: number, radius: number, armOffset: number, color: THREE.Color): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const softArr = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const t = i / count;
    const angle = armOffset + t * Math.PI * 3.5;
    const r = radius * (0.3 + t * 0.9) + (Math.random() - 0.5) * 1.2;
    positions[i * 3] = Math.cos(angle) * r;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 0.8;
    positions[i * 3 + 2] = Math.sin(angle) * r;
    colors[i * 3] = color.r;
    colors[i * 3 + 1] = color.g;
    colors[i * 3 + 2] = color.b;
    sizes[i] = 2.0 + Math.random() * 2.8;
    phases[i] = Math.random() * Math.PI * 2;
    softArr[i] = 0.35;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geo.setAttribute('aSoftness', new THREE.BufferAttribute(softArr, 1));

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

export function buildNebulaCore(colorHex = 0x38bdf8, lowPower = false): NebulaCore {
  const root = new THREE.Group();
  const scale = lowPower ? 0.4 : 1;
  const coreColor = new THREE.Color(colorHex);

  // Zone 1: bright cyan core
  const innerColor = coreColor.clone().lerp(new THREE.Color(0xffffff), 0.18);
  // Zone 2: blue-purple mid ring
  const midColor = coreColor.clone().lerp(new THREE.Color(0x818cf8), 0.4);
  // Zone 3: purple-pink outer arms
  const outerColor = new THREE.Color(0xc084fc).lerp(new THREE.Color(0xec4899), 0.35);

  const coreGlow = new THREE.Mesh(
    new THREE.SphereGeometry(1.0, 32, 32),
    new THREE.MeshBasicMaterial({ color: innerColor, transparent: true, opacity: 0.14 }),
  );
  root.add(coreGlow);

  const midGlow = new THREE.Mesh(
    new THREE.SphereGeometry(2.8, 32, 32),
    new THREE.MeshBasicMaterial({
      color: midColor,
      transparent: true,
      opacity: 0.06,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false,
    }),
  );
  root.add(midGlow);

  root.add(buildDiskParticles(Math.floor(1800 * scale), 1.8, 3.5, innerColor, 3.8, 0.2));
  root.add(buildDiskParticles(Math.floor(1200 * scale), 5, 6, midColor, 3.0, 0.35));
  root.add(buildDiskParticles(Math.floor(800 * scale), 9, 5, outerColor, 2.4, 0.45));

  root.add(buildSpiralArm(Math.floor(650 * scale), 13, 0, outerColor));
  root.add(buildSpiralArm(Math.floor(650 * scale), 13, Math.PI, outerColor));
  root.add(buildSpiralArm(Math.floor(450 * scale), 17, Math.PI * 0.5, midColor));
  root.add(buildSpiralArm(Math.floor(450 * scale), 17, Math.PI * 1.5, midColor));

  const light = new THREE.PointLight(coreColor, 1.8, 70);
  root.add(light);
  const rimLight = new THREE.PointLight(0xec4899, 0.8, 90);
  rimLight.position.set(8, 2, -6);
  root.add(rimLight);

  return {
    root,
    tick(time: number) {
      const t = time * 0.001;
      root.rotation.y = t * 0.06;
      const hueShift = Math.sin(t * 0.15) * 0.08;
      (coreGlow.material as THREE.MeshBasicMaterial).color.copy(innerColor.clone().offsetHSL(hueShift, 0, 0));
      root.traverse((obj) => {
        if (obj instanceof THREE.Points) {
          const mat = obj.material as THREE.ShaderMaterial;
          if (mat.uniforms?.uTime) mat.uniforms.uTime.value = t;
        }
      });
    },
  };
}

export function disposeNebulaCore(core: NebulaCore | null): void {
  if (!core) return;
  disposeObject3D(core.root);
  core.root.parent?.remove(core.root);
}
