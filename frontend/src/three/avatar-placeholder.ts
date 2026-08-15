import * as THREE from 'three';
import { disposeObject3D } from './dispose';

export type TutorPresetId = 'orbit' | 'mentor' | 'coach';

export const TUTOR_PRESETS: Array<{
  id: TutorPresetId;
  label: string;
  hint: string;
}> = [
  { id: 'orbit', label: '星轨讲师', hint: '青蓝全息' },
  { id: 'mentor', label: '温和学姐', hint: '暖紫柔和' },
  { id: 'coach', label: '硬核学长', hint: '深灰琥珀' },
];

export interface AvatarNode {
  root: THREE.Group;
  head: THREE.Mesh;
  mouth: THREE.Mesh;
  isSpeaking: boolean;
  phase: number;
  preset: TutorPresetId;
}

type PresetPalette = {
  body: number;
  head: number;
  accent: number;
  mouth: number;
  holo: number;
  eye: number;
  hair?: number;
};

const PALETTES: Record<TutorPresetId, PresetPalette> = {
  orbit: {
    body: 0x3b82f6,
    head: 0xfca5a5,
    accent: 0x38bdf8,
    mouth: 0x9f1239,
    holo: 0x38bdf8,
    eye: 0x1e293b,
  },
  mentor: {
    body: 0xa78bfa,
    head: 0xfed7aa,
    accent: 0xf9a8d4,
    mouth: 0xbe185d,
    holo: 0xe879f9,
    eye: 0x4c1d95,
    hair: 0x7c3aed,
  },
  coach: {
    body: 0x334155,
    head: 0xd6b48c,
    accent: 0xf59e0b,
    mouth: 0x7c2d12,
    holo: 0xfbbf24,
    eye: 0x0f172a,
    hair: 0x1e293b,
  },
};

export function buildAvatarPlaceholder(preset: TutorPresetId = 'orbit'): AvatarNode {
  const palette = PALETTES[preset] || PALETTES.orbit;
  const root = new THREE.Group();

  const bodyGeo = new THREE.CylinderGeometry(
    preset === 'coach' ? 0.45 : 0.38,
    preset === 'mentor' ? 0.55 : 0.62,
    preset === 'coach' ? 1.55 : 1.45,
    32,
  );
  const bodyMat = new THREE.MeshStandardMaterial({
    color: palette.body,
    roughness: preset === 'coach' ? 0.45 : 0.7,
    metalness: preset === 'orbit' ? 0.35 : 0.15,
  });
  const body = new THREE.Mesh(bodyGeo, bodyMat);
  body.position.y = -0.75;
  root.add(body);

  // Shoulder badge / collar accent
  const collarGeo = new THREE.TorusGeometry(0.42, 0.045, 8, 24);
  const collarMat = new THREE.MeshStandardMaterial({
    color: palette.accent,
    roughness: 0.4,
    metalness: 0.5,
  });
  const collar = new THREE.Mesh(collarGeo, collarMat);
  collar.rotation.x = Math.PI / 2;
  collar.position.y = -0.05;
  root.add(collar);

  const headGeo = new THREE.SphereGeometry(preset === 'coach' ? 0.58 : 0.56, 32, 32);
  const headMat = new THREE.MeshStandardMaterial({
    color: palette.head,
    roughness: 0.5,
  });
  const head = new THREE.Mesh(headGeo, headMat);
  head.position.y = 0.5;
  root.add(head);

  if (palette.hair) {
    const hairGeo =
      preset === 'mentor'
        ? new THREE.SphereGeometry(0.58, 24, 24, 0, Math.PI * 2, 0, Math.PI * 0.55)
        : new THREE.CylinderGeometry(0.5, 0.52, 0.28, 16);
    const hairMat = new THREE.MeshStandardMaterial({ color: palette.hair, roughness: 0.85 });
    const hair = new THREE.Mesh(hairGeo, hairMat);
    hair.position.y = preset === 'mentor' ? 0.72 : 0.78;
    if (preset === 'coach') hair.position.y = 0.82;
    root.add(hair);
  }

  const eyeGeo = new THREE.SphereGeometry(0.09, 16, 16);
  const eyeMat = new THREE.MeshBasicMaterial({ color: palette.eye });
  const leftEye = new THREE.Mesh(eyeGeo, eyeMat);
  leftEye.position.set(-0.22, 0.08, 0.48);
  head.add(leftEye);
  const rightEye = new THREE.Mesh(eyeGeo, eyeMat);
  rightEye.position.set(0.22, 0.08, 0.48);
  head.add(rightEye);

  const mouthGeo = new THREE.BoxGeometry(0.28, 0.05, 0.1);
  const mouthMat = new THREE.MeshBasicMaterial({ color: palette.mouth });
  const mouth = new THREE.Mesh(mouthGeo, mouthMat);
  mouth.position.set(0, -0.2, 0.52);
  head.add(mouth);

  const holoGeo = new THREE.CylinderGeometry(0.7, 0.9, 3, 32, 1, true);
  const holoMat = new THREE.MeshBasicMaterial({
    color: palette.holo,
    transparent: true,
    opacity: preset === 'orbit' ? 0.18 : 0.12,
    side: THREE.DoubleSide,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const holo = new THREE.Mesh(holoGeo, holoMat);
  holo.position.y = -0.5;
  root.add(holo);

  return { root, head, mouth, isSpeaking: false, phase: 0, preset };
}

export function updateAvatarLipsync(avatar: AvatarNode, time: number) {
  if (!avatar) return;

  avatar.head.position.y = 0.5 + Math.sin(time * 0.002) * 0.03;

  if (avatar.isSpeaking) {
    avatar.phase += 0.3;
    const amplitude = Math.abs(Math.sin(avatar.phase)) * 2.5 + 0.5;
    avatar.mouth.scale.y = amplitude;
    avatar.mouth.scale.x = 1.0 + amplitude * 0.2;
  } else {
    avatar.mouth.scale.y = THREE.MathUtils.lerp(avatar.mouth.scale.y, 1.0, 0.2);
    avatar.mouth.scale.x = THREE.MathUtils.lerp(avatar.mouth.scale.x, 1.0, 0.2);
    avatar.phase = 0;
  }
}

export function disposeAvatar(avatar: AvatarNode | null) {
  if (!avatar) return;
  disposeObject3D(avatar.root);
  avatar.root.parent?.remove(avatar.root);
}
