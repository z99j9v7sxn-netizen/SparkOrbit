import * as THREE from 'three';
import type { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js';

function disposeMaterial(material: THREE.Material): void {
  for (const key of Object.keys(material)) {
    const value = (material as unknown as Record<string, unknown>)[key];
    if (value instanceof THREE.Texture) value.dispose();
  }
  material.dispose();
}

export function disposeObject3D(root: THREE.Object3D | null | undefined): void {
  if (!root) return;
  root.traverse((obj) => {
    if (
      obj instanceof THREE.Mesh
      || obj instanceof THREE.Line
      || obj instanceof THREE.Points
      || obj instanceof THREE.Sprite
      || obj instanceof THREE.InstancedMesh
    ) {
      obj.geometry?.dispose?.();
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      mats.forEach((m) => m && disposeMaterial(m));
    }
  });
}

export function disposeComposer(composer: EffectComposer | null | undefined): void {
  composer?.dispose();
}
