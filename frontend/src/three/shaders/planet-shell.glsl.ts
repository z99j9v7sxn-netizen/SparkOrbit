export const planetShellVertex = /* glsl */ `
attribute float aPhase;
attribute float aSize;

uniform float uTime;
uniform float uHover;
uniform float uBaseRadius;
uniform float uPixelRatio;

varying float vAlpha;

void main() {
  vec3 dir = normalize(position);
  float breathe = sin(uTime * 1.15 + aPhase) * 0.035;
  float ripple = uHover * sin(uTime * 4.2 - aPhase * 2.8) * 0.14;
  vec3 pos = dir * (uBaseRadius + breathe + ripple);

  vAlpha = 0.32 + 0.22 * sin(uTime * 0.75 + aPhase) + uHover * 0.28;

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  gl_Position = projectionMatrix * mvPosition;
  gl_PointSize = aSize * uPixelRatio * (170.0 / -mvPosition.z);
}
`;

export const planetShellFragment = /* glsl */ `
uniform vec3 uColor;

varying float vAlpha;

void main() {
  vec2 uv = gl_PointCoord - 0.5;
  float dist = length(uv);
  float glow = smoothstep(0.5, 0.0, dist);
  float alpha = glow * vAlpha;
  if (alpha < 0.02) discard;
  gl_FragColor = vec4(uColor * (0.55 + glow * 0.65), alpha);
}
`;
