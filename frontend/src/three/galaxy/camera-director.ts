import * as THREE from 'three';
import gsap from 'gsap';

export interface CameraDirector {
  /** 每帧调用：基位 + 待机漂移 + 指针视差合成相机位姿 */
  update: (nowMs: number, pointer: { x: number; y: number }) => void;
  /** 入场：相机从远处推入基位 */
  playIntro: (short?: boolean) => void;
  /** 飞入簇心，resolve 时机 = 镜头到位（可切换分区） */
  flyTo: (target: THREE.Vector3) => Promise<void>;
  /** 从簇内拉回星系全景 */
  flyBack: () => Promise<void>;
  readonly flying: boolean;
  dispose: () => void;
}

const HOME_POS = new THREE.Vector3(0, 5, 26);
const HOME_LOOK = new THREE.Vector3(0, 0.4, 0);

export function createCameraDirector(camera: THREE.PerspectiveCamera): CameraDirector {
  const basePos = HOME_POS.clone();
  const lookAt = HOME_LOOK.clone();
  const parallaxCur = new THREE.Vector2(0, 0);
  let flying = false;
  let timelines: gsap.core.Timeline[] = [];

  function killTimelines(): void {
    timelines.forEach((tl) => tl.kill());
    timelines = [];
  }

  return {
    get flying() {
      return flying;
    },

    update(nowMs: number, pointer: { x: number; y: number }) {
      const t = nowMs * 0.001;
      // 指针视差带惯性（飞行中减弱避免打架）
      const damp = flying ? 0.15 : 1;
      parallaxCur.x += (pointer.x * 1.6 * damp - parallaxCur.x) * 0.045;
      parallaxCur.y += (pointer.y * 1.0 * damp - parallaxCur.y) * 0.045;
      // 待机缓慢漂移
      const driftX = Math.sin(t * 0.07) * 0.7 * (flying ? 0.2 : 1);
      const driftY = Math.cos(t * 0.05) * 0.45 * (flying ? 0.2 : 1);

      camera.position.set(
        basePos.x + parallaxCur.x + driftX,
        basePos.y + parallaxCur.y + driftY,
        basePos.z,
      );
      camera.lookAt(lookAt);
    },

    playIntro(short = false) {
      killTimelines();
      basePos.copy(HOME_POS).z += short ? 10 : 26;
      basePos.y += short ? 2 : 6;
      lookAt.copy(HOME_LOOK);
      const tl = gsap.timeline();
      tl.to(basePos, {
        x: HOME_POS.x,
        y: HOME_POS.y,
        z: HOME_POS.z,
        duration: short ? 1.4 : 2.6,
        ease: 'power3.out',
      });
      timelines.push(tl);
    },

    flyTo(target: THREE.Vector3) {
      killTimelines();
      flying = true;
      // 停在簇心稍前方，再穿越过去，营造「冲进星云」的两段式镜头
      const dir = target.clone().sub(basePos).normalize();
      const approach = target.clone().sub(dir.clone().multiplyScalar(4.5));
      const through = target.clone().add(dir.clone().multiplyScalar(2.0));

      return new Promise<void>((resolve) => {
        const tl = gsap.timeline({
          onComplete: () => {
            flying = false;
            resolve();
          },
        });
        tl.to(basePos, {
          x: approach.x,
          y: approach.y,
          z: approach.z,
          duration: 1.05,
          ease: 'power2.in',
        }, 0);
        tl.to(lookAt, {
          x: target.x,
          y: target.y,
          z: target.z,
          duration: 0.9,
          ease: 'power2.inOut',
        }, 0);
        tl.to(basePos, {
          x: through.x,
          y: through.y,
          z: through.z,
          duration: 0.55,
          ease: 'power2.out',
        }, '>');
        timelines.push(tl);
      });
    },

    flyBack() {
      killTimelines();
      flying = true;
      return new Promise<void>((resolve) => {
        const tl = gsap.timeline({
          onComplete: () => {
            flying = false;
            resolve();
          },
        });
        tl.to(basePos, {
          x: HOME_POS.x,
          y: HOME_POS.y,
          z: HOME_POS.z,
          duration: 1.5,
          ease: 'power3.inOut',
        }, 0);
        tl.to(lookAt, {
          x: HOME_LOOK.x,
          y: HOME_LOOK.y,
          z: HOME_LOOK.z,
          duration: 1.3,
          ease: 'power2.inOut',
        }, 0);
        timelines.push(tl);
      });
    },

    dispose() {
      killTimelines();
    },
  };
}
