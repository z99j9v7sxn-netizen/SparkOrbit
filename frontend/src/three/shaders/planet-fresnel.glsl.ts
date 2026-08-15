export const planetFresnelVertex = /* glsl */ `
varying vec3 vNormal;
varying vec3 vViewPosition;

void main() {
  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);
  vViewPosition = -mvPosition.xyz;
  vNormal = normalize(normalMatrix * normal);
  gl_Position = projectionMatrix * mvPosition;
}
`;

export const planetFresnelFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uIntensity;
uniform float uPower;

varying vec3 vNormal;
varying vec3 vViewPosition;

void main() {
  vec3 normal = normalize(vNormal);
  vec3 viewDir = normalize(vViewPosition);
  float fresnel = pow(1.0 - abs(dot(normal, viewDir)), uPower);
  float alpha = fresnel * uIntensity;
  if (alpha < 0.008) discard;
  gl_FragColor = vec4(uColor * (0.45 + fresnel * 0.85), alpha);
}
`;
