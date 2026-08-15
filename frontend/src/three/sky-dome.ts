import * as THREE from 'three';
import { planetNoiseCommon } from './shaders/planet-noise.glsl';

/**
 * 程序化深空天穹：单个 BackSide 大球一次 draw 画出
 * 垂直深空渐变 + 斜向 FBM 银河带（含暗尘埃缝）+ 大尺度星云斑。
 * 全程序化无纹理资源，替代纯色 scene.background。
 */
export interface SkyDome {
  mesh: THREE.Mesh;
  tick: (timeMs: number) => void;
  dispose: () => void;
}

const skyVertex = /* glsl */ `
varying vec3 vDir;
void main() {
  vDir = position;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const skyFragment = /* glsl */ `
uniform float uTime;
varying vec3 vDir;

${planetNoiseCommon}

void main() {
  vec3 d = normalize(vDir);

  // 深空垂直渐变：底部微蓝、顶部更深
  vec3 sky = mix(vec3(0.014, 0.022, 0.06), vec3(0.028, 0.04, 0.105), smoothstep(-0.65, 0.4, -abs(d.y) + 0.15));

  // 斜向银河带
  vec3 bandNormal = normalize(vec3(0.35, 0.85, 0.4));
  vec3 bandTangent = normalize(cross(bandNormal, vec3(0.0, 0.0, 1.0)));
  float bandCoord = dot(d, bandNormal);
  float along = dot(d, bandTangent);
  float band = exp(-pow(bandCoord * 4.6, 2.0));

  // FBM 低频形体 + 暗尘埃缝（带心一条被吸收的暗缝，银河才不是均匀光带）
  vec3 q = d * 3.4 + vec3(uTime * 0.0035, 0.0, uTime * 0.002);
  float structure = fbm(q) * 0.5 + 0.5;
  float dust = smoothstep(0.38, 0.78, fbm2(d * 6.0 + 3.7) * 0.5 + 0.5);
  float lane = exp(-pow(bandCoord * 10.0, 2.0)) * dust;
  float milky = band * (0.35 + structure * 0.8) * (1.0 - lane * 0.85);

#ifdef SKY_RICH
  // 高频 ridged 丝缕：让银河出现纤维状气体结构
  float fil = ridged2(d * 7.5 + 5.0);
  milky *= 0.72 + 0.55 * fil;
#endif

  // 沿带蓝 → 紫 → 粉（沿用学习区既有色带）
  float t = clamp(along * 0.5 + 0.5, 0.0, 1.0);
  vec3 c1 = vec3(0.055, 0.40, 0.91);
  vec3 c2 = vec3(0.75, 0.52, 0.99);
  vec3 c3 = vec3(0.93, 0.28, 0.60);
  vec3 bandColor = t < 0.5 ? mix(c1, c2, t * 2.0) : mix(c2, c3, (t - 0.5) * 2.0);
  vec3 col = sky + bandColor * milky * 0.32;

  // 银心增亮：带的一端出现暖色亮核（Sagittarius core），另一端冷色渐弱
  float core = exp(-pow((along - 0.58) * 2.8, 2.0)) * band;
  col += vec3(1.0, 0.78, 0.5) * core * (0.16 + 0.1 * structure);
  col *= 1.0 - smoothstep(0.2, -0.9, along) * 0.18 * band;

  // 远处大尺度星云斑
  float neb = smoothstep(0.55, 0.95, fbm2(d * 2.2 + 11.0) * 0.5 + 0.5);
  col += vec3(0.28, 0.32, 0.62) * neb * 0.05;

#ifdef SKY_RICH
  // 双团域扭曲彩斑（蓝紫 / 品红），缓慢漂移，给远离银河带的天区补层次
  vec3 wp = domainWarp(d * 1.8 + vec3(uTime * 0.002, 0.0, 0.0), 0.55);
  float p1 = smoothstep(0.52, 0.92, fbm2(wp + 17.0) * 0.5 + 0.5);
  float p2 = smoothstep(0.55, 0.95, fbm2(wp * 1.3 - 9.0) * 0.5 + 0.5);
  col += vec3(0.36, 0.30, 0.85) * p1 * 0.06;
  col += vec3(0.85, 0.25, 0.55) * p2 * 0.045;
#endif

  gl_FragColor = vec4(col, 1.0);
}
`;

/** 银河带的法向，供背景星层按带做密度偏置时对齐（与 fragment 内 bandNormal 一致） */
export const SKY_BAND_NORMAL = new THREE.Vector3(0.35, 0.85, 0.4).normalize();

export function buildSkyDome(scene: THREE.Scene, lowPower = false): SkyDome {
  const defines: Record<string, number | string> = { FBM_OCTAVES: lowPower ? 2 : 3 };
  if (!lowPower) defines.SKY_RICH = 1;
  const material = new THREE.ShaderMaterial({
    defines,
    uniforms: { uTime: { value: 0 } },
    vertexShader: skyVertex,
    fragmentShader: skyFragment,
    side: THREE.BackSide,
    depthWrite: false,
    fog: false,
  });

  const mesh = new THREE.Mesh(new THREE.SphereGeometry(560, lowPower ? 32 : 48, lowPower ? 24 : 32), material);
  mesh.renderOrder = -10;
  mesh.frustumCulled = false;
  scene.add(mesh);

  return {
    mesh,
    tick(timeMs: number) {
      material.uniforms.uTime.value = timeMs * 0.001;
    },
    dispose() {
      scene.remove(mesh);
      mesh.geometry.dispose();
      material.dispose();
    },
  };
}
