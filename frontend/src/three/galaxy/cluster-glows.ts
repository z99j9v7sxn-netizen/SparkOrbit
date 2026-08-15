import * as THREE from 'three';
import { disposeObject3D } from '../dispose';
import { CLUSTERS } from './cluster-layout';

/** 辉光基准透明度（视觉主旋钮） */
const CORE_OPACITY = 0.1;
const HALO_OPACITY = 0.03;

export interface ClusterGlows {
  root: THREE.Group;
  /** hoverId：悬停簇编号（-1 无）；fade：随 globalFade 联动 */
  tick: (nowMs: number, hoverId: number, fade: number) => void;
  dispose: () => void;
}

interface GlowEntry {
  id: number;
  core: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  halo: THREE.Mesh<THREE.SphereGeometry, THREE.MeshBasicMaterial>;
  phase: number;
  /** 悬停插值状态，平滑过渡 */
  hoverT: number;
}

function buildGlowPair(
  position: THREE.Vector3,
  color: THREE.Color,
  coreRadius: number,
  haloRadius: number,
): { core: GlowEntry['core']; halo: GlowEntry['halo'] } {
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(coreRadius, 24, 24),
    new THREE.MeshBasicMaterial({
      color: color.clone().lerp(new THREE.Color(0xffffff), 0.3),
      transparent: true,
      opacity: CORE_OPACITY,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  core.position.copy(position);

  const halo = new THREE.Mesh(
    new THREE.SphereGeometry(haloRadius, 24, 24),
    new THREE.MeshBasicMaterial({
      color: color.clone(),
      transparent: true,
      opacity: HALO_OPACITY,
      blending: THREE.AdditiveBlending,
      side: THREE.BackSide,
      depthWrite: false,
    }),
  );
  halo.position.copy(position);

  return { core, halo };
}

/**
 * 簇心辉光层：每簇「内核小球 + BackSide 光晕」双层网格（复刻 nebula-core 手法），
 * 常态呼吸脉动，悬停簇放大增亮。中心亮团由学习区簇承担，不再叠独立星系核。
 */
export function buildClusterGlows(scene: THREE.Scene): ClusterGlows {
  const root = new THREE.Group();
  scene.add(root);

  const entries: GlowEntry[] = CLUSTERS.map((spec, idx) => {
    // 光晕收在粒子团内部（0.6 倍半径），避免 BackSide 硬切边读作一圈灰色大圆盘
    const { core, halo } = buildGlowPair(spec.position, spec.color, spec.radius * 0.3, spec.radius * 0.6);
    root.add(core, halo);
    return { id: spec.id, core, halo, phase: idx * 1.13, hoverT: 0 };
  });

  return {
    root,
    tick(nowMs: number, hoverId: number, fade: number) {
      const t = nowMs * 0.001;
      for (const entry of entries) {
        const hovered = entry.id === hoverId;
        // 平滑趋近目标，约 300ms 收敛
        entry.hoverT += ((hovered ? 1 : 0) - entry.hoverT) * 0.08;
        const breath = 1 + Math.sin(t * 0.7 + entry.phase) * 0.07;
        const scale = breath * (1 + entry.hoverT * 0.2);
        entry.core.scale.setScalar(scale);
        entry.halo.scale.setScalar(scale);
        entry.core.material.opacity = CORE_OPACITY * fade * (1 + entry.hoverT * 1.2) * breath;
        entry.halo.material.opacity = HALO_OPACITY * fade * (1 + entry.hoverT * 1.0) * breath;
      }
    },
    dispose() {
      disposeObject3D(root);
      root.parent?.remove(root);
    },
  };
}
