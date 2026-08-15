import { planetNoiseCommon } from './planet-noise.glsl';

/**
 * 星球地表 uber shader。
 *
 * defines:
 *  - ARCH_GASGIANT / ARCH_LAVA / ARCH_ICE / ARCH_ROCKY / ARCH_STORM，均未定义时为类地
 *  - FBM_OCTAVES：分形倍频数
 *  - USE_BUMP：开启法线扰动
 *  - USE_CLOUD_SHADOW：开启云影
 */
export const planetSurfaceVertex = /* glsl */ `
varying vec3 vDir;
varying vec3 vWorldPos;

void main() {
  vDir = normalize(position);
  vec4 worldPos = modelMatrix * vec4(position, 1.0);
  vWorldPos = worldPos.xyz;
  gl_Position = projectionMatrix * viewMatrix * worldPos;
}
`;

export const planetSurfaceFragment = /* glsl */ `
// three 只在顶点前缀里声明 modelMatrix，片元里需自行声明后由渲染器自动绑定
uniform mat4 modelMatrix;

uniform float uTime;
uniform vec3 uSunPos;
uniform vec3 uSunColor;
uniform float uAmbient;

uniform vec3 uBaseColor;
uniform vec3 uAccentColor;
uniform vec3 uAtmoColor;
uniform vec3 uSeed;
uniform float uStripeFreq;
uniform float uBump;

uniform vec3 uCloudSeed;
uniform float uCloudCoverage;

uniform float uSaturation;
uniform float uGlow;
uniform vec3 uOverlayColor;
uniform float uOverlayStrength;
uniform float uHover;
uniform float uPulse;
uniform float uNightLights;

varying vec3 vDir;
varying vec3 vWorldPos;

${planetNoiseCommon}

/** 廉价高度场，仅用于法线扰动的浮雕感 */
float bumpHeight(vec3 d) {
#if defined(ARCH_GASGIANT) || defined(ARCH_STORM)
  return fbm2(d * 5.0 + uSeed) * 0.5 + 0.5;
#elif defined(ARCH_LAVA)
  vec2 w = worley(d * 3.2 + uSeed);
  return (w.y - w.x) * 0.6 + fbm2(d * 6.0 + uSeed) * 0.4;
#elif defined(ARCH_ICE)
  return ridged2(d * 4.2 + uSeed);
#elif defined(ARCH_ROCKY)
  vec2 w = worley(d * 3.6 + uSeed);
  return smoothstep(0.0, 0.42, w.x) * 0.75 + fbm2(d * 7.0 + uSeed) * 0.25;
#else
  return ridged2(d * 4.6 + uSeed) * 0.62 + fbm2(d * 2.2 + uSeed) * 0.38;
#endif
}

/** 沿球面切平面做中心差分，得到扰动后的物体空间法线 */
vec3 perturbedNormal(vec3 d, float strength) {
  if (strength < 0.001) return d;
  vec3 up = mix(vec3(0.0, 1.0, 0.0), vec3(1.0, 0.0, 0.0), step(0.98, abs(d.y)));
  vec3 t = normalize(cross(up, d));
  vec3 b = cross(d, t);
  float eps = 0.02;
  float h0 = bumpHeight(d);
  float ht = bumpHeight(normalize(d + t * eps));
  float hb = bumpHeight(normalize(d + b * eps));
  vec3 grad = (t * (ht - h0) + b * (hb - h0)) / eps;
  return normalize(d - grad * strength);
}

void main() {
  vec3 d = normalize(vDir);

  vec3 albedo = uBaseColor;
  vec3 emissive = vec3(0.0);
  float gloss = 0.3;
  float specMask = 0.15;
  float bumpMask = 1.0;
  float cityMask = 0.0;

#if defined(ARCH_GASGIANT)
  float flow = uTime * 0.014;
  float turbulence = fbm(d * 2.1 + uSeed + vec3(flow, 0.0, 0.0)) * 0.6;
  float bands = sin(d.y * uStripeFreq * 3.6 + turbulence * 2.1 + uSeed.x) * 0.5 + 0.5;
  float fine = fbm(d * vec3(5.0, 13.0, 5.0) + uSeed + vec3(flow * 1.7, 0.0, 0.0)) * 0.5 + 0.5;
  float band = clamp(bands * 0.76 + fine * 0.24, 0.0, 1.0);
  albedo = mix(uBaseColor * 0.5, uAccentColor * 0.85, band);
  albedo = mix(albedo, vec3(0.88), smoothstep(0.86, 1.0, band) * 0.16);

  vec3 stormAxis = normalize(vec3(sin(uSeed.x * 2.3), 0.34, cos(uSeed.z * 1.9)));
  vec3 stretched = normalize(d * vec3(1.0, 2.2, 1.0));
  float stormDist = distance(stretched, normalize(stormAxis * vec3(1.0, 2.2, 1.0)));
  float storm = smoothstep(0.44, 0.05, stormDist);
  float swirl = sin(stormDist * 24.0 - uTime * 0.5 + turbulence * 3.0) * 0.5 + 0.5;
  albedo = mix(albedo, mix(vec3(0.80, 0.38, 0.26), vec3(0.96, 0.74, 0.50), swirl), storm * 0.8);
  gloss = 0.25;
  specMask = 0.10;
  bumpMask = 0.35;

#elif defined(ARCH_LAVA)
  vec2 w = worley(d * 3.2 + uSeed);
  float seam = 1.0 - smoothstep(0.0, 0.13, w.y - w.x);
  float molten = pow(seam, 1.5);
  float crust = fbm(d * 4.6 + uSeed) * 0.5 + 0.5;
  albedo = mix(vec3(0.07, 0.05, 0.05), vec3(0.20, 0.13, 0.11), crust) * (0.75 + uBaseColor * 0.5);
  float breath = 0.68 + 0.32 * sin(uTime * 1.3 + w.x * 11.0);
  vec3 lava = mix(vec3(1.0, 0.30, 0.04), vec3(1.0, 0.86, 0.42), molten * breath);
  emissive = lava * molten * (0.35 + 0.3 * breath);
  albedo = mix(albedo, lava * 0.5, molten * 0.55);
  gloss = 0.32;
  specMask = 0.18;

#elif defined(ARCH_ICE)
  vec2 w = worley(d * 2.4 + uSeed);
  float plate = smoothstep(0.0, 0.07, w.y - w.x);
  float frost = fbm(d * 6.2 + uSeed) * 0.5 + 0.5;
  float cracks = ridged(d * 3.4 + uSeed);
  albedo = mix(vec3(0.32, 0.44, 0.55), vec3(0.52, 0.62, 0.70), frost);
  albedo = mix(albedo * 0.6, albedo, plate);
  albedo = mix(albedo, albedo * (0.7 + 0.6 * cracks), 0.35);
  albedo = mix(albedo, uBaseColor * 0.7, 0.35);
  gloss = 0.92;
  specMask = 0.42;

#elif defined(ARCH_ROCKY)
  vec2 w = worley(d * 3.6 + uSeed);
  float basin = smoothstep(0.0, 0.34, w.x);
  float craterRim = 1.0 - smoothstep(0.0, 0.10, abs(w.x - 0.30));
  float dust = fbm(d * 5.4 + uSeed) * 0.5 + 0.5;
  float maria = smoothstep(0.54, 0.78, fbm(d * 1.5 + uSeed * 2.0) * 0.5 + 0.5);
  albedo = uBaseColor * (0.52 + dust * 0.55);
  albedo *= mix(0.70, 1.0, basin);
  albedo += vec3(0.07) * craterRim;
  albedo = mix(albedo, albedo * 0.55, maria);
  gloss = 0.05;
  specMask = 0.04;

#elif defined(ARCH_STORM)
  vec3 axis = normalize(vec3(sin(uSeed.x * 1.7), 1.15, cos(uSeed.z * 1.3)));
  vec3 tangentA = normalize(cross(axis, vec3(0.0, 0.0, 1.0) + vec3(0.001)));
  vec3 tangentB = cross(axis, tangentA);
  float angle = atan(dot(d, tangentB), dot(d, tangentA));
  float polar = acos(clamp(dot(d, axis), -1.0, 1.0));
  float churn = fbm(d * 2.4 + uSeed + vec3(uTime * 0.02, 0.0, 0.0));
  float spiral = sin(angle * 3.0 + polar * 8.5 - uTime * 0.45 + churn * 2.6) * 0.5 + 0.5;
  float body = fbm(d * 3.4 + uSeed * 1.3 + vec3(0.0, uTime * 0.015, 0.0)) * 0.5 + 0.5;
  float v = clamp(body * 0.5 + spiral * 0.5, 0.0, 1.0);
  v = smoothstep(0.18, 0.86, v);
  albedo = mix(uBaseColor * 0.22, uAccentColor * 0.66, v);
  albedo = mix(albedo, vec3(0.66, 0.67, 0.74), smoothstep(0.78, 1.0, v) * 0.5);
  // 气旋眼：螺旋槽处压暗，拉开层次
  albedo *= 0.72 + 0.42 * spiral;
  gloss = 0.2;
  specMask = 0.1;
  bumpMask = 0.5;

#else
  vec3 q = domainWarp(d * 1.5 + uSeed, 0.3);
  float elevation = fbm(q) * 0.5 + 0.5;
  elevation = elevation * 0.82 + ridged(q * 2.4) * 0.18;
  float sea = 0.52;
  float land = smoothstep(sea, sea + 0.03, elevation);
  float shore = 1.0 - smoothstep(sea + 0.02, sea + 0.16, elevation);

  vec3 deepWater = uBaseColor * 0.22;
  vec3 shallowWater = uBaseColor * 0.72 + vec3(0.02, 0.07, 0.13);
  vec3 ocean = mix(deepWater, shallowWater, smoothstep(sea - 0.13, sea, elevation));

  float relief = clamp((elevation - sea) / 0.32, 0.0, 1.0);
  float arid = fbm(d * 2.0 + uSeed * 1.7) * 0.5 + 0.5;
  vec3 lowland = uAccentColor;
  vec3 desert = mix(uAccentColor, vec3(0.78, 0.66, 0.42), 0.75);
  vec3 highland = mix(uAccentColor, vec3(0.40, 0.32, 0.24), 0.72);
  vec3 ground = mix(lowland, desert, smoothstep(0.52, 0.82, arid) * (1.0 - smoothstep(0.5, 0.8, abs(d.y))));
  ground = mix(ground, highland, smoothstep(0.16, 0.58, relief));
  ground = mix(ground, vec3(0.74, 0.76, 0.80), smoothstep(0.70, 0.94, relief));

  albedo = mix(ocean, ground, land);
  float capNoise = fbm(d * 3.6 + uSeed) * 0.10;
  float cap = smoothstep(0.74, 0.90, abs(d.y) + capNoise);
  albedo = mix(albedo, vec3(0.80, 0.84, 0.88), cap);

  gloss = mix(0.95, 0.16, land);
  specMask = mix(0.9, 0.06, land) * (1.0 - cap * 0.55);
  bumpMask = land * (1.0 - cap * 0.6);
  cityMask = smoothstep(0.30, 0.66, snoise(d * 34.0 + uSeed * 3.0)) * land * (1.0 - cap) * (0.35 + 0.65 * shore);
#endif

#ifdef USE_BUMP
  vec3 nObj = perturbedNormal(d, uBump * bumpMask);
#else
  vec3 nObj = d;
#endif

  mat3 modelRot = mat3(modelMatrix);
  vec3 N = normalize(modelRot * nObj);
  vec3 L = normalize(uSunPos - vWorldPos);
  vec3 V = normalize(cameraPosition - vWorldPos);

  float ndl = dot(N, L);
  float day = smoothstep(-0.18, 0.30, ndl);
  float wrapped = clamp((ndl + 0.22) / 1.22, 0.0, 1.0);
  // 略微收紧晨昏线，但保留环境光下限，夜面仍能看清、可点击
  wrapped *= 0.35 + 0.65 * wrapped;

#ifdef USE_CLOUD_SHADOW
  // modelRot 为正交（含等比缩放），其转置即逆旋转，可把光线方向带回物体空间
  vec3 lObj = normalize(vec3(dot(modelRot[0], L), dot(modelRot[1], L), dot(modelRot[2], L)));
  float shade = cloudDensityLow(normalize(d + lObj * 0.05), uCloudSeed, uCloudCoverage, uTime);
  wrapped *= 1.0 - shade * 0.34;
#endif

  vec3 ambientColor = mix(vec3(0.30, 0.38, 0.58), uAtmoColor, 0.45) * uAmbient;
  float camFill = max(dot(N, V), 0.0) * 0.09;
  vec3 color = albedo * (uSunColor * wrapped * 0.88 + ambientColor + camFill);

  vec3 H = normalize(L + V);
  float spec = pow(max(dot(N, H), 0.0), mix(16.0, 110.0, gloss)) * specMask * day;
  color += uSunColor * spec * 0.5;

  color += emissive;

  float night = 1.0 - day;
  color += vec3(1.0, 0.80, 0.45) * cityMask * night * uNightLights * 0.8;

  float rim = pow(1.0 - max(dot(N, V), 0.0), 3.4);
  color += uAtmoColor * rim * (0.10 + day * 0.42);

  float luma = dot(color, vec3(0.2126, 0.7152, 0.0722));
  color = mix(vec3(luma), color, uSaturation);

  float pulse = uPulse * (0.5 + 0.5 * sin(uTime * 3.4));
  color += albedo * uGlow * (0.55 + 0.45 * day);
  color += uOverlayColor * uOverlayStrength * (0.20 + rim * 0.6 + pulse * 0.4);
  color *= 1.0 + uHover * 0.32;

  gl_FragColor = vec4(color, 1.0);

  #include <tonemapping_fragment>
  #include <colorspace_fragment>
}
`;
