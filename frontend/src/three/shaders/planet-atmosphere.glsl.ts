/**
 * 星球大气壳：BackSide 球壳上的伪散射。
 *
 * 与旧的纯 fresnel 描边相比，这里把太阳方向纳入计算：
 * 日侧边缘明亮偏冷、晨昏线附近厚重、逆光时在轮廓上出现一圈前向散射光弧、夜侧几乎消失。
 * 保留 uIntensity 命名，悬停高亮仍可直接 tween 该 uniform。
 */
export const planetAtmosphereVertex = /* glsl */ `
varying vec3 vWorldPos;

void main() {
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPos = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

export const planetAtmosphereFragment = /* glsl */ `
uniform mat4 modelMatrix;

uniform vec3 uColor;
uniform vec3 uSunPos;
uniform float uIntensity;
uniform float uPower;
uniform float uSaturation;

varying vec3 vWorldPos;

void main() {
  vec3 center = modelMatrix[3].xyz;
  vec3 viewDir = normalize(vWorldPos - cameraPosition);
  // BackSide 渲染取到的是远侧壳面，沿视线镜像回近侧，昼夜朝向才与地表一致
  vec3 N = reflect(normalize(vWorldPos - center), viewDir);
  vec3 V = -viewDir;
  vec3 L = normalize(uSunPos - center);

  float fresnel = pow(1.0 - abs(dot(N, V)), uPower);
  float lit = smoothstep(-0.45, 0.32, dot(N, L));
  float towardSun = max(dot(-V, L), 0.0);
  float halo = pow(fresnel, 1.35) * pow(towardSun, 2.5);

  float alpha = uIntensity * (fresnel * (0.14 + 0.9 * lit) + halo * 0.7);
  if (alpha < 0.006) discard;

  vec3 tint = mix(uColor * 0.35, uColor * 0.95 + vec3(0.03, 0.05, 0.08), lit);
  vec3 color = tint * (0.4 + fresnel * 0.75);
  float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
  color = mix(vec3(luma), color, uSaturation);

  gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));
}
`;
