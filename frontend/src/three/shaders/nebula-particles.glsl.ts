export const nebulaParticleVertex = /* glsl */ `
attribute float aSize;
attribute float aPhase;
attribute float aSoftness;

uniform float uTime;
uniform float uPixelRatio;

varying vec3 vColor;
varying float vAlpha;
varying float vSoftness;

void main() {
  vColor = color;
  vSoftness = aSoftness;
  vec3 pos = position;
  pos.x += sin(uTime * 0.12 + aPhase) * 0.55;
  pos.y += cos(uTime * 0.1 + aPhase * 1.3) * 0.45;
  pos.z += sin(uTime * 0.08 + aPhase * 0.7) * 0.35;

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  gl_PointSize = aSize * uPixelRatio * (200.0 / -mvPosition.z);
  vAlpha = 0.32 + 0.28 * sin(uTime * 0.7 + aPhase);
}
`;

export const nebulaParticleFragment = /* glsl */ `
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
