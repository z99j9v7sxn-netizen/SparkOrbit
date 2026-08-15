export const particleFieldVertex = /* glsl */ `
attribute float aSize;
attribute float aPhase;
attribute float aDepth;

uniform float uTime;
uniform vec2 uPointer;
uniform float uPixelRatio;

varying vec3 vColor;
varying float vAlpha;

void main() {
  vec3 pos = position;
  float drift = sin(uTime * 0.045 + aPhase) * 2.2;
  pos.x += drift * cos(aPhase * 1.7);
  pos.y += sin(uTime * 0.038 + aPhase * 1.15) * 1.6;
  pos.z += drift * sin(aPhase * 1.3);
  pos += vec3(uPointer.x * aDepth * 0.9, uPointer.y * aDepth * 0.55, uPointer.x * aDepth * 0.15);

  vec4 mvPosition = modelViewMatrix * vec4(pos, 1.0);
  gl_Position = projectionMatrix * mvPosition;

  float depthFactor = clamp(1.0 + mvPosition.z * 0.006, 0.35, 2.4);
  gl_PointSize = aSize * uPixelRatio * depthFactor * (130.0 / -mvPosition.z);
  vAlpha = 0.18 + 0.32 * sin(uTime * 0.55 + aPhase) + aDepth * 0.22;
  vColor = color;
}
`;

export const particleFieldFragment = /* glsl */ `
varying vec3 vColor;
varying float vAlpha;

void main() {
  vec2 uv = gl_PointCoord - 0.5;
  float dist = length(uv);
  float core = smoothstep(0.5, 0.0, dist);
  float glow = pow(core, 1.6);
  float alpha = glow * vAlpha;
  if (alpha < 0.012) discard;
  gl_FragColor = vec4(vColor * (0.5 + glow * 0.5), alpha * 0.72);
}
`;
