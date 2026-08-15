import * as THREE from 'three';
import type { Planet } from '../api/orbit';
import {
  getArchetypeBaseColor,
  getPlanetIdentity,
  getStateOverlay,
  hashSlug,
  type PlanetArchetype,
  type PlanetIdentity,
} from './planet-materials';
import { planetAtmosphereFragment, planetAtmosphereVertex } from './shaders/planet-atmosphere.glsl';
import { planetCloudsFragment, planetCloudsVertex } from './shaders/planet-clouds.glsl';
import { planetFresnelFragment, planetFresnelVertex } from './shaders/planet-fresnel.glsl';
import { planetRingFragment, planetRingVertex } from './shaders/planet-ring.glsl';
import { planetShellFragment, planetShellVertex } from './shaders/planet-shell.glsl';
import { planetSurfaceFragment, planetSurfaceVertex } from './shaders/planet-surface.glsl';

export interface PlanetMeshGroup {
  root: THREE.Group;
  body: THREE.Mesh;
  /** 太阳方向相关的大气壳，同时承担旧 fresnel 描边的角色 */
  atmosphere: THREE.Mesh;
  shell: THREE.Points;
  ring: THREE.Mesh | null;
  moon: THREE.Mesh | null;
  clouds: THREE.Mesh | null;
}

/**
 * 全星球共享的 uniform 对象。
 * 材质 clone 后把这几项换回同一引用，于是每帧只写一次即可驱动全部星球。
 */
export const planetGlobals = {
  uTime: { value: 0 },
  uSunPos: { value: new THREE.Vector3(0, 0, 0) },
  uSunColor: { value: new THREE.Color(0xfff1dc) },
  uAmbient: { value: 0.22 },
};

/** 恒星（星系中心）位置与色温，决定所有星球的昼夜面朝向 */
export function setPlanetSunLight(color: THREE.Color, position?: THREE.Vector3): void {
  planetGlobals.uSunColor.value.copy(color).lerp(new THREE.Color(0xfff4e2), 0.6).multiplyScalar(0.85);
  if (position) planetGlobals.uSunPos.value.copy(position);
}

function shareGlobalUniforms(material: THREE.ShaderMaterial): void {
  const u = material.uniforms as Record<string, THREE.IUniform>;
  if (u.uTime) u.uTime = planetGlobals.uTime;
  if (u.uSunPos) u.uSunPos = planetGlobals.uSunPos;
  if (u.uSunColor) u.uSunColor = planetGlobals.uSunColor;
  if (u.uAmbient) u.uAmbient = planetGlobals.uAmbient;
}

const ARCHETYPE_DEFINE: Record<PlanetArchetype, string | null> = {
  gasGiant: 'ARCH_GASGIANT',
  lavaCore: 'ARCH_LAVA',
  iceCrystal: 'ARCH_ICE',
  storm: 'ARCH_STORM',
  rockyMoon: 'ARCH_ROCKY',
  ringed: null, // 类地
};

const BUMP_SCALE: Record<PlanetArchetype, number> = {
  gasGiant: 0.35,
  lavaCore: 1.0,
  iceCrystal: 0.9,
  storm: 0.45,
  rockyMoon: 1.5,
  ringed: 1.2,
};

interface PlanetPalette {
  base: THREE.Color;
  accent: THREE.Color;
  atmo: THREE.Color;
}

function archetypeAtmosphereColor(archetype: PlanetArchetype, base: THREE.Color, galaxyBase: THREE.Color): THREE.Color {
  switch (archetype) {
    case 'lavaCore': return new THREE.Color(0xf97316);
    case 'iceCrystal': return new THREE.Color(0x7dd3fc);
    case 'storm': return new THREE.Color(0xa78bfa);
    case 'gasGiant': return base.clone().lerp(new THREE.Color(0xfbbf24), 0.28);
    default: return new THREE.Color(0x93c5fd).lerp(galaxyBase, 0.32);
  }
}

function getPlanetPalette(identity: PlanetIdentity, galaxyBase: THREE.Color): PlanetPalette {
  const base = getArchetypeBaseColor(identity, galaxyBase);
  let accent: THREE.Color;

  switch (identity.archetype) {
    case 'gasGiant':
      accent = base.clone().lerp(new THREE.Color(0xfdf0d5), 0.6);
      break;
    case 'lavaCore':
      accent = new THREE.Color(0xfb923c);
      break;
    case 'iceCrystal':
      accent = new THREE.Color(0xe0f2fe);
      break;
    case 'storm':
      accent = base.clone().lerp(new THREE.Color(0xede9fe), 0.55);
      break;
    case 'rockyMoon':
      accent = base.clone().multiplyScalar(0.6);
      break;
    default: {
      // 类地：base 压成深海色，accent 取偏移色相当作植被
      const hsl = { h: 0, s: 0, l: 0 };
      base.getHSL(hsl);
      base.setHSL(hsl.h, Math.min(hsl.s + 0.2, 0.92), Math.max(hsl.l * 0.6, 0.15));
      accent = new THREE.Color().setHSL((hsl.h + 0.42 + identity.hueOffset * 0.12) % 1, 0.4, 0.33);
    }
  }

  return { base, accent, atmo: archetypeAtmosphereColor(identity.archetype, base, galaxyBase) };
}

const surfaceTemplates = new Map<string, THREE.ShaderMaterial>();

function getSurfaceMaterial(archetype: PlanetArchetype, lowPower: boolean, cloudShadow: boolean): THREE.ShaderMaterial {
  const key = `${archetype}|${lowPower ? 'lp' : 'hi'}|${cloudShadow ? 'cs' : 'nc'}`;
  let template = surfaceTemplates.get(key);
  if (!template) {
    const defines: Record<string, string | number> = { FBM_OCTAVES: lowPower ? 2 : 4 };
    const archDefine = ARCHETYPE_DEFINE[archetype];
    if (archDefine) defines[archDefine] = '';
    if (!lowPower) defines.USE_BUMP = '';
    if (cloudShadow) defines.USE_CLOUD_SHADOW = '';

    template = new THREE.ShaderMaterial({
      defines,
      uniforms: {
        uTime: { value: 0 },
        uSunPos: { value: new THREE.Vector3() },
        uSunColor: { value: new THREE.Color(0xffffff) },
        uAmbient: { value: 0.3 },
        uBaseColor: { value: new THREE.Color(0xffffff) },
        uAccentColor: { value: new THREE.Color(0xffffff) },
        uAtmoColor: { value: new THREE.Color(0xffffff) },
        uSeed: { value: new THREE.Vector3() },
        uStripeFreq: { value: 3 },
        uBump: { value: 0.04 },
        uCloudSeed: { value: new THREE.Vector3() },
        uCloudCoverage: { value: 0.5 },
        uSaturation: { value: 1 },
        uGlow: { value: 0 },
        uOverlayColor: { value: new THREE.Color(0x000000) },
        uOverlayStrength: { value: 0 },
        uHover: { value: 0 },
        uPulse: { value: 0 },
        uNightLights: { value: 0 },
      },
      vertexShader: planetSurfaceVertex,
      fragmentShader: planetSurfaceFragment,
    });
    surfaceTemplates.set(key, template);
  }

  const material = template.clone();
  shareGlobalUniforms(material);
  return material;
}

const cloudTemplates = new Map<string, THREE.ShaderMaterial>();

function createCloudMaterial(lowPower: boolean): THREE.ShaderMaterial {
  const key = lowPower ? 'lp' : 'hi';
  let cloudTemplate = cloudTemplates.get(key);
  if (!cloudTemplate) {
    cloudTemplate = new THREE.ShaderMaterial({
      defines: { FBM_OCTAVES: lowPower ? 2 : 4 },
      uniforms: {
        uTime: { value: 0 },
        uSunPos: { value: new THREE.Vector3() },
        uSunColor: { value: new THREE.Color(0xffffff) },
        uSeed: { value: new THREE.Vector3() },
        uTint: { value: new THREE.Color(0xffffff) },
        uCoverage: { value: 0.5 },
        uOpacity: { value: 0.85 },
        uSaturation: { value: 1 },
      },
      vertexShader: planetCloudsVertex,
      fragmentShader: planetCloudsFragment,
      transparent: true,
      depthWrite: false,
    });
    cloudTemplates.set(key, cloudTemplate);
  }
  const material = cloudTemplate.clone();
  shareGlobalUniforms(material);
  return material;
}

export function buildFresnelShell(color: THREE.Color, size: number, intensity = 0.38): THREE.Mesh {
  const mesh = new THREE.Mesh(
    new THREE.SphereGeometry(size * 1.18, 32, 32),
    new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: color.clone() },
        uIntensity: { value: intensity },
        uPower: { value: 2.4 },
      },
      vertexShader: planetFresnelVertex,
      fragmentShader: planetFresnelFragment,
      transparent: true,
      depthWrite: false,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
    }),
  );
  mesh.renderOrder = 1;
  return mesh;
}

function buildAtmosphereShell(color: THREE.Color, size: number, intensity: number): THREE.Mesh {
  const material = new THREE.ShaderMaterial({
    uniforms: {
      uColor: { value: color.clone() },
      uSunPos: { value: new THREE.Vector3() },
      uIntensity: { value: intensity },
      uPower: { value: 2.2 },
      uSaturation: { value: 1 },
    },
    vertexShader: planetAtmosphereVertex,
    fragmentShader: planetAtmosphereFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    side: THREE.BackSide,
  });
  shareGlobalUniforms(material);
  const mesh = new THREE.Mesh(new THREE.SphereGeometry(size * 1.16, 32, 32), material);
  mesh.renderOrder = 1;
  return mesh;
}

export function buildParticleShell(color: THREE.Color, size: number, count: number, sizeScale = 1): THREE.Points {
  const positions = new Float32Array(count * 3);
  const phases = new Float32Array(count);
  const sizes = new Float32Array(count);
  const golden = Math.PI * (3 - Math.sqrt(5));

  for (let i = 0; i < count; i++) {
    const y = 1 - (i / Math.max(count - 1, 1)) * 2;
    const r = Math.sqrt(Math.max(0, 1 - y * y));
    const theta = golden * i;
    positions[i * 3] = Math.cos(theta) * r;
    positions[i * 3 + 1] = y;
    positions[i * 3 + 2] = Math.sin(theta) * r;
    phases[i] = Math.random() * Math.PI * 2;
    sizes[i] = (0.9 + Math.random() * 1.6) * sizeScale;
  }

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('aPhase', new THREE.BufferAttribute(phases, 1));
  geo.setAttribute('aSize', new THREE.BufferAttribute(sizes, 1));

  const mat = new THREE.ShaderMaterial({
    uniforms: {
      uTime: planetGlobals.uTime,
      uHover: { value: 0 },
      uColor: { value: color.clone() },
      uBaseRadius: { value: size * 1.22 },
      uPixelRatio: { value: Math.min(typeof window !== 'undefined' ? window.devicePixelRatio : 1, 2) },
    },
    vertexShader: planetShellVertex,
    fragmentShader: planetShellFragment,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
  });

  const shell = new THREE.Points(geo, mat);
  shell.renderOrder = 2;
  return shell;
}

function buildRing(color: THREE.Color, size: number, seed: THREE.Vector3, tilt: number): THREE.Mesh {
  const inner = size * 1.35;
  const outer = size * 2.2;
  const geo = new THREE.RingGeometry(inner, outer, 128);
  // 重映射 UV：u 沿半径方向，让 shader 里的一维条纹变成同心环带
  const pos = geo.attributes.position;
  const uv = geo.attributes.uv;
  const v = new THREE.Vector3();
  for (let i = 0; i < pos.count; i++) {
    v.fromBufferAttribute(pos, i);
    const t = (v.length() - inner) / (outer - inner);
    uv.setXY(i, t, 0.5);
  }
  uv.needsUpdate = true;

  const material = new THREE.ShaderMaterial({
    defines: { FBM_OCTAVES: 2 },
    uniforms: {
      uColor: { value: color.clone().lerp(new THREE.Color(0xffffff), 0.35) },
      uSunPos: { value: new THREE.Vector3() },
      uSunColor: { value: new THREE.Color(0xffffff) },
      uSeed: { value: seed.clone() },
      uOpacity: { value: 0.9 },
      uPlanetRadius: { value: size },
      uSaturation: { value: 1 },
    },
    vertexShader: planetRingVertex,
    fragmentShader: planetRingFragment,
    transparent: true,
    depthWrite: false,
    side: THREE.DoubleSide,
  });
  shareGlobalUniforms(material);

  const ring = new THREE.Mesh(geo, material);
  ring.rotation.x = Math.PI * tilt;
  return ring;
}

function buildMoon(size: number, seed: THREE.Vector3, palette: PlanetPalette, lowPower: boolean): THREE.Mesh {
  const material = getSurfaceMaterial('rockyMoon', lowPower, false);
  const u = material.uniforms;
  u.uBaseColor.value.copy(palette.base).lerp(new THREE.Color(0xcbd5e1), 0.6);
  u.uAccentColor.value.copy(palette.accent);
  u.uAtmoColor.value.set(0x94a3b8);
  u.uSeed.value.copy(seed).addScalar(13.7);
  u.uBump.value = 0.05;
  u.uStripeFreq.value = 3;

  const moon = new THREE.Mesh(new THREE.SphereGeometry(size * 0.22, lowPower ? 20 : 28, lowPower ? 20 : 28), material);
  moon.position.set(size * 2.2, size * 0.5, size * 0.8);
  return moon;
}

function shellParticleCount(size: number, lowPower = false): number {
  const base = size >= 0.85 ? 150 : size >= 0.7 ? 120 : 100;
  return lowPower ? Math.floor(base * 0.55) : base;
}

/** 气态巨星与风暴星的「云」本身就画在地表 shader 里，再叠一层壳只会糊掉条带 */
const CLOUDY_ARCHETYPES: PlanetArchetype[] = ['ringed', 'iceCrystal'];

function planetSeed(slugHash: number): THREE.Vector3 {
  return new THREE.Vector3(
    (slugHash % 211) * 0.37,
    ((slugHash >> 5) % 197) * 0.41,
    ((slugHash >> 11) % 181) * 0.29,
  );
}

function planetRadius(planet: Planet): number {
  return planet.difficulty === 'hard' ? 0.9 : planet.difficulty === 'medium' ? 0.75 : 0.62;
}

interface PlanetStateUniforms {
  saturation: number;
  glow: number;
  overlayColor: THREE.Color;
  overlayStrength: number;
  pulse: number;
  nightLights: number;
  atmoIntensity: number;
}

function computeStateUniforms(planet: Planet): PlanetStateUniforms {
  const overlay = getStateOverlay(planet);
  const isLit = planet.is_permanent || planet.status === 'lit';
  return {
    saturation: overlay.saturationMul,
    glow: overlay.emissiveBoost * 0.075,
    overlayColor: overlay.overlayColor ?? new THREE.Color(0x000000),
    overlayStrength: overlay.overlayColor ? overlay.overlayOpacity : 0,
    pulse: overlay.pulse ? 1 : 0,
    nightLights: isLit ? 1 : 0,
    atmoIntensity: overlay.glowRing ? 0.34 : 0.22,
  };
}

function applyPlanetState(group: PlanetMeshGroup, planet: Planet): void {
  const state = computeStateUniforms(planet);

  const bodyMat = group.body.material as THREE.ShaderMaterial;
  bodyMat.uniforms.uSaturation.value = state.saturation;
  bodyMat.uniforms.uGlow.value = state.glow;
  bodyMat.uniforms.uOverlayColor.value.copy(state.overlayColor);
  bodyMat.uniforms.uOverlayStrength.value = state.overlayStrength;
  bodyMat.uniforms.uPulse.value = state.pulse;
  bodyMat.uniforms.uNightLights.value = state.nightLights;

  const atmoMat = group.atmosphere.material as THREE.ShaderMaterial;
  atmoMat.uniforms.uIntensity.value = state.atmoIntensity;
  atmoMat.uniforms.uSaturation.value = state.saturation;
  group.body.userData.baseFresnelIntensity = state.atmoIntensity;

  if (group.clouds) {
    (group.clouds.material as THREE.ShaderMaterial).uniforms.uSaturation.value = state.saturation;
  }
  if (group.ring) {
    (group.ring.material as THREE.ShaderMaterial).uniforms.uSaturation.value = state.saturation;
  }
  if (group.moon) {
    const moonMat = group.moon.material as THREE.ShaderMaterial;
    moonMat.uniforms.uSaturation.value = state.saturation;
    moonMat.uniforms.uGlow.value = state.glow * 0.5;
  }
}

export function createPlanetMesh(planet: Planet, galaxyBase: THREE.Color, lowPower = false): PlanetMeshGroup {
  const identity = getPlanetIdentity(planet.slug);
  const palette = getPlanetPalette(identity, galaxyBase);
  const size = planetRadius(planet);
  const slugHash = hashSlug(planet.slug);
  const seed = planetSeed(slugHash);

  const hasClouds = !lowPower && CLOUDY_ARCHETYPES.includes(identity.archetype);
  const cloudSeed = seed.clone().addScalar(7.3);
  const cloudCoverage = 0.44 + ((slugHash >> 7) % 17) * 0.012;

  const bodyMaterial = getSurfaceMaterial(identity.archetype, lowPower, hasClouds);
  const u = bodyMaterial.uniforms;
  u.uBaseColor.value.copy(palette.base);
  u.uAccentColor.value.copy(palette.accent);
  u.uAtmoColor.value.copy(palette.atmo);
  u.uSeed.value.copy(seed);
  u.uStripeFreq.value = identity.stripeFreq;
  u.uBump.value = identity.bumpScale * BUMP_SCALE[identity.archetype];
  u.uCloudSeed.value.copy(cloudSeed);
  u.uCloudCoverage.value = cloudCoverage;

  const segments = lowPower ? 40 : 56;
  const body = new THREE.Mesh(new THREE.SphereGeometry(size, segments, segments), bodyMaterial);

  const atmosphere = buildAtmosphereShell(palette.atmo, size, 0.24);
  // 粒子壳只作微弱的尘埃点缀，避免在轮廓上叠成一圈发光颗粒
  const shell = buildParticleShell(palette.atmo.clone().multiplyScalar(0.18), size, shellParticleCount(size, lowPower), 0.34);

  const root = new THREE.Group();
  root.add(body);
  root.add(atmosphere);
  root.add(shell);

  // 轴倾角 + 自转速度（slug 决定，稳定可复现）
  const tilt = ((slugHash % 47) / 47 - 0.5) * 0.55;
  root.rotation.z = tilt;
  body.userData.spinSpeed = 0.0016 + ((slugHash >> 3) % 23) * 0.00012;

  let clouds: THREE.Mesh | null = null;
  if (hasClouds) {
    const cloudMaterial = createCloudMaterial(lowPower);
    cloudMaterial.uniforms.uSeed.value.copy(cloudSeed);
    cloudMaterial.uniforms.uCoverage.value = cloudCoverage;
    cloudMaterial.uniforms.uTint.value.copy(palette.atmo).lerp(new THREE.Color(0xffffff), 0.72);
    cloudMaterial.uniforms.uOpacity.value = identity.archetype === 'iceCrystal' ? 0.45 : 0.8;
    clouds = new THREE.Mesh(new THREE.SphereGeometry(size * 1.035, 40, 40), cloudMaterial);
    clouds.renderOrder = 0;
    root.add(clouds);
  }

  let ring: THREE.Mesh | null = null;
  if (identity.hasRing || identity.archetype === 'ringed') {
    ring = buildRing(palette.base, size, seed, identity.archetype === 'ringed' ? 0.38 : 0.48);
    root.add(ring);
  }

  let moon: THREE.Mesh | null = null;
  if (identity.hasMoon) {
    moon = buildMoon(size, seed, palette, lowPower);
    root.add(moon);
  }

  body.userData.planetIdentity = identity;
  body.userData.planetArchetype = identity.archetype;
  body.userData.baseColor = palette.base.clone();
  body.userData.shell = shell;
  body.userData.fresnel = atmosphere;
  body.userData.clouds = clouds;
  body.userData.ring = ring;
  body.userData.moon = moon;

  const group: PlanetMeshGroup = { root, body, atmosphere, shell, ring, moon, clouds };
  applyPlanetState(group, planet);
  return group;
}

/** 每帧驱动所有星球材质（自转湍流、熔岩脉动、粒子壳呼吸） */
export function tickPlanetVisuals(timeMs: number): void {
  planetGlobals.uTime.value = timeMs * 0.001;
}

export function updatePlanetMeshVisuals(group: PlanetMeshGroup, planet: Planet, galaxyBase: THREE.Color): void {
  applyPlanetPalette(group, planet, galaxyBase);
  applyPlanetState(group, planet);
}

export function updatePlanetBodyVisuals(body: THREE.Mesh, planet: Planet, galaxyBase: THREE.Color): void {
  const group: PlanetMeshGroup = {
    root: body.parent as THREE.Group,
    body,
    atmosphere: body.userData.fresnel as THREE.Mesh,
    shell: body.userData.shell as THREE.Points,
    ring: (body.userData.ring as THREE.Mesh | null) ?? null,
    moon: (body.userData.moon as THREE.Mesh | null) ?? null,
    clouds: (body.userData.clouds as THREE.Mesh | null) ?? null,
  };
  updatePlanetMeshVisuals(group, planet, galaxyBase);
}

function applyPlanetPalette(group: PlanetMeshGroup, planet: Planet, galaxyBase: THREE.Color): void {
  const identity = getPlanetIdentity(planet.slug);
  const palette = getPlanetPalette(identity, galaxyBase);
  const bodyMat = group.body.material as THREE.ShaderMaterial;
  bodyMat.uniforms.uBaseColor.value.copy(palette.base);
  bodyMat.uniforms.uAccentColor.value.copy(palette.accent);
  bodyMat.uniforms.uAtmoColor.value.copy(palette.atmo);
  group.body.userData.baseColor = palette.base.clone();

  (group.atmosphere.material as THREE.ShaderMaterial).uniforms.uColor.value.copy(palette.atmo);
  (group.shell.material as THREE.ShaderMaterial).uniforms.uColor.value.copy(palette.atmo).multiplyScalar(0.18);
  if (group.clouds) {
    (group.clouds.material as THREE.ShaderMaterial).uniforms.uTint.value.copy(palette.atmo).lerp(new THREE.Color(0xffffff), 0.72);
  }
  if (group.ring) {
    (group.ring.material as THREE.ShaderMaterial).uniforms.uColor.value.copy(palette.base).lerp(new THREE.Color(0xffffff), 0.35);
  }
}

export function getPlanetPickMesh(group: PlanetMeshGroup): THREE.Mesh {
  return group.body;
}
