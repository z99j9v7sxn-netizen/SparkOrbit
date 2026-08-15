/**
 * 星球程序化材质共用的 GLSL 噪声库。
 * 供地表 / 云层 / 环带 shader 以 `${planetNoiseCommon}` 内联复用。
 *
 * 需要在 material.defines 中提供 FBM_OCTAVES（缺省 4）。
 */
export const planetNoiseCommon = /* glsl */ `
#ifndef FBM_OCTAVES
#define FBM_OCTAVES 4
#endif

vec3 pn_mod289(vec3 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 pn_mod289(vec4 x) { return x - floor(x * (1.0 / 289.0)) * 289.0; }
vec4 pn_permute(vec4 x) { return pn_mod289(((x * 34.0) + 1.0) * x); }
vec4 pn_taylorInvSqrt(vec4 r) { return 1.79284291400159 - 0.85373472095314 * r; }

/** 无三角函数的 hash33（Dave Hoskins），worley 每像素要跑 27 次，避开 sin 明显更省 */
vec3 pn_hash3(vec3 p) {
  p = fract(p * vec3(0.1031, 0.1030, 0.0973));
  p += dot(p, p.yxz + 33.33);
  return fract((p.xxy + p.yxx) * p.zyx);
}

/** Ashima 3D simplex noise，返回约 [-1, 1] */
float snoise(vec3 v) {
  const vec2 C = vec2(1.0 / 6.0, 1.0 / 3.0);
  const vec4 D = vec4(0.0, 0.5, 1.0, 2.0);

  vec3 i = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);

  vec3 g = step(x0.yzx, x0.xyz);
  vec3 l = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);

  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;

  i = pn_mod289(i);
  vec4 p = pn_permute(pn_permute(pn_permute(
      i.z + vec4(0.0, i1.z, i2.z, 1.0))
    + i.y + vec4(0.0, i1.y, i2.y, 1.0))
    + i.x + vec4(0.0, i1.x, i2.x, 1.0));

  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;

  vec4 j = p - 49.0 * floor(p * ns.z * ns.z);

  vec4 x_ = floor(j * ns.z);
  vec4 y_ = floor(j - 7.0 * x_);

  vec4 x = x_ * ns.x + ns.yyyy;
  vec4 y = y_ * ns.x + ns.yyyy;
  vec4 h = 1.0 - abs(x) - abs(y);

  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);

  vec4 s0 = floor(b0) * 2.0 + 1.0;
  vec4 s1 = floor(b1) * 2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));

  vec4 a0 = b0.xzyw + s0.xzyw * sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw * sh.zzww;

  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);

  vec4 norm = pn_taylorInvSqrt(vec4(dot(p0, p0), dot(p1, p1), dot(p2, p2), dot(p3, p3)));
  p0 *= norm.x;
  p1 *= norm.y;
  p2 *= norm.z;
  p3 *= norm.w;

  vec4 m = max(0.6 - vec4(dot(x0, x0), dot(x1, x1), dot(x2, x2), dot(x3, x3)), 0.0);
  m = m * m;
  return 42.0 * dot(m * m, vec4(dot(p0, x0), dot(p1, x1), dot(p2, x2), dot(p3, x3)));
}

/** 多倍频分形噪声，倍频数由 FBM_OCTAVES 决定，返回约 [-1, 1] */
float fbm(vec3 p) {
  float amp = 0.5;
  float sum = 0.0;
  float norm = 0.0;
  for (int i = 0; i < FBM_OCTAVES; i++) {
    sum += amp * snoise(p);
    norm += amp;
    p *= 2.03;
    amp *= 0.5;
  }
  return sum / norm;
}

/** 两倍频廉价版本，用于凹凸/遮罩等不需要高频细节的场合 */
float fbm2(vec3 p) {
  return (snoise(p) * 0.62 + snoise(p * 2.07) * 0.31) / 0.93;
}

/** 脊状噪声：山脉、裂纹 */
float ridged(vec3 p) {
  float amp = 0.5;
  float sum = 0.0;
  float norm = 0.0;
  for (int i = 0; i < FBM_OCTAVES; i++) {
    sum += amp * (1.0 - abs(snoise(p)));
    norm += amp;
    p *= 2.11;
    amp *= 0.5;
  }
  return sum / norm;
}

float ridged2(vec3 p) {
  return ((1.0 - abs(snoise(p))) * 0.64 + (1.0 - abs(snoise(p * 2.11))) * 0.32) / 0.96;
}

/** 域扭曲：让条带与大陆边缘出现湍流感，而不是规整的正弦 */
vec3 domainWarp(vec3 p, float strength) {
  vec3 offset = vec3(
    snoise(p + vec3(11.3, 4.7, 19.1)),
    snoise(p + vec3(27.7, 31.2, 5.4)),
    snoise(p + vec3(41.1, 17.9, 23.6))
  );
  return p + offset * strength;
}

/** 3D Worley（细胞）噪声，返回最近与次近距离，用于陨石坑与熔岩裂缝 */
vec2 worley(vec3 p) {
  vec3 cell = floor(p);
  vec3 f = fract(p);
  float f1 = 8.0;
  float f2 = 8.0;
  for (int x = -1; x <= 1; x++) {
    for (int y = -1; y <= 1; y++) {
      for (int z = -1; z <= 1; z++) {
        vec3 g = vec3(float(x), float(y), float(z));
        vec3 o = pn_hash3(cell + g);
        vec3 d = g + o - f;
        float dist = dot(d, d);
        if (dist < f1) {
          f2 = f1;
          f1 = dist;
        } else if (dist < f2) {
          f2 = dist;
        }
      }
    }
  }
  return vec2(sqrt(f1), sqrt(f2));
}

/**
 * 云层密度场：地表 shader 与云层 shader 共用同一表达式，
 * 因此地表投下的云影能与云层本体对齐。
 */
vec3 cloudSamplePos(vec3 dir, vec3 seed, float time) {
  return dir * 2.7 + seed + vec3(time * 0.011, time * 0.004, time * 0.008);
}

float cloudDensity(vec3 dir, vec3 seed, float coverage, float time) {
  vec3 q = domainWarp(cloudSamplePos(dir, seed, time), 0.32);
  return smoothstep(coverage, coverage + 0.24, fbm(q) * 0.5 + 0.5);
}

float cloudDensityLow(vec3 dir, vec3 seed, float coverage, float time) {
  vec3 q = cloudSamplePos(dir, seed, time);
  return smoothstep(coverage, coverage + 0.28, fbm2(q) * 0.5 + 0.5);
}
`;
