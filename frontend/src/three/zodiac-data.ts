/**
 * 黄道十二宫相对星图数据（简化公有星座形态，非绝对赤经赤纬）。
 * 每个星座给出本地 2D 坐标（约 -1~1）与连线边，再映射到 3D 黄道带位置。
 */
export interface ZodiacStar {
  id: string;
  x: number;
  y: number;
  bright?: boolean;
}

export type ZodiacElement = 'fire' | 'earth' | 'air' | 'water';

export interface ZodiacConstellation {
  slug: string;
  name: string;
  symbol: string;
  /** 黄道角 0-330 度 */
  eclipticLon: number;
  element: ZodiacElement;
  dateRange: string;
  motto: string;
  stars: ZodiacStar[];
  edges: [number, number][];
}

/** 四元素配色：three 用十六进制，DOM 用 css 字符串 */
export const ZODIAC_ELEMENT_META: Record<
  ZodiacElement,
  { label: string; hex: number; nebulaHex: number; css: string }
> = {
  fire: { label: '火象', hex: 0xf59e0b, nebulaHex: 0xb45309, css: '#f59e0b' },
  earth: { label: '土象', hex: 0xd4af37, nebulaHex: 0x92722a, css: '#d4af37' },
  air: { label: '风象', hex: 0xf5e9c8, nebulaHex: 0xa79b6e, css: '#f5e9c8' },
  water: { label: '水象', hex: 0x9dd8c8, nebulaHex: 0x2f7a6e, css: '#9dd8c8' },
};

export const ZODIAC_CONSTELLATIONS: ZodiacConstellation[] = [
  {
    slug: 'aries', name: '白羊座', symbol: '♈\uFE0E', eclipticLon: 0,
    element: 'fire', dateRange: '3.21 - 4.19', motto: '烈焰先驱 · 一往无前',
    stars: [{ id: 'a', x: -0.6, y: 0.2, bright: true }, { id: 'b', x: -0.1, y: 0.35 }, { id: 'c', x: 0.4, y: 0.1, bright: true }, { id: 'd', x: 0.7, y: -0.2 }],
    edges: [[0, 1], [1, 2], [2, 3]],
  },
  {
    slug: 'taurus', name: '金牛座', symbol: '♉\uFE0E', eclipticLon: 30,
    element: 'earth', dateRange: '4.20 - 5.20', motto: '沉稳大地 · 厚积薄发',
    stars: [{ id: 'a', x: -0.7, y: 0.3 }, { id: 'b', x: -0.2, y: 0.15, bright: true }, { id: 'c', x: 0.2, y: -0.05 }, { id: 'd', x: 0.55, y: 0.25 }, { id: 'e', x: 0.7, y: -0.3, bright: true }],
    edges: [[0, 1], [1, 2], [2, 3], [2, 4]],
  },
  {
    slug: 'gemini', name: '双子座', symbol: '♊\uFE0E', eclipticLon: 60,
    element: 'air', dateRange: '5.21 - 6.21', motto: '灵动双星 · 思维如风',
    stars: [{ id: 'a', x: -0.5, y: 0.6, bright: true }, { id: 'b', x: 0.5, y: 0.55, bright: true }, { id: 'c', x: -0.55, y: 0.1 }, { id: 'd', x: 0.45, y: 0.05 }, { id: 'e', x: -0.45, y: -0.5 }, { id: 'f', x: 0.4, y: -0.55 }],
    edges: [[0, 1], [0, 2], [1, 3], [2, 4], [3, 5]],
  },
  {
    slug: 'cancer', name: '巨蟹座', symbol: '♋\uFE0E', eclipticLon: 90,
    element: 'water', dateRange: '6.22 - 7.22', motto: '静水深流 · 守护之心',
    stars: [{ id: 'a', x: -0.4, y: 0.4 }, { id: 'b', x: 0.1, y: 0.2, bright: true }, { id: 'c', x: 0.5, y: 0.35 }, { id: 'd', x: 0.0, y: -0.3 }, { id: 'e', x: 0.35, y: -0.45 }],
    edges: [[0, 1], [1, 2], [1, 3], [3, 4]],
  },
  {
    slug: 'leo', name: '狮子座', symbol: '♌\uFE0E', eclipticLon: 120,
    element: 'fire', dateRange: '7.23 - 8.22', motto: '王者之焰 · 光芒万丈',
    stars: [{ id: 'a', x: -0.7, y: 0.2 }, { id: 'b', x: -0.3, y: 0.45, bright: true }, { id: 'c', x: 0.1, y: 0.25 }, { id: 'd', x: 0.35, y: 0.0 }, { id: 'e', x: 0.65, y: -0.25, bright: true }, { id: 'f', x: 0.2, y: -0.4 }],
    edges: [[0, 1], [1, 2], [2, 3], [3, 4], [3, 5]],
  },
  {
    slug: 'virgo', name: '处女座', symbol: '♍\uFE0E', eclipticLon: 150,
    element: 'earth', dateRange: '8.23 - 9.22', motto: '精益求精 · 纤尘不染',
    stars: [{ id: 'a', x: -0.5, y: 0.5 }, { id: 'b', x: -0.2, y: 0.2 }, { id: 'c', x: 0.15, y: 0.0, bright: true }, { id: 'd', x: 0.45, y: -0.2 }, { id: 'e', x: 0.2, y: -0.45 }, { id: 'f', x: 0.65, y: 0.15 }],
    edges: [[0, 1], [1, 2], [2, 3], [2, 4], [2, 5]],
  },
  {
    slug: 'libra', name: '天秤座', symbol: '♎\uFE0E', eclipticLon: 180,
    element: 'air', dateRange: '9.23 - 10.23', motto: '衡星在手 · 优雅致远',
    stars: [{ id: 'a', x: -0.55, y: 0.35 }, { id: 'b', x: 0.0, y: 0.45, bright: true }, { id: 'c', x: 0.55, y: 0.3 }, { id: 'd', x: -0.25, y: -0.25 }, { id: 'e', x: 0.3, y: -0.3 }],
    edges: [[0, 1], [1, 2], [0, 3], [2, 4]],
  },
  {
    slug: 'scorpio', name: '天蝎座', symbol: '♏\uFE0E', eclipticLon: 210,
    element: 'water', dateRange: '10.24 - 11.22', motto: '深渊凝视 · 专注如一',
    stars: [{ id: 'a', x: -0.7, y: 0.35 }, { id: 'b', x: -0.3, y: 0.2, bright: true }, { id: 'c', x: 0.1, y: 0.05 }, { id: 'd', x: 0.4, y: -0.15 }, { id: 'e', x: 0.65, y: -0.4 }, { id: 'f', x: 0.35, y: -0.55 }, { id: 'g', x: 0.05, y: -0.4 }],
    edges: [[0, 1], [1, 2], [2, 3], [3, 4], [4, 5], [5, 6]],
  },
  {
    slug: 'sagittarius', name: '射手座', symbol: '♐\uFE0E', eclipticLon: 240,
    element: 'fire', dateRange: '11.23 - 12.21', motto: '离弦之箭 · 直指远方',
    stars: [{ id: 'a', x: -0.4, y: 0.5 }, { id: 'b', x: 0.1, y: 0.35, bright: true }, { id: 'c', x: 0.45, y: 0.1 }, { id: 'd', x: 0.0, y: 0.0 }, { id: 'e', x: -0.35, y: -0.3 }, { id: 'f', x: 0.25, y: -0.45 }],
    edges: [[0, 1], [1, 2], [1, 3], [3, 4], [3, 5]],
  },
  {
    slug: 'capricorn', name: '摩羯座', symbol: '♑\uFE0E', eclipticLon: 270,
    element: 'earth', dateRange: '12.22 - 1.19', motto: '孤峰独攀 · 步步为营',
    stars: [{ id: 'a', x: -0.65, y: 0.25 }, { id: 'b', x: -0.2, y: 0.35, bright: true }, { id: 'c', x: 0.25, y: 0.2 }, { id: 'd', x: 0.55, y: -0.1 }, { id: 'e', x: 0.2, y: -0.4 }],
    edges: [[0, 1], [1, 2], [2, 3], [3, 4]],
  },
  {
    slug: 'aquarius', name: '水瓶座', symbol: '♒\uFE0E', eclipticLon: 300,
    element: 'air', dateRange: '1.20 - 2.18', motto: '倒转星河 · 思想自由',
    stars: [{ id: 'a', x: -0.4, y: 0.55, bright: true }, { id: 'b', x: 0.0, y: 0.35 }, { id: 'c', x: 0.35, y: 0.15 }, { id: 'd', x: -0.15, y: -0.05 }, { id: 'e', x: 0.2, y: -0.35 }, { id: 'f', x: 0.55, y: -0.5 }],
    edges: [[0, 1], [1, 2], [1, 3], [3, 4], [4, 5]],
  },
  {
    slug: 'pisces', name: '双鱼座', symbol: '♓\uFE0E', eclipticLon: 330,
    element: 'water', dateRange: '2.19 - 3.20', motto: '梦泅星海 · 温柔无界',
    stars: [{ id: 'a', x: -0.7, y: 0.4 }, { id: 'b', x: -0.3, y: 0.15 }, { id: 'c', x: 0.1, y: -0.05, bright: true }, { id: 'd', x: 0.4, y: 0.25 }, { id: 'e', x: 0.7, y: 0.45 }, { id: 'f', x: 0.25, y: -0.4 }],
    edges: [[0, 1], [1, 2], [2, 3], [3, 4], [2, 5]],
  },
];

const RING_RADIUS = 14;

/** 将星座本地坐标映射到 3D 黄道带世界坐标 */
export function constellationWorldPos(c: ZodiacConstellation, localX: number, localY: number): [number, number, number] {
  const angle = (c.eclipticLon * Math.PI) / 180;
  const cx = Math.cos(angle) * RING_RADIUS;
  const cz = Math.sin(angle) * RING_RADIUS;
  // 本地切向/径向基
  const tx = -Math.sin(angle);
  const tz = Math.cos(angle);
  const scale = 2.2;
  return [
    cx + tx * localX * scale,
    localY * scale * 1.1,
    cz + tz * localX * scale,
  ];
}

export function constellationCenter(c: ZodiacConstellation): [number, number, number] {
  return constellationWorldPos(c, 0, 0);
}
