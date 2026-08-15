import { planetNoiseCommon } from './planet-noise.glsl';

/**
 * 云层壳：与地表共用 cloudDensity 表达式，
 * 因此地表 shader 里以同一 seed/coverage 采样即可得到对齐的云影。
 */
export const planetCloudsVertex = /* glsl */ `
varying vec3 vDir;
varying vec3 vWorldPos;

void main() {
  vDir = normalize(position);
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPos = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

export const planetCloudsFragment = /* glsl */ `
uniform mat4 modelMatrix;

uniform float uTime;
uniform vec3 uSunPos;
uniform vec3 uSunColor;
uniform vec3 uSeed;
uniform vec3 uTint;
uniform float uCoverage;
uniform float uOpacity;
uniform float uSaturation;

varying vec3 vDir;
varying vec3 vWorldPos;

${planetNoiseCommon}

void main() {
  vec3 d = normalize(vDir);
  float density = cloudDensity(d, uSeed, uCoverage, uTime);
  if (density < 0.012) discard;

  vec3 N = normalize(mat3(modelMatrix) * d);
  vec3 L = normalize(uSunPos - vWorldPos);
  vec3 V = normalize(cameraPosition - vWorldPos);

  float ndl = dot(N, L);
  float day = smoothstep(-0.14, 0.34, ndl);
  // 云顶受光、云底偏冷，加一点前向散射让晨昏线附近的云边发亮
  float scatter = pow(max(dot(-V, L), 0.0), 3.0) * (1.0 - day) * 0.6;

  vec3 color = mix(uTint * 0.14, uTint * 0.72, day) * (0.35 + 0.5 * day);
  color += uSunColor * scatter * 0.28;
  float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
  color = mix(vec3(luma), color, uSaturation);

  // 边缘渐隐，避免球壳在轮廓处切出硬边
  float limb = smoothstep(0.0, 0.32, dot(N, V));
  float alpha = density * uOpacity * (0.30 + 0.70 * limb) * (0.22 + 0.78 * day);
  if (alpha < 0.004) discard;

  gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));

  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
`;
