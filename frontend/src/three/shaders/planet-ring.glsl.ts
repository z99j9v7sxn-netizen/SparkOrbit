import { planetNoiseCommon } from './planet-noise.glsl';

/**
 * 行星环带：程序化细密条纹 + 颗粒感，并接收球体投在环面上的本影。
 * 几何体 uv.x 已被重映射为「归一化半径」。
 */
export const planetRingVertex = /* glsl */ `
varying vec3 vObj;
varying vec3 vWorldPos;
varying float vRadial;

void main() {
  vObj = position;
  vRadial = uv.x;
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPos = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

export const planetRingFragment = /* glsl */ `
uniform mat4 modelMatrix;

uniform vec3 uColor;
uniform vec3 uSunPos;
uniform vec3 uSunColor;
uniform vec3 uSeed;
uniform float uOpacity;
uniform float uPlanetRadius;
uniform float uSaturation;

varying vec3 vObj;
varying vec3 vWorldPos;
varying float vRadial;

${planetNoiseCommon}

void main() {
  float coarse = snoise(vec3(vRadial * 26.0 + uSeed.x, 0.0, 0.0)) * 0.5 + 0.5;
  float fine = snoise(vec3(vRadial * 88.0 + uSeed.y, 3.7, 0.0)) * 0.5 + 0.5;
  float density = smoothstep(0.16, 0.60, coarse * 0.68 + fine * 0.32);

  // 卡西尼缝
  density *= 1.0 - 0.9 * smoothstep(0.035, 0.0, abs(vRadial - 0.42));
  // 内外边界羽化
  density *= smoothstep(0.0, 0.07, vRadial) * smoothstep(1.0, 0.88, vRadial);

  float angle = atan(vObj.y, vObj.x);
  float grain = snoise(vec3(vRadial * 190.0 + uSeed.z, angle * 22.0, 0.0)) * 0.5 + 0.5;
  density *= 0.72 + 0.52 * grain;
  if (density < 0.01) discard;

  vec3 V = normalize(cameraPosition - vWorldPos);
  vec3 L = normalize(uSunPos - vWorldPos);
  vec3 center = modelMatrix[3].xyz;
  vec3 rel = vWorldPos - center;

  // 球体本影：从环面点朝太阳的射线是否被星球挡住
  float along = -dot(rel, L);
  float missDistance = length(rel + L * along);
  float occluded = step(0.0, along) * smoothstep(uPlanetRadius * 1.12, uPlanetRadius * 0.82, missDistance);

  vec3 ringNormal = normalize(mat3(modelMatrix) * vec3(0.0, 0.0, 1.0));
  float grazing = 1.0 - abs(dot(ringNormal, V));
  float facing = 0.35 + 0.65 * abs(dot(ringNormal, L));

  vec3 color = uColor * (0.55 + 0.75 * grain) * facing;
  color += uSunColor * pow(grazing, 3.0) * 0.25;
  color = mix(color * 0.18, color, 1.0 - occluded * 0.85);
  float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
  color = mix(vec3(luma), color, uSaturation);

  float alpha = density * uOpacity * (0.45 + 0.7 * grazing) * (1.0 - occluded * 0.35);

  gl_FragColor = vec4(color, clamp(alpha, 0.0, 1.0));

  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
`;
