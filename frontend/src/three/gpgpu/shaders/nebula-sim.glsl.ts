/**
 * GPGPU 模拟 shader：
 * - 速度场 = 归位弹簧(星系形态) + 银河公转 + curl-noise 内部流动 + 鼠标力场 + warp 尾迹 + 阻尼
 * - 位置场 = 速度积分
 * GPUComputationRenderer 会自动注入 resolution 与 texturePosition / textureVelocity 采样器。
 */

/** 轻量 value-noise + 有限差分 curl（自研实现，流场用途足够平滑） */
const NOISE_GLSL = /* glsl */ `
float hash31(vec3 p) {
  p = fract(p * 0.3183099 + vec3(0.71, 0.113, 0.419));
  p *= 17.0;
  return fract(p.x * p.y * p.z * (p.x + p.y + p.z));
}

float vnoise(vec3 p) {
  vec3 i = floor(p);
  vec3 f = fract(p);
  vec3 u = f * f * (3.0 - 2.0 * f);
  float n000 = hash31(i);
  float n100 = hash31(i + vec3(1.0, 0.0, 0.0));
  float n010 = hash31(i + vec3(0.0, 1.0, 0.0));
  float n110 = hash31(i + vec3(1.0, 1.0, 0.0));
  float n001 = hash31(i + vec3(0.0, 0.0, 1.0));
  float n101 = hash31(i + vec3(1.0, 0.0, 1.0));
  float n011 = hash31(i + vec3(0.0, 1.0, 1.0));
  float n111 = hash31(i + vec3(1.0, 1.0, 1.0));
  return mix(
    mix(mix(n000, n100, u.x), mix(n010, n110, u.x), u.y),
    mix(mix(n001, n101, u.x), mix(n011, n111, u.x), u.y),
    u.z
  );
}

/** 两个错位噪声场的梯度叉积 → 无散度流场 */
vec3 curlNoise(vec3 p) {
  const float e = 0.35;
  vec3 dx = vec3(e, 0.0, 0.0);
  vec3 dy = vec3(0.0, e, 0.0);
  vec3 dz = vec3(0.0, 0.0, e);

  vec3 g1 = vec3(
    vnoise(p + dx) - vnoise(p - dx),
    vnoise(p + dy) - vnoise(p - dy),
    vnoise(p + dz) - vnoise(p - dz)
  );
  vec3 q = p + vec3(31.7, 15.3, 7.1);
  vec3 g2 = vec3(
    vnoise(q + dx) - vnoise(q - dx),
    vnoise(q + dy) - vnoise(q - dy),
    vnoise(q + dz) - vnoise(q - dz)
  );
  return normalize(cross(g1, g2) + vec3(1e-5));
}
`;

export const nebulaVelocityShader = /* glsl */ `
${NOISE_GLSL}

uniform float uTime;
uniform float uDelta;
uniform sampler2D uHome;
uniform float uFormation;      // 0 弥散 → 1 星系形态
uniform float uSwirl;          // 银河公转强度
uniform float uFlow;           // curl 流动幅度
uniform vec3 uPointer;         // 鼠标世界坐标（星系平面交点）
uniform float uPointerStrength;
uniform float uHoverCluster;   // -1 无
uniform float uWarp;           // 飞入尾迹强度
uniform vec3 uWarpDir;         // 尾迹方向（粒子相对流向）

void main() {
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec4 posData = texture2D(texturePosition, uv);
  vec3 pos = posData.xyz;
  float seed = posData.w;
  vec3 vel = texture2D(textureVelocity, uv).xyz;
  vec4 homeData = texture2D(uHome, uv);
  vec3 home = homeData.xyz;
  float cluster = homeData.w;

  float dt = uDelta;

  // 归位弹簧：formation 越高约束越强；悬停簇收拢更紧
  float springK = mix(0.06, 2.2, uFormation);
  if (cluster >= 0.0 && uHoverCluster >= 0.0 && abs(cluster - uHoverCluster) < 0.5) {
    springK *= 2.8;
  }
  vel += (home - pos) * springK * dt;

  // 银河公转（绕 Y 轴切向），核心处衰减避免抖动
  float r = length(pos.xz);
  vec3 tangent = vec3(-pos.z, 0.0, pos.x) / max(r, 1e-3);
  vel += tangent * uSwirl * smoothstep(0.5, 5.0, r) * dt;

  // curl-noise 内部流动，随时间缓慢演化
  vec3 flow = curlNoise(pos * 0.06 + vec3(0.0, uTime * 0.025, seed * 0.35));
  vel += flow * uFlow * (0.6 + seed * 0.8) * dt;

  // 鼠标力场：近距吸引 + 涡旋搅动
  vec3 dp = pos - uPointer;
  float pd2 = dot(dp, dp);
  float falloff = exp(-pd2 * 0.022) * uPointerStrength;
  if (falloff > 0.001) {
    vec3 dpn = dp / max(sqrt(pd2), 1e-3);
    vec3 vortex = normalize(cross(vec3(0.0, 1.0, 0.0), dpn) + vec3(1e-5));
    vel += (-dpn * 2.6 + vortex * 4.2) * falloff * dt;
  }

  // warp：飞入时粒子沿行进反方向拉出尾迹
  vel += uWarpDir * uWarp * (10.0 + seed * 14.0) * dt;

  // 阻尼 + 限速
  vel *= exp(-2.3 * dt);
  float speed = length(vel);
  float maxSpeed = 13.0 + uWarp * 34.0;
  if (speed > maxSpeed) vel *= maxSpeed / speed;

  gl_FragColor = vec4(vel, 1.0);
}
`;

export const nebulaPositionShader = /* glsl */ `
uniform float uDelta;

void main() {
  vec2 uv = gl_FragCoord.xy / resolution.xy;
  vec4 posData = texture2D(texturePosition, uv);
  vec3 vel = texture2D(textureVelocity, uv).xyz;
  posData.xyz += vel * uDelta;
  gl_FragColor = posData;
}
`;
