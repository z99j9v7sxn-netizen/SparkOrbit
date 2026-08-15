import * as THREE from 'three';
import { disposeObject3D } from './dispose';

export interface ParallaxLayer {
  group: THREE.Group;
  speed: number;
}

export interface ParallaxStarfield {
  root: THREE.Group;
  layers: ParallaxLayer[];
}

const dummy = new THREE.Object3D();

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

function buildInstancedLayer(
  count: number,
  rMin: number,
  rMax: number,
  sizeMin: number,
  sizeMax: number,
  palette: number[],
  emissiveIntensity: number,
  blending?: THREE.Blending,
): THREE.InstancedMesh {
  const geo = new THREE.SphereGeometry(1, 8, 8);
  const mat = new THREE.MeshStandardMaterial({
    color: 0xffffff,
    emissive: 0xffffff,
    emissiveIntensity,
    roughness: 0.4,
    metalness: 0.1,
    transparent: true,
    opacity: 0.85,
    ...(blending !== undefined ? { blending, depthWrite: false } : {}),
  });
  const mesh = new THREE.InstancedMesh(geo, mat, count);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);

  for (let i = 0; i < count; i++) {
    const pos = randomSpherePoint(rMin, rMax);
    const scale = sizeMin + Math.random() * (sizeMax - sizeMin);
    dummy.position.copy(pos);
    dummy.scale.setScalar(scale);
    dummy.updateMatrix();
    mesh.setMatrixAt(i, dummy.matrix);
    mesh.setColorAt(i, new THREE.Color(palette[Math.floor(Math.random() * palette.length)]));
  }
  mesh.instanceMatrix.needsUpdate = true;
  if (mesh.instanceColor) mesh.instanceColor.needsUpdate = true;
  return mesh;
}

function generateStarfieldTexture(size = 2048): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  ctx.fillStyle = '#020617';
  ctx.fillRect(0, 0, size, size);

  // Draw milky way band
  const gradient = ctx.createLinearGradient(0, 0, size, size);
  gradient.addColorStop(0, 'rgba(15, 23, 42, 0)');
  gradient.addColorStop(0.5, 'rgba(30, 58, 138, 0.4)');
  gradient.addColorStop(1, 'rgba(15, 23, 42, 0)');
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);

  // Draw tiny stars
  for (let i = 0; i < 4000; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const r = Math.random() * 1.5;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(255,255,255,${0.3 + Math.random() * 0.7})`;
    ctx.fill();
  }

  // Draw bright stars
  for (let i = 0; i < 200; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const r = 1 + Math.random() * 2;
    ctx.beginPath();
    ctx.arc(x, y, r, 0, Math.PI * 2);
    ctx.fillStyle = `rgba(186, 230, 253, ${0.8 + Math.random() * 0.2})`;
    ctx.fill();
    // glow
    const glow = ctx.createRadialGradient(x, y, 0, x, y, r * 4);
    glow.addColorStop(0, 'rgba(125, 211, 252, 0.4)');
    glow.addColorStop(1, 'transparent');
    ctx.fillStyle = glow;
    ctx.fillRect(x - r * 4, y - r * 4, r * 8, r * 8);
  }

  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function buildFarLayerTextured(): THREE.Mesh {
  const geo = new THREE.SphereGeometry(600, 64, 64);
  const mat = new THREE.MeshBasicMaterial({
    map: generateStarfieldTexture(),
    side: THREE.BackSide,
    depthWrite: false,
    transparent: true,
    opacity: 0.8
  });
  return new THREE.Mesh(geo, mat);
}

function buildNearPointsLayer(count: number): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const colorObj = new THREE.Color();
  
  for (let i = 0; i < count; i++) {
    const p = randomSpherePoint(20, 60);
    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;
    
    // random dust colors
    colorObj.setHex([0x7dd3fc, 0x38bdf8, 0xe0f2fe][Math.floor(Math.random() * 3)]);
    colors[i * 3] = colorObj.r;
    colors[i * 3 + 1] = colorObj.g;
    colors[i * 3 + 2] = colorObj.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.PointsMaterial({ 
    size: 0.8, 
    vertexColors: true, 
    transparent: true, 
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });
  return new THREE.Points(geo, mat);
}

export function buildParallaxStarfield(scene: THREE.Scene, lowPower = false): ParallaxStarfield {
  const root = new THREE.Group();
  scene.add(root);
  const layers: ParallaxLayer[] = [];

  // Layer 1: Near Points
  const nearGroup = new THREE.Group();
  nearGroup.add(buildNearPointsLayer(lowPower ? 1000 : 3000));
  root.add(nearGroup);
  layers.push({ group: nearGroup, speed: 0.003 });

  // Layer 2: Mid InstancedMesh
  const midGroup = new THREE.Group();
  midGroup.add(buildInstancedLayer(
    lowPower ? 200 : 400, 100, 180, 1.0, 2.5,
    [0x93c5fd, 0x818cf8, 0xfbbf24], 2.0, THREE.AdditiveBlending
  ));
  root.add(midGroup);
  layers.push({ group: midGroup, speed: 0.0012 });

  // Layer 3: Far textured mesh
  const farGroup = new THREE.Group();
  farGroup.add(buildFarLayerTextured());
  root.add(farGroup);
  layers.push({ group: farGroup, speed: 0.0003 });

  return { root, layers };
}

export function disposeParallaxStarfield(field: ParallaxStarfield | null): void {
  if (!field) return;
  disposeObject3D(field.root);
  field.root.parent?.remove(field.root);
}
