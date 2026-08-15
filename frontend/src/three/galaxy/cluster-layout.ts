import * as THREE from 'three';

/** 学生端七大分区，与 StudentPortal / ZoneHub 的 zone key 保持一致 */
export type GalaxyZoneKey = 'chat' | 'learn' | 'study' | 'leisure' | 'domain' | 'treehole' | 'interview';

export interface ClusterSpec {
  key: GalaxyZoneKey;
  /** 模拟 shader 中的簇编号（home 纹理 w 通道） */
  id: number;
  position: THREE.Vector3;
  /** 簇内粒子散布半径 */
  radius: number;
  color: THREE.Color;
  /** 簇心少量高亮粒子的偏白色调 */
  accent: THREE.Color;
}

/** 屏幕投影锚点，供 ZoneHub DOM 标签定位 */
export interface ZoneAnchor {
  key: GalaxyZoneKey;
  x: number;
  y: number;
  /** 0(近) → 1(远)，可用于缩放标签 */
  depth: number;
  visible: boolean;
  hovered: boolean;
}

/**
 * 簇的空间布局：环绕星系核错落分布。
 * 相机基位约 (0, 5, 26) 朝向原点，布局大致对应原 ZoneHub 的散落百分比。
 */
export const CLUSTERS: ClusterSpec[] = [
  {
    key: 'learn',
    id: 0,
    position: new THREE.Vector3(0.0, 0.6, 0.0),
    radius: 4.0,
    color: new THREE.Color(0x38bdf8),
    accent: new THREE.Color(0xbfe8ff),
  },
  {
    key: 'domain',
    id: 1,
    position: new THREE.Vector3(0.4, 6.6, -2.5),
    radius: 3.2,
    color: new THREE.Color(0x818cf8),
    accent: new THREE.Color(0xd6dbff),
  },
  {
    key: 'treehole',
    id: 2,
    position: new THREE.Vector3(9.8, 3.8, -1.0),
    radius: 3.4,
    color: new THREE.Color(0xa78bfa),
    accent: new THREE.Color(0xe9defe),
  },
  {
    key: 'chat',
    id: 3,
    position: new THREE.Vector3(8.8, -3.6, 2.0),
    radius: 3.6,
    color: new THREE.Color(0xec4899),
    accent: new THREE.Color(0xffd3e8),
  },
  {
    key: 'study',
    id: 4,
    position: new THREE.Vector3(-10.2, -4.0, -1.5),
    radius: 3.6,
    color: new THREE.Color(0x22d3ee),
    accent: new THREE.Color(0xc9f6ff),
  },
  {
    key: 'leisure',
    id: 5,
    position: new THREE.Vector3(0.2, -6.8, 1.0),
    radius: 3.4,
    color: new THREE.Color(0x34d399),
    accent: new THREE.Color(0xccffe9),
  },
  {
    key: 'interview',
    id: 6,
    position: new THREE.Vector3(-9.6, 3.4, 1.5),
    radius: 3.2,
    color: new THREE.Color(0xf59e0b),
    accent: new THREE.Color(0xffe7b8),
  },
];

export function clusterByKey(key: GalaxyZoneKey): ClusterSpec {
  const found = CLUSTERS.find((c) => c.key === key);
  if (!found) throw new Error(`unknown galaxy zone: ${key}`);
  return found;
}

/** 环境粒子（尘埃带 + 核心亮团 + 远景壳）占总量比例 */
const AMBIENT_SHARE = 0.65;

/** 尘埃带蓝→紫→粉渐变，与既有 nebula-background 色带一致 */
const BAND_COLORS = [new THREE.Color(0x0ea5e9), new THREE.Color(0x6366f1), new THREE.Color(0xc084fc), new THREE.Color(0xec4899)];

export interface ParticleData {
  count: number;
  /** RGBA：xyz = 星系形态归位点，w = 簇编号（环境粒子为 -1） */
  home: Float32Array;
  /** 初始散布位置（入场汇聚动画起点），RGBA，w = 随机种子 */
  scatter: Float32Array;
  color: Float32Array;
  size: Float32Array;
  softness: Float32Array;
  phase: Float32Array;
  clusterId: Float32Array;
}

function gaussianOffset(radius: number): THREE.Vector3 {
  // 三次均匀随机近似高斯，簇心密、边缘疏
  const g = () => (Math.random() + Math.random() + Math.random()) / 3 - 0.5;
  return new THREE.Vector3(g() * 2 * radius, g() * 2 * radius * 0.75, g() * 2 * radius);
}

function bandColorAt(angle: number): THREE.Color {
  const t = ((Math.sin(angle) + 1) * 0.5) * (BAND_COLORS.length - 1);
  const i = Math.min(Math.floor(t), BAND_COLORS.length - 2);
  return BAND_COLORS[i].clone().lerp(BAND_COLORS[i + 1], t - i);
}

/**
 * 生成粒子静态数据：home 纹理（模拟层）与渲染属性（几何层）共用同一次分配，
 * 保证簇编号在两侧一致。count 必须等于 FBO 纹理 size*size。
 */
export function generateParticleData(count: number): ParticleData {
  const home = new Float32Array(count * 4);
  const scatter = new Float32Array(count * 4);
  const color = new Float32Array(count * 3);
  const size = new Float32Array(count);
  const softness = new Float32Array(count);
  const phase = new Float32Array(count);
  const clusterId = new Float32Array(count);

  const ambientCount = Math.floor(count * AMBIENT_SHARE);
  const clusterCount = count - ambientCount;
  const perCluster = Math.floor(clusterCount / CLUSTERS.length);

  for (let i = 0; i < count; i++) {
    let homePos: THREE.Vector3;
    let c: THREE.Color;
    let cid = -1;
    let psize: number;
    let soft: number;

    if (i < clusterCount) {
      const spec = CLUSTERS[Math.min(Math.floor(i / perCluster), CLUSTERS.length - 1)];
      cid = spec.id;
      // 约 20% 粒子放到 1~2.2 倍半径形成稀疏外晕，簇读作星团而非实心球
      const haloT = Math.random() < 0.2 ? 1 + Math.random() * 1.2 : 1;
      homePos = spec.position.clone().add(gaussianOffset(spec.radius * haloT));
      const centerT = 1 - Math.min(homePos.distanceTo(spec.position) / spec.radius, 1);
      if (Math.random() < 0.15) {
        // 软云体：大而软、深色调，铺出簇的星云体积（高 softness 在 fragment 中自动压 alpha）
        c = spec.color.clone().lerp(new THREE.Color(0x0f172a), 0.25 + Math.random() * 0.2);
        psize = 5 + Math.random() * 5;
        soft = 0.85 + Math.random() * 0.1;
      } else {
        // 星点：小颗锐利，云中有星
        c = spec.color.clone().lerp(spec.accent, centerT * centerT * 0.35);
        psize = 1.0 + Math.random() * 1.5 + centerT * 0.7;
        soft = 0.25 + Math.random() * 0.3;
      }
    } else {
      const kind = Math.random();
      if (kind < 0.78) {
        // 银河尘埃带（原星系核亮团配额并入此处，中心由学习区簇承担）
        const a = Math.random() * Math.PI * 2;
        const r = 5 + Math.random() * 19;
        homePos = new THREE.Vector3(Math.cos(a) * r, (Math.random() - 0.5) * (2.2 + r * 0.16), Math.sin(a) * r);
        if (Math.random() < 0.1) {
          // 尘埃带软云体，呼应旧背景的 cloud layer
          c = bandColorAt(a).lerp(new THREE.Color(0x0f172a), 0.35);
          psize = 6 + Math.random() * 6;
          soft = 0.88;
        } else {
          c = bandColorAt(a).lerp(new THREE.Color(0x1e293b), Math.random() * 0.25);
          psize = 1.0 + Math.random() * 2.4;
          soft = 0.5 + Math.random() * 0.35;
        }
      } else {
        // 远景星壳
        const theta = Math.random() * Math.PI * 2;
        const phi = Math.acos(2 * Math.random() - 1);
        const r = 36 + Math.random() * 30;
        homePos = new THREE.Vector3(
          r * Math.sin(phi) * Math.cos(theta),
          r * Math.sin(phi) * Math.sin(theta) * 0.6,
          r * Math.cos(phi),
        );
        c = bandColorAt(theta).lerp(new THREE.Color(0xffffff), 0.55);
        psize = 0.8 + Math.random() * 1.2;
        soft = 0.2;
      }
    }

    // 入场起点：大半径弥散球壳
    const st = Math.random() * Math.PI * 2;
    const sp = Math.acos(2 * Math.random() - 1);
    const sr = 46 + Math.random() * 34;
    scatter[i * 4] = sr * Math.sin(sp) * Math.cos(st);
    scatter[i * 4 + 1] = sr * Math.sin(sp) * Math.sin(st) * 0.7;
    scatter[i * 4 + 2] = sr * Math.cos(sp);
    scatter[i * 4 + 3] = Math.random();

    home[i * 4] = homePos.x;
    home[i * 4 + 1] = homePos.y;
    home[i * 4 + 2] = homePos.z;
    home[i * 4 + 3] = cid;

    color[i * 3] = c.r;
    color[i * 3 + 1] = c.g;
    color[i * 3 + 2] = c.b;
    size[i] = psize;
    softness[i] = soft;
    phase[i] = Math.random() * Math.PI * 2;
    clusterId[i] = cid;
  }

  return { count, home, scatter, color, size, softness, phase, clusterId };
}
