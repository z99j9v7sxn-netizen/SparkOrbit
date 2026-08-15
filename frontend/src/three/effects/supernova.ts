import * as THREE from 'three';
import gsap from 'gsap';

export interface BurstFx {
  points: THREE.Points;
  velocities: THREE.Vector3[];
  life: number;
  ttl: number;
}

export function spawnBurst(scene: THREE.Scene, worldPos: THREE.Vector3, color: THREE.Color): BurstFx {
  const count = 260;
  const positions = new Float32Array(count * 3);
  const velocities: THREE.Vector3[] = [];
  for (let i = 0; i < count; i++) {
    positions[i * 3] = worldPos.x;
    positions[i * 3 + 1] = worldPos.y;
    positions[i * 3 + 2] = worldPos.z;
    const dir = new THREE.Vector3(Math.random() * 2 - 1, Math.random() * 2 - 1, Math.random() * 2 - 1).normalize();
    velocities.push(dir.multiplyScalar(0.18 + Math.random() * 0.42));
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const mat = new THREE.PointsMaterial({
    color,
    size: 0.5,
    transparent: true,
    opacity: 1,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const points = new THREE.Points(geo, mat);
  scene.add(points);
  return { points, velocities, life: 0, ttl: 70 };
}

export function spawnShockwave(
  scene: THREE.Scene,
  camera: THREE.Camera,
  worldPos: THREE.Vector3,
): THREE.Mesh {
  const ring = new THREE.Mesh(
    new THREE.RingGeometry(0.2, 0.5, 64),
    new THREE.MeshBasicMaterial({
      color: 0xfff2c4,
      transparent: true,
      opacity: 0.9,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  ring.position.copy(worldPos);
  ring.lookAt(camera.position);
  scene.add(ring);
  gsap.to(ring.scale, { x: 22, y: 22, z: 22, duration: 1.2, ease: 'power2.out' });
  gsap.to(ring.material, {
    opacity: 0,
    duration: 1.2,
    ease: 'power1.out',
    onComplete: () => {
      scene.remove(ring);
      ring.geometry.dispose();
      (ring.material as THREE.Material).dispose();
    },
  });
  return ring;
}

export function playSupernovaOnMesh(mesh: THREE.Mesh): gsap.core.Timeline {
  const mat = mesh.material as THREE.MeshStandardMaterial;
  const tl = gsap.timeline()
    .to(mesh.scale, { x: 3.4, y: 3.4, z: 3.4, duration: 0.45, ease: 'power3.out' })
    .to(mesh.scale, { x: 1.4, y: 1.4, z: 1.4, duration: 0.7, ease: 'elastic.out(1,0.4)' });
  if (mat.emissiveIntensity !== undefined) {
    tl.fromTo(
      mat,
      { emissiveIntensity: mat.emissiveIntensity },
      { emissiveIntensity: 7, duration: 0.4, yoyo: true, repeat: 1, ease: 'power2.out' },
      0,
    );
  }
  const glow = (mesh.material as THREE.ShaderMaterial).uniforms?.uGlow;
  if (glow) {
    tl.fromTo(
      glow,
      { value: glow.value },
      { value: 2.4, duration: 0.4, yoyo: true, repeat: 1, ease: 'power2.out' },
      0,
    );
  }
  return tl;
}

export function updateBurstFx(scene: THREE.Scene, fx: BurstFx): boolean {
  const attr = fx.points.geometry.getAttribute('position') as THREE.BufferAttribute;
  for (let j = 0; j < fx.velocities.length; j++) {
    attr.setX(j, attr.getX(j) + fx.velocities[j].x);
    attr.setY(j, attr.getY(j) + fx.velocities[j].y);
    attr.setZ(j, attr.getZ(j) + fx.velocities[j].z);
    fx.velocities[j].multiplyScalar(0.96);
  }
  attr.needsUpdate = true;
  fx.life += 1;
  (fx.points.material as THREE.PointsMaterial).opacity = Math.max(0, 1 - fx.life / fx.ttl);
  if (fx.life >= fx.ttl) {
    scene.remove(fx.points);
    fx.points.geometry.dispose();
    (fx.points.material as THREE.Material).dispose();
    return true;
  }
  return false;
}

export function spawnMeteorImpact(
  scene: THREE.Scene,
  camera: THREE.Camera,
  worldPos: THREE.Vector3,
  isHit: boolean,
): BurstFx | null {
  if (isHit) {
    spawnShockwave(scene, camera, worldPos);
    return spawnBurst(scene, worldPos, new THREE.Color(0x7dd3fc));
  }

  const ring = new THREE.Mesh(
    new THREE.RingGeometry(1.5, 2.8, 64),
    new THREE.MeshBasicMaterial({
      color: 0xef4444,
      transparent: true,
      opacity: 0.75,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  ring.position.copy(worldPos);
  ring.lookAt(camera.position);
  scene.add(ring);
  gsap.to(ring.scale, { x: 10, y: 10, z: 10, duration: 0.9, ease: 'power2.out' });
  gsap.to(ring.material, {
    opacity: 0,
    duration: 0.9,
    ease: 'power1.out',
    onComplete: () => {
      scene.remove(ring);
      ring.geometry.dispose();
      (ring.material as THREE.Material).dispose();
    },
  });
  return null;
}
