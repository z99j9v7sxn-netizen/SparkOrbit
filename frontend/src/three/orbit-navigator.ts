import * as THREE from 'three';
import { disposeObject3D } from './dispose';

export interface NavigatorTrack {
  root: THREE.Group;
  curves: THREE.Mesh[];
}

export function buildOrbitTrack(points: THREE.Vector3[], color: THREE.Color = new THREE.Color(0x22d3ee)): NavigatorTrack {
  const root = new THREE.Group();
  const curves: THREE.Mesh[] = [];

  const mat = new THREE.MeshBasicMaterial({
    color,
    transparent: true,
    opacity: 0.8,
    blending: THREE.AdditiveBlending,
    depthWrite: false
  });

  for (let i = 0; i < points.length - 1; i++) {
    const p1 = points[i];
    const p2 = points[i + 1];

    // Control points to create an arc
    const mid = p1.clone().lerp(p2, 0.5);
    const dist = p1.distanceTo(p2);
    // Lift the arc upwards
    mid.y += dist * 0.3;

    const cp1 = p1.clone().lerp(mid, 0.5);
    const cp2 = mid.clone().lerp(p2, 0.5);

    const curve = new THREE.CubicBezierCurve3(p1, cp1, cp2, p2);
    
    // Create tube geometry around the curve
    const geo = new THREE.TubeGeometry(curve, 64, 0.15, 8, false);
    const mesh = new THREE.Mesh(geo, mat);
    
    // Add pulsing user data
    mesh.userData.phase = i;
    
    root.add(mesh);
    curves.push(mesh);
  }

  return { root, curves };
}

export function updateOrbitTrack(track: NavigatorTrack, time: number) {
  track.curves.forEach((mesh) => {
    const mat = mesh.material as THREE.MeshBasicMaterial;
    // Simple pulsing opacity based on time
    mat.opacity = 0.4 + Math.sin(time * 0.003 + mesh.userData.phase) * 0.4;
  });
}

export function disposeOrbitTrack(track: NavigatorTrack | null) {
  if (!track) return;
  disposeObject3D(track.root);
  track.root.parent?.remove(track.root);
}
