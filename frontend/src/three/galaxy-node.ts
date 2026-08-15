import * as THREE from 'three';
import { buildFresnelShell, buildParticleShell } from './create-planet-mesh';

export interface StarCore {
  root: THREE.Group;
  tick: (time: number) => void;
}

function createStarSurfaceTexture(color: THREE.Color, size = 512): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const r = Math.floor(color.r * 255);
  const g = Math.floor(color.g * 255);
  const b = Math.floor(color.b * 255);

  const grad = ctx.createRadialGradient(size * 0.46, size * 0.44, 0, size * 0.5, size * 0.5, size * 0.5);
  grad.addColorStop(0, '#fffef8');
  grad.addColorStop(0.18, '#fff4cc');
  grad.addColorStop(0.42, `rgb(${Math.min(255, r + 40)}, ${Math.min(255, g + 30)}, ${b})`);
  grad.addColorStop(0.78, `rgb(${r}, ${g}, ${b})`);
  grad.addColorStop(1, `rgb(${Math.floor(r * 0.45)}, ${Math.floor(g * 0.45)}, ${Math.floor(b * 0.45)})`);
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, size, size);

  for (let y = 0; y < size; y++) {
    const wave = Math.sin((y / size) * Math.PI * 7 + color.g * 8);
    ctx.fillStyle = `rgba(255,255,255,${0.05 + wave * 0.035})`;
    ctx.fillRect(0, y, size, 1);
  }

  for (let i = 0; i < 55; i++) {
    const x = Math.random() * size;
    const y = Math.random() * size;
    const rad = 3 + Math.random() * 16;
    const granule = ctx.createRadialGradient(x, y, 0, x, y, rad);
    granule.addColorStop(0, `rgba(255,230,180,${0.15 + Math.random() * 0.25})`);
    granule.addColorStop(0.6, `rgba(${r},${g},${b},0.12)`);
    granule.addColorStop(1, 'transparent');
    ctx.fillStyle = granule;
    ctx.fillRect(x - rad, y - rad, rad * 2, rad * 2);
  }

  const tex = new THREE.CanvasTexture(canvas);
  return tex;
}

export function buildParticleOrbitRing(radius: number, color: number, count = 180): THREE.Points {
  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const c = new THREE.Color(color);
  for (let i = 0; i < count; i++) {
    const a = (i / count) * Math.PI * 2;
    positions[i * 3] = Math.cos(a) * radius;
    positions[i * 3 + 1] = (Math.random() - 0.5) * 0.15;
    positions[i * 3 + 2] = Math.sin(a) * radius;
    colors[i * 3] = c.r;
    colors[i * 3 + 1] = c.g;
    colors[i * 3 + 2] = c.b;
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  const mat = new THREE.PointsMaterial({
    size: 0.22,
    vertexColors: true,
    transparent: true,
    opacity: 0.38,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  return new THREE.Points(geo, mat);
}

export function buildStarCore(color: THREE.Color, lowPower = false): StarCore {
  const group = new THREE.Group();
  const radius = 3.4;
  const glowColor = color.clone().lerp(new THREE.Color(0xfbbf24), 0.28);
  const tex = createStarSurfaceTexture(color);

  const inner = new THREE.Mesh(
    new THREE.SphereGeometry(radius, lowPower ? 48 : 64, lowPower ? 48 : 64),
    new THREE.MeshPhysicalMaterial({
      color: 0xfff7ed,
      emissive: color,
      emissiveIntensity: 1.05,
      roughness: 0.18,
      metalness: 0.2,
      clearcoat: 0.75,
      clearcoatRoughness: 0.08,
      map: tex,
      bumpMap: tex,
      bumpScale: 0.055,
    }),
  );
  group.add(inner);

  const hotCore = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 0.88, 32, 32),
    new THREE.MeshBasicMaterial({
      color: 0xfffbeb,
      transparent: true,
      opacity: 0.28,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  group.add(hotCore);

  const fresnel = buildFresnelShell(glowColor, radius, 0.68);
  const shell = buildParticleShell(glowColor, radius, lowPower ? 420 : 780);
  group.add(fresnel);
  group.add(shell);

  const corona = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.35, 32, 32),
    new THREE.MeshBasicMaterial({
      color: glowColor,
      transparent: true,
      opacity: 0.1,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false,
    }),
  );
  group.add(corona);

  const outerHalo = new THREE.Mesh(
    new THREE.SphereGeometry(radius * 1.75, 24, 24),
    new THREE.MeshBasicMaterial({
      color: color,
      transparent: true,
      opacity: 0.045,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false,
    }),
  );
  group.add(outerHalo);

  group.add(new THREE.PointLight(color.getHex(), 2.0, 120));

  return {
    root: group,
    tick(time: number) {
      inner.rotation.y = time * 0.00012;
      hotCore.rotation.y = -time * 0.00008;
    },
  };
}
