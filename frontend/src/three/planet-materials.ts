import * as THREE from 'three';
import type { Planet } from '../api/orbit';

export const COLOR_LOCKED = 0x334155;

export type PlanetArchetype = 'gasGiant' | 'lavaCore' | 'iceCrystal' | 'ringed' | 'storm' | 'rockyMoon';

export interface PlanetIdentity {
  archetype: PlanetArchetype;
  hueOffset: number;
  stripeFreq: number;
  bumpScale: number;
  roughness: number;
  metalness: number;
  hasRing: boolean;
  hasMoon: boolean;
}

export interface PlanetStateOverlay {
  emissiveBoost: number;
  saturationMul: number;
  overlayColor: THREE.Color | null;
  overlayOpacity: number;
  glowRing: boolean;
  pulse: boolean;
}

export function hashSlug(slug: string): number {
  let h = 0;
  for (let i = 0; i < slug.length; i++) {
    h = (h << 5) - h + slug.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

const ARCHETYPES: PlanetArchetype[] = ['gasGiant', 'lavaCore', 'iceCrystal', 'ringed', 'storm', 'rockyMoon'];

export function getPlanetIdentity(slug: string): PlanetIdentity {
  const h = hashSlug(slug);
  const archetype = ARCHETYPES[h % ARCHETYPES.length];
  return {
    archetype,
    hueOffset: ((h >> 4) % 360) / 360,
    stripeFreq: 2 + (h % 5),
    bumpScale: 0.02 + (h % 8) * 0.008,
    roughness: archetype === 'iceCrystal' ? 0.15 : archetype === 'rockyMoon' ? 0.75 : 0.4,
    metalness: archetype === 'iceCrystal' ? 0.45 : archetype === 'lavaCore' ? 0.15 : 0.28,
    hasRing: archetype === 'ringed' || (h % 7 === 0),
    hasMoon: h % 5 === 0,
  };
}

export function getStateOverlay(p: Planet): PlanetStateOverlay {
  if (p.is_permanent || p.status === 'lit') {
    return { emissiveBoost: 3.5, saturationMul: 1.15, overlayColor: null, overlayOpacity: 0, glowRing: true, pulse: false };
  }
  if (p.status === 'fading') {
    return { emissiveBoost: 1.2, saturationMul: 0.7, overlayColor: new THREE.Color(0xfbbf24), overlayOpacity: 0.25, glowRing: false, pulse: false };
  }
  if (p.status === 'meteor') {
    return { emissiveBoost: 2.2, saturationMul: 0.85, overlayColor: new THREE.Color(0xef4444), overlayOpacity: 0.35, glowRing: true, pulse: true };
  }
  if (p.status === 'locked') {
    return { emissiveBoost: 0.1, saturationMul: 0.35, overlayColor: new THREE.Color(0x334155), overlayOpacity: 0.5, glowRing: false, pulse: false };
  }
  return { emissiveBoost: 0.8, saturationMul: 0.9, overlayColor: null, overlayOpacity: 0, glowRing: false, pulse: false };
}

/** @deprecated Use getStateOverlay + identity base colors instead */
export function planetColor(
  p: Planet,
  base: THREE.Color,
): { color: number; emissive: number; intensity: number } {
  const identity = getPlanetIdentity(p.slug);
  const overlay = getStateOverlay(p);
  const baseColor = getArchetypeBaseColor(identity, base);
  if (overlay.saturationMul < 0.5) {
    baseColor.lerp(new THREE.Color(COLOR_LOCKED), 1 - overlay.saturationMul);
  }
  return {
    color: baseColor.getHex(),
    emissive: baseColor.getHex(),
    intensity: overlay.emissiveBoost,
  };
}

export function getArchetypeBaseColor(identity: PlanetIdentity, galaxyBase: THREE.Color): THREE.Color {
  const c = galaxyBase.clone();
  switch (identity.archetype) {
    case 'gasGiant':
      c.offsetHSL(identity.hueOffset * 0.15, 0.2, 0.05);
      break;
    case 'lavaCore':
      c.setHex(0xef4444).lerp(galaxyBase, 0.35);
      break;
    case 'iceCrystal':
      c.setHex(0x7dd3fc).lerp(galaxyBase, 0.25);
      break;
    case 'ringed':
      c.offsetHSL(identity.hueOffset * 0.1, 0.15, 0.08);
      break;
    case 'storm':
      c.setHex(0xa78bfa).lerp(galaxyBase, 0.4);
      break;
    case 'rockyMoon':
      c.setHex(0x94a3b8).lerp(galaxyBase, 0.3);
      break;
  }
  return c;
}

export function applyPlanetMaterial(mesh: THREE.Mesh, planet: Planet, base: THREE.Color): void {
  const identity = getPlanetIdentity(planet.slug);
  const overlay = getStateOverlay(planet);
  const baseColor = getArchetypeBaseColor(identity, base);
  if (overlay.saturationMul < 1) {
    baseColor.lerp(new THREE.Color(0x64748b), 1 - overlay.saturationMul);
  }
  const mat = mesh.material as THREE.MeshStandardMaterial;
  mat.color.copy(baseColor);
  mat.emissive.copy(baseColor);
  mat.emissiveIntensity = overlay.emissiveBoost;
}
