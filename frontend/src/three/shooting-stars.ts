import * as THREE from 'three';

/**
 * 偶发流星：3 条流星的小对象池，每 8~20 秒随机触发一条。
 * 亮头 + 渐隐尾迹（共享一张 canvas 渐变纹理），flare-and-fade 生命周期。
 * lowPower / prefers-reduced-motion 场景下由调用方直接不创建。
 */
export interface ShootingStars {
  tick: (timeMs: number) => void;
  dispose: () => void;
}

const POOL_SIZE = 3;
const TRAIL_LENGTH = 26;
const TRAIL_WIDTH = 0.55;

function createTrailTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 8;
  const ctx = canvas.getContext('2d')!;
  const grad = ctx.createLinearGradient(0, 0, 128, 0);
  grad.addColorStop(0, 'rgba(125, 211, 252, 0)');
  grad.addColorStop(0.7, 'rgba(186, 230, 253, 0.55)');
  grad.addColorStop(0.94, 'rgba(255, 255, 255, 0.95)');
  grad.addColorStop(1, 'rgba(255, 255, 255, 1)');
  ctx.fillStyle = grad;
  ctx.fillRect(0, 0, 128, 8);
  return new THREE.CanvasTexture(canvas);
}

interface StarState {
  mesh: THREE.Mesh;
  material: THREE.MeshBasicMaterial;
  active: boolean;
  bornAt: number;
  duration: number;
  start: THREE.Vector3;
  dir: THREE.Vector3;
  speed: number;
}

const X_AXIS = new THREE.Vector3(1, 0, 0);

export function buildShootingStars(scene: THREE.Scene): ShootingStars {
  const texture = createTrailTexture();
  const geometry = new THREE.PlaneGeometry(TRAIL_LENGTH, TRAIL_WIDTH);
  const stars: StarState[] = [];

  for (let i = 0; i < POOL_SIZE; i++) {
    const material = new THREE.MeshBasicMaterial({
      map: texture,
      transparent: true,
      opacity: 0,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
    });
    const mesh = new THREE.Mesh(geometry, material);
    mesh.visible = false;
    mesh.frustumCulled = false;
    scene.add(mesh);
    stars.push({
      mesh,
      material,
      active: false,
      bornAt: 0,
      duration: 0,
      start: new THREE.Vector3(),
      dir: new THREE.Vector3(),
      speed: 0,
    });
  }

  let nextSpawnAt = 0;

  function spawn(nowMs: number): void {
    const star = stars.find((s) => !s.active);
    if (!star) return;

    // 出生点：远景上半球壳，划向斜下方
    const theta = Math.random() * Math.PI * 2;
    const r = 150 + Math.random() * 80;
    star.start.set(
      Math.cos(theta) * r,
      45 + Math.random() * 70,
      Math.sin(theta) * r * 0.7,
    );
    star.dir.set(
      (Math.random() - 0.5) * 1.6,
      -(0.5 + Math.random() * 0.5),
      (Math.random() - 0.5) * 1.6,
    ).normalize();
    star.speed = 110 + Math.random() * 70;
    star.duration = 1.0 + Math.random() * 0.6;
    star.bornAt = nowMs;
    star.active = true;
    star.mesh.visible = true;
    star.mesh.quaternion.setFromUnitVectors(X_AXIS, star.dir);
  }

  return {
    tick(timeMs: number) {
      if (nextSpawnAt === 0) nextSpawnAt = timeMs + 4000 + Math.random() * 8000;
      if (timeMs >= nextSpawnAt) {
        spawn(timeMs);
        nextSpawnAt = timeMs + 8000 + Math.random() * 12000;
      }
      for (const star of stars) {
        if (!star.active) continue;
        const age = (timeMs - star.bornAt) * 0.001;
        const t = age / star.duration;
        if (t >= 1) {
          star.active = false;
          star.mesh.visible = false;
          star.material.opacity = 0;
          continue;
        }
        star.mesh.position.copy(star.start).addScaledVector(star.dir, star.speed * age);
        // flare-and-fade：快速点亮 → 缓慢熄灭
        star.material.opacity = Math.sin(Math.min(t, 1) * Math.PI) * 0.85;
      }
    },
    dispose() {
      for (const star of stars) {
        scene.remove(star.mesh);
        star.material.dispose();
      }
      geometry.dispose();
      texture.dispose();
    },
  };
}
