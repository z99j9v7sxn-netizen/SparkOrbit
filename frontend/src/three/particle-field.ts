import * as THREE from 'three';
import { particleFieldFragment, particleFieldVertex } from './shaders/particle-field.glsl';

const PALETTE = [
  new THREE.Color(0x38bdf8),
  new THREE.Color(0x6366f1),
  new THREE.Color(0xa78bfa),
  new THREE.Color(0xf472b6),
  new THREE.Color(0x7dd3fc),
  new THREE.Color(0x818cf8),
];

export interface ParticleField {
  root: THREE.Group;
  tick: (time: number, pointer?: { x: number; y: number }) => void;
}

interface LayerSpec {
  count: number;
  radiusMin: number;
  radiusMax: number;
  parallax: number;
  sizeScale: number;
}

function sampleShellPosition(radiusMin: number, radiusMax: number): THREE.Vector3 {
  const u = Math.random();
  const v = Math.random();
  const theta = 2 * Math.PI * u;
  const phi = Math.acos(2 * v - 1);
  const r = radiusMin + Math.random() * (radiusMax - radiusMin);
  return new THREE.Vector3(
    r * Math.sin(phi) * Math.cos(theta),
    r * Math.sin(phi) * Math.sin(theta) * 0.65,
    r * Math.cos(phi),
  );
}

function buildLayer(spec: LayerSpec, lowPower: boolean): THREE.Points {
  const count = lowPower ? Math.floor(spec.count * 0.55) : spec.count;
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);
  const phases = new Float32Array(count);
  const depths = new Float32Array(count);

  for (let i = 0; i < count; i++) {
    const pos = sampleShellPosition(spec.radiusMin, spec.radiusMax);
    positions[i * 3] = pos.x;
    positions[i * 3 + 1] = pos.y;
    positions[i * 3 + 2] = pos.z;

    const c = PALETTE[Math.floor(Math.random() * PALETTE.length)];
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;

    sizes[i] = (1.0 + Math.random() * 2.6) * spec.sizeScale;
    phases[i] = Math.random() * Math.PI * 2;
    depths[i] = spec.parallax * (0.4 + Math.random() * 0.6);
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geo.setAttribute('aDepth', new THREE.BufferAttribute(depths, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: { value: 0 },
      uPointer: { value: new THREE.Vector2(0, 0) },
      uPixelRatio: { value: Math.min(window.devicePixelRatio, 2) },
    },
    vertexShader: particleFieldVertex,
    fragmentShader: particleFieldFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexColors: true,
  });

  const points = new THREE.Points(geo, mat);
  points.frustumCulled = false;
  points.userData.parallax = spec.parallax;
  return points;
}

export function buildParticleField(scene: THREE.Scene, lowPower = false): ParticleField {
  const root = new THREE.Group();
  const layers: THREE.Points[] = [
    buildLayer({ count: 2000, radiusMin: 90, radiusMax: 130, parallax: 0.15, sizeScale: 0.75 }, lowPower),
    buildLayer({ count: 2200, radiusMin: 130, radiusMax: 170, parallax: 0.45, sizeScale: 0.9 }, lowPower),
    buildLayer({ count: 1500, radiusMin: 170, radiusMax: 210, parallax: 0.85, sizeScale: 1.05 }, lowPower),
  ];
  layers.forEach((layer) => root.add(layer));
  scene.add(root);

  return {
    root,
    tick(time: number, pointer = { x: 0, y: 0 }) {
      const t = time * 0.001;
      layers.forEach((layer) => {
        const mat = layer.material as THREE.ShaderMaterial;
        mat.uniforms.uTime.value = t;
        const p = layer.userData.parallax as number;
        mat.uniforms.uPointer.value.set(pointer.x * p, pointer.y * p);
      });
    },
  };
}

export function disposeParticleField(field: ParticleField | null): void {
  if (!field) return;
  field.root.parent?.remove(field.root);
  field.root.traverse((obj) => {
    if (obj instanceof THREE.Points) {
      obj.geometry.dispose();
      (obj.material as THREE.Material).dispose();
    }
  });
}
