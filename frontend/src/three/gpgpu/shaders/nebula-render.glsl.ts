/**
 * 渲染 shader：从 GPGPU 位置纹理读取粒子位置，软粒子加色混合，
 * 视觉风格延续既有 nebula-particles（径向辉光 + softness 调制）。
 */

export const nebulaRenderVertex = /* glsl */ `
uniform sampler2D uPositions;
uniform sampler2D uVelocities;
uniform float uPixelRatio;
uniform float uTime;
uniform float uHoverCluster;   // -1 无悬停
uniform float uGlobalFade;     // 全局亮度（dimmed / 转场淡出）

attribute vec2 aUv;
attribute vec3 aColor;
attribute float aSize;
attribute float aCluster;
attribute float aSoftness;
attribute float aPhase;

varying vec3 vColor;
varying float vAlpha;
varying float vSoftness;

void main() {
  vec3 pos = texture2D(uPositions, aUv).xyz;
  vec3 vel = texture2D(uVelocities, aUv).xyz;
  float speed = length(vel);

  bool isHovered = uHoverCluster >= 0.0 && abs(aCluster - uHoverCluster) < 0.5;
  float hoverBoost = isHovered ? 1.0 : 0.0;
  // 悬停时其余簇微暗，环境粒子保持
  float dimOthers = (uHoverCluster >= 0.0 && !isHovered && aCluster >= 0.0) ? 0.45 : 1.0;

  // 高速粒子增亮，形成流动/尾迹的能量感（封顶防止加色混合过曝）
  vColor = aColor * (1.0 + hoverBoost * 0.4 + min(speed * 0.06, 0.3));
  vSoftness = aSoftness;

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  gl_Position = projectionMatrix * mvPosition;

  float size = aSize * (1.0 + hoverBoost * 0.35);
  gl_PointSize = size * uPixelRatio * (95.0 / max(1.0, -mvPosition.z));

  float twinkle = 0.24 + 0.12 * sin(uTime * 0.75 + aPhase);
  vAlpha = (twinkle + hoverBoost * 0.3) * dimOthers * uGlobalFade;
}
`;

export const nebulaRenderFragment = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;
varying float vSoftness;

void main() {
  vec2 uv = gl_PointCoord - 0.5;
  float dist = length(uv);
  float power = mix(1.2, 2.4, vSoftness);
  float core = smoothstep(0.5, 0.0, dist);
  float glow = pow(core, power);
  float alpha = glow * vAlpha * mix(0.75, 0.45, vSoftness);
  if (alpha < 0.015) discard;
  gl_FragColor = vec4(vColor * (0.55 + glow * 0.45), alpha);
}
`;
