export const filmGrainVertex = /* glsl */ `
varying vec2 vUv;

void main() {
  vUv = uv;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

export const filmGrainFragment = /* glsl */ `
uniform sampler2D tDiffuse;
uniform float uSeed;
uniform float uIntensity;

varying vec2 vUv;

// 整数型哈希（PCG 变体）：无 sin 干涉条纹，逐像素独立
float hash(vec2 p, float seed) {
  uvec2 q = uvec2(ivec2(p)) * uvec2(1597334673u, 3812015801u);
  uint n = (q.x ^ q.y ^ uint(seed * 4096.0)) * 1597334673u;
  n = (n ^ (n >> 16)) * 2246822519u;
  n = n ^ (n >> 13);
  return float(n) * (1.0 / 4294967295.0);
}

void main() {
  vec4 color = texture2D(tDiffuse, vUv);
  float grain = hash(gl_FragCoord.xy, uSeed) * 2.0 - 1.0;
  // 亮部噪点弱、暗部稍强，避免高光区闪烁
  float luma = dot(color.rgb, vec3(0.299, 0.587, 0.114));
  color.rgb += grain * uIntensity * (1.0 - luma * 0.6);
  gl_FragColor = color;
}
`;
