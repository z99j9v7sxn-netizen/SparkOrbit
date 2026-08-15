import * as THREE from 'three';
import type { Galaxy } from '../api/orbit';

/**
 * 宇宙层「科目星系」的可扩展布局。
 * N ≤ 6 沿单环排布（少量时环最可读）；N > 6 用黄金角螺旋（phyllotaxis），
 * 任意数量等密度无重叠，10~20 个星系也能摆下。
 */
export interface GalaxyPlacement {
  galaxy: Galaxy;
  position: THREE.Vector3;
  /** 星系节点基准尺寸（传给 createSpiralGalaxy 的 size） */
  size: number;
  /** 点云盘半径（size * 2.1，与 spiral-galaxy 内部一致） */
  diskRadius: number;
}

export interface UniverseLayout {
  placements: GalaxyPlacement[];
  /** 布局包围半径（含最外星系的盘径），用于相机取景 */
  boundRadius: number;
}

const GOLDEN_ANGLE = Math.PI * (3 - Math.sqrt(5)); // ≈ 137.5°

function hashString(str: string): number {
  let h = 0;
  for (let i = 0; i < str.length; i++) {
    h = (h << 5) - h + str.charCodeAt(i);
    h |= 0;
  }
  return Math.abs(h);
}

export function galaxyNodeSize(galaxy: Galaxy): number {
  return 2.4 + Math.min(galaxy.planet_count / 12, 0.8);
}

/** 星系点云盘半径（spiral-galaxy 直接引用此函数，保证布局与渲染一致） */
export function galaxyDiskRadius(size: number): number {
  return size * 3.0;
}

export function layoutGalaxies(galaxies: Galaxy[]): UniverseLayout {
  const placements: GalaxyPlacement[] = [];
  if (!galaxies.length) return { placements, boundRadius: 20 };

  const sizes = galaxies.map(galaxyNodeSize);
  const maxDisk = galaxyDiskRadius(Math.max(...sizes));
  // 间距收紧：盘径占间距约 48%，星系在画面中足够大又不至于贴边
  const minGap = maxDisk * 2.05 + 2;
  let boundRadius = 0;

  if (galaxies.length <= 6) {
    // 单环：环周长保证相邻星系间距 ≥ minGap
    const n = galaxies.length;
    const ringR = Math.max(15, (n * minGap) / (Math.PI * 2));
    galaxies.forEach((g, i) => {
      const angle = (i / n) * Math.PI * 2 - Math.PI / 2;
      const y = (((hashString(g.slug) >> 3) % 100) / 100 - 0.5) * 4.8;
      const size = sizes[i];
      placements.push({
        galaxy: g,
        position: new THREE.Vector3(Math.cos(angle) * ringR, y, Math.sin(angle) * ringR),
        size,
        diskRadius: galaxyDiskRadius(size),
      });
      boundRadius = Math.max(boundRadius, ringR + galaxyDiskRadius(size));
    });
  } else {
    // 黄金角螺旋：r = spacing·√(i + offset)，相邻最小间距趋近 spacing
    const spacing = minGap;
    galaxies.forEach((g, i) => {
      const angle = i * GOLDEN_ANGLE - Math.PI / 2;
      const radius = spacing * Math.sqrt(i + 1.2);
      const y = (((hashString(g.slug) >> 3) % 100) / 100 - 0.5) * 5;
      const size = sizes[i];
      placements.push({
        galaxy: g,
        position: new THREE.Vector3(Math.cos(angle) * radius, y, Math.sin(angle) * radius),
        size,
        diskRadius: galaxyDiskRadius(size),
      });
      boundRadius = Math.max(boundRadius, radius + galaxyDiskRadius(size));
    });
  }

  return { placements, boundRadius };
}

/** 按包围半径与 fov/aspect 反推能装下整个布局的相机距离 */
export function fitCameraDistance(boundRadius: number, fovDeg: number, aspect: number): number {
  const fov = THREE.MathUtils.degToRad(fovDeg);
  const halfH = Math.tan(fov / 2);
  const halfW = halfH * Math.max(aspect, 0.5);
  const dist = boundRadius / Math.min(halfH, halfW);
  return dist * 1.04;
}

/**
 * 全局粒子预算：所有星系共享，帧率不随星系数线性劣化。
 * 返回每个星系的基准点数（planet_count 在 spiral-galaxy 内再做 ±25% 密度加权）。
 */
export function galaxyPointBudget(galaxyCount: number, lowPower: boolean): number {
  const budget = lowPower ? 12000 : 30000;
  return Math.round(THREE.MathUtils.clamp(budget / Math.max(galaxyCount, 1), 600, 2600));
}
