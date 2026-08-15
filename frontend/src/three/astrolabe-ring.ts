import * as THREE from 'three';
import { ZODIAC_CONSTELLATIONS, ZODIAC_ELEMENT_META, constellationCenter } from './zodiac-data';

/**
 * 金色占星仪（浑天仪风）环组：
 * 雕刻环带（宫位符号 + 度数刻痕）+ 主刻度环 + 倾斜赤道环 + 垂直子午环
 * + 元素扇区弧带 + 反向旋转内环 + 虚线外环 + 宫位符号奖章
 * + 噪声日冕太阳 + 悬停光束。
 */
export interface AstrolabeRing {
  root: THREE.Group;
  setMedallionHighlight: (slug: string, on: boolean) => void;
  /** 悬停星座时从太阳拉出一条光束；传 null 淡出 */
  setBeam: (slug: string | null) => void;
  tick: (time: number) => void;
  dispose: () => void;
}

const GOLD = 0xd4af37;
const GOLD_BRIGHT = 0xf5d76e;
const RING_RADIUS = 14;
const OBLIQUITY = (23.4 * Math.PI) / 180;

function makeGlowTexture(): THREE.CanvasTexture {
  const canvas = document.createElement('canvas');
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, 'rgba(255,250,230,1)');
  g.addColorStop(0.25, 'rgba(245,215,110,0.85)');
  g.addColorStop(0.6, 'rgba(212,175,55,0.28)');
  g.addColorStop(1, 'rgba(212,175,55,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  return new THREE.CanvasTexture(canvas);
}

/**
 * 雕刻环带贴图：十二宫符号 + 每 5° 刻痕 + 宫界分隔线 + 上下饰边。
 * 圆柱侧壁上世界方位角 a 对应贴图 u = (PI/2 - a) / 2PI，
 * 因此按该公式排布符号即可与下方奖章严格对齐。
 */
function makeEngravedBandTexture(): THREE.CanvasTexture {
  const w = 2048;
  const h = 128;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;

  const uOfDeg = (deg: number) => {
    const a = (deg * Math.PI) / 180;
    let u = (Math.PI / 2 - a) / (Math.PI * 2);
    u = ((u % 1) + 1) % 1;
    return u * w;
  };

  // 上下双饰边
  ctx.strokeStyle = 'rgba(212,175,55,0.85)';
  ctx.lineWidth = 2;
  [10, h - 10].forEach((y) => {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  });
  ctx.strokeStyle = 'rgba(212,175,55,0.35)';
  ctx.lineWidth = 1;
  [17, h - 17].forEach((y) => {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
    ctx.stroke();
  });

  // 每 5° 刻痕；宫界（15° + k*30°）为通高分隔线
  for (let deg = 0; deg < 360; deg += 5) {
    const x = uOfDeg(deg);
    const isBoundary = (deg - 15) % 30 === 0;
    ctx.strokeStyle = isBoundary ? 'rgba(245,215,110,0.75)' : 'rgba(212,175,55,0.4)';
    ctx.lineWidth = isBoundary ? 1.6 : 1;
    ctx.beginPath();
    if (isBoundary) {
      ctx.moveTo(x, 20);
      ctx.lineTo(x, h - 20);
    } else {
      ctx.moveTo(x, 20);
      ctx.lineTo(x, 32);
      ctx.moveTo(x, h - 32);
      ctx.lineTo(x, h - 20);
    }
    ctx.stroke();
    if (isBoundary) {
      // 宫界菱形饰点
      ctx.fillStyle = 'rgba(245,215,110,0.9)';
      ctx.save();
      ctx.translate(x, h / 2);
      ctx.rotate(Math.PI / 4);
      ctx.fillRect(-3.4, -3.4, 6.8, 6.8);
      ctx.restore();
    }
  }

  // 十二宫符号（居于各自宫位中心）
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ZODIAC_CONSTELLATIONS.forEach((c) => {
    const x = uOfDeg(c.eclipticLon);
    const tint = ZODIAC_ELEMENT_META[c.element].css;
    ctx.font = '600 52px "Segoe UI Symbol", "Noto Serif SC", serif';
    ctx.shadowColor = 'rgba(245,215,110,0.9)';
    ctx.shadowBlur = 14;
    ctx.fillStyle = 'rgba(250,240,214,0.95)';
    ctx.fillText(c.symbol, x, h / 2 - 2);
    ctx.shadowBlur = 0;
    // 符号两侧的元素色小圆点
    ctx.fillStyle = tint;
    ctx.globalAlpha = 0.85;
    [-46, 46].forEach((dx) => {
      ctx.beginPath();
      ctx.arc(x + dx, h / 2, 3, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.globalAlpha = 1;
  });

  const tex = new THREE.CanvasTexture(canvas);
  tex.wrapS = THREE.RepeatWrapping;
  tex.anisotropy = 4;
  return tex;
}

/** 光束贴图：靠太阳端淡入、指向星座端聚亮再收尾 */
function makeBeamTexture(): THREE.CanvasTexture {
  const w = 256;
  const h = 64;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const along = ctx.createLinearGradient(0, 0, w, 0);
  along.addColorStop(0, 'rgba(245,215,110,0)');
  along.addColorStop(0.3, 'rgba(245,215,110,0.35)');
  along.addColorStop(0.82, 'rgba(253,240,200,0.85)');
  along.addColorStop(1, 'rgba(253,240,200,0)');
  ctx.fillStyle = along;
  ctx.fillRect(0, 0, w, h);
  // 纵向羽化
  const across = ctx.createLinearGradient(0, 0, 0, h);
  across.addColorStop(0, 'rgba(0,0,0,1)');
  across.addColorStop(0.5, 'rgba(0,0,0,0)');
  across.addColorStop(1, 'rgba(0,0,0,1)');
  ctx.globalCompositeOperation = 'destination-out';
  ctx.fillStyle = across;
  ctx.fillRect(0, 0, w, h);
  return new THREE.CanvasTexture(canvas);
}

function makeMedallionTexture(symbol: string, bright: boolean): THREE.CanvasTexture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const cx = size / 2;

  const alpha = bright ? 1 : 0.72;
  ctx.strokeStyle = `rgba(212, 175, 55, ${alpha})`;
  ctx.lineWidth = 2.5;
  ctx.beginPath();
  ctx.arc(cx, cx, 52, 0, Math.PI * 2);
  ctx.stroke();

  ctx.lineWidth = 1;
  ctx.strokeStyle = `rgba(245, 215, 110, ${alpha * 0.55})`;
  ctx.beginPath();
  ctx.arc(cx, cx, 44, 0, Math.PI * 2);
  ctx.stroke();

  // 四向装饰刻点
  ctx.fillStyle = `rgba(245, 215, 110, ${alpha})`;
  [0, Math.PI / 2, Math.PI, (Math.PI / 2) * 3].forEach((a) => {
    ctx.beginPath();
    ctx.arc(cx + Math.cos(a) * 52, cx + Math.sin(a) * 52, 2.6, 0, Math.PI * 2);
    ctx.fill();
  });

  ctx.font = '600 56px "Segoe UI Symbol", "Noto Serif SC", serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.shadowColor = 'rgba(245, 215, 110, 0.9)';
  ctx.shadowBlur = bright ? 14 : 6;
  ctx.fillStyle = bright ? 'rgba(253, 248, 231, 1)' : `rgba(243, 229, 184, ${alpha})`;
  ctx.fillText(symbol, cx, cx + 4);

  return new THREE.CanvasTexture(canvas);
}

function buildTicks(radius: number): THREE.LineSegments {
  const positions: number[] = [];
  for (let deg = 0; deg < 360; deg += 5) {
    const isMajor = deg % 30 === 0;
    const a = (deg * Math.PI) / 180;
    const inner = radius - (isMajor ? 0.55 : 0.22);
    const outer = radius + (isMajor ? 0.28 : 0.1);
    positions.push(
      Math.cos(a) * inner, 0, Math.sin(a) * inner,
      Math.cos(a) * outer, 0, Math.sin(a) * outer,
    );
  }
  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  return new THREE.LineSegments(
    geo,
    new THREE.LineBasicMaterial({
      color: GOLD,
      transparent: true,
      opacity: 0.5,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
}

/** 噪声日冕太阳：球面 fbm 火舌 + 边缘辉光，靠 uTime 驱动 */
function makeSunMaterial(): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    transparent: false,
    fog: false,
    uniforms: {
      uTime: { value: 0 },
    },
    vertexShader: /* glsl */ `
      varying vec3 vNormal;
      varying vec3 vPos;
      varying vec3 vViewDir;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPos = position;
        vec4 mv = modelViewMatrix * vec4(position, 1.0);
        vViewDir = normalize(-mv.xyz);
        gl_Position = projectionMatrix * mv;
      }
    `,
    fragmentShader: /* glsl */ `
      uniform float uTime;
      varying vec3 vNormal;
      varying vec3 vPos;
      varying vec3 vViewDir;

      float hash(vec3 p) {
        return fract(sin(dot(p, vec3(127.1, 311.7, 74.7))) * 43758.5453);
      }
      float noise(vec3 p) {
        vec3 i = floor(p);
        vec3 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        float n000 = hash(i);
        float n100 = hash(i + vec3(1.0, 0.0, 0.0));
        float n010 = hash(i + vec3(0.0, 1.0, 0.0));
        float n110 = hash(i + vec3(1.0, 1.0, 0.0));
        float n001 = hash(i + vec3(0.0, 0.0, 1.0));
        float n101 = hash(i + vec3(1.0, 0.0, 1.0));
        float n011 = hash(i + vec3(0.0, 1.0, 1.0));
        float n111 = hash(i + vec3(1.0, 1.0, 1.0));
        return mix(
          mix(mix(n000, n100, f.x), mix(n010, n110, f.x), f.y),
          mix(mix(n001, n101, f.x), mix(n011, n111, f.x), f.y),
          f.z
        );
      }
      float fbm(vec3 p) {
        float v = 0.0;
        float amp = 0.5;
        for (int i = 0; i < 4; i++) {
          v += amp * noise(p);
          p *= 2.1;
          amp *= 0.5;
        }
        return v;
      }

      void main() {
        vec3 p = normalize(vPos);
        float t = uTime * 0.00012;
        float f = fbm(p * 3.2 + vec3(t * 2.0, t * 1.4, -t));
        f += 0.5 * fbm(p * 7.0 - vec3(t * 3.0, 0.0, t * 2.0));
        f *= 0.68;

        vec3 deep = vec3(0.86, 0.42, 0.10);
        vec3 mid = vec3(1.0, 0.76, 0.34);
        vec3 hot = vec3(1.0, 0.96, 0.82);
        vec3 col = mix(deep, mid, smoothstep(0.25, 0.6, f));
        col = mix(col, hot, smoothstep(0.62, 0.92, f));

        // 边缘辉光（fresnel），让球体和光晕自然衔接
        float rim = pow(1.0 - abs(dot(normalize(vNormal), vViewDir)), 2.2);
        col += vec3(1.0, 0.82, 0.5) * rim * 0.65;

        gl_FragColor = vec4(col * 1.12, 1.0);
      }
    `,
  });
}

export function buildAstrolabeRing(lowPower = false): AstrolabeRing {
  const root = new THREE.Group();
  const disposables: Array<{ dispose: () => void }> = [];
  const track = <T extends { dispose: () => void }>(item: T): T => {
    disposables.push(item);
    return item;
  };

  // --- 主环带（宽金环，半透明底衬） ---
  const band = new THREE.Mesh(
    track(new THREE.RingGeometry(RING_RADIUS - 0.5, RING_RADIUS + 0.24, 160)),
    track(
      new THREE.MeshBasicMaterial({
        color: GOLD,
        transparent: true,
        opacity: 0.08,
        side: THREE.DoubleSide,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  band.rotation.x = -Math.PI / 2;
  band.userData = { skipRaycast: true };
  root.add(band);

  // --- 雕刻环带（圆柱侧壁贴图：符号 + 刻痕 + 饰边） ---
  const engravedTex = track(makeEngravedBandTexture());
  const engravedGeo = track(
    new THREE.CylinderGeometry(RING_RADIUS + 0.02, RING_RADIUS + 0.02, 1.15, 180, 1, true),
  );
  const engravedMat = track(
    new THREE.MeshBasicMaterial({
      map: engravedTex,
      transparent: true,
      opacity: 0.6,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    }),
  );
  const engraved = new THREE.Mesh(engravedGeo, engravedMat);
  engraved.userData = { skipRaycast: true };
  root.add(engraved);

  // --- 元素扇区弧带（火/土/风/水配色，打破全金单色） ---
  ZODIAC_CONSTELLATIONS.forEach((c) => {
    const meta = ZODIAC_ELEMENT_META[c.element];
    const thetaLength = (26 * Math.PI) / 180;
    const thetaStart = -((c.eclipticLon + 13) * Math.PI) / 180;
    const arc = new THREE.Mesh(
      track(new THREE.RingGeometry(RING_RADIUS - 1.05, RING_RADIUS - 0.6, 28, 1, thetaStart, thetaLength)),
      track(
        new THREE.MeshBasicMaterial({
          color: meta.hex,
          transparent: true,
          opacity: 0.14,
          side: THREE.DoubleSide,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      ),
    );
    arc.rotation.x = -Math.PI / 2;
    arc.userData = { skipRaycast: true };
    root.add(arc);
  });

  // --- 主环线 ---
  const mainRing = new THREE.Mesh(
    track(new THREE.TorusGeometry(RING_RADIUS, 0.025, 8, 160)),
    track(new THREE.MeshBasicMaterial({ color: GOLD_BRIGHT, transparent: true, opacity: 0.55 })),
  );
  mainRing.rotation.x = Math.PI / 2;
  mainRing.userData = { skipRaycast: true };
  root.add(mainRing);

  // --- 刻度（每 5° 短刻度，每 30° 宫位分隔长刻度） ---
  const ticks = buildTicks(RING_RADIUS);
  track(ticks.geometry);
  track(ticks.material as THREE.Material);
  ticks.userData = { skipRaycast: true };
  root.add(ticks);

  // --- 倾斜赤道环（黄赤交角 23.4°，带游走光珠） ---
  const equatorGroup = new THREE.Group();
  const equatorSpin = new THREE.Group();
  const equatorRadius = RING_RADIUS * 0.86;
  const equatorRing = new THREE.Mesh(
    track(new THREE.TorusGeometry(equatorRadius, 0.016, 8, 140)),
    track(
      new THREE.MeshBasicMaterial({
        color: GOLD,
        transparent: true,
        opacity: 0.32,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  equatorRing.rotation.x = Math.PI / 2;
  equatorRing.userData = { skipRaycast: true };
  equatorSpin.add(equatorRing);

  const beadGeo = track(new THREE.SphereGeometry(0.09, 10, 10));
  const beadMat = track(
    new THREE.MeshBasicMaterial({
      color: GOLD_BRIGHT,
      transparent: true,
      opacity: 0.85,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  for (let i = 0; i < 12; i++) {
    const a = (i / 12) * Math.PI * 2;
    const bead = new THREE.Mesh(beadGeo, beadMat);
    bead.position.set(Math.cos(a) * equatorRadius, 0, Math.sin(a) * equatorRadius);
    bead.userData = { skipRaycast: true };
    equatorSpin.add(bead);
  }
  equatorSpin.userData = { skipRaycast: true };
  equatorGroup.add(equatorSpin);
  equatorGroup.rotation.x = OBLIQUITY;
  equatorGroup.userData = { skipRaycast: true };
  root.add(equatorGroup);

  // --- 垂直子午环组（两条交叉大圆，缓慢绕天轴旋转，形成天球骨架） ---
  const meridianGroup = new THREE.Group();
  const meridianMat = track(
    new THREE.MeshBasicMaterial({
      color: GOLD,
      transparent: true,
      opacity: 0.14,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    }),
  );
  const meridianGeo = track(new THREE.TorusGeometry(RING_RADIUS + 0.65, 0.012, 8, 140));
  [0, Math.PI / 2].forEach((offset) => {
    const meridian = new THREE.Mesh(meridianGeo, meridianMat);
    meridian.rotation.y = offset;
    meridian.userData = { skipRaycast: true };
    meridianGroup.add(meridian);
  });
  meridianGroup.userData = { skipRaycast: true };
  root.add(meridianGroup);

  // --- 反向旋转内环（细刻度 + 细环线） ---
  const innerGroup = new THREE.Group();
  const innerRing = new THREE.Mesh(
    track(new THREE.TorusGeometry(RING_RADIUS - 1.5, 0.014, 8, 128)),
    track(new THREE.MeshBasicMaterial({ color: GOLD, transparent: true, opacity: 0.3 })),
  );
  innerRing.rotation.x = Math.PI / 2;
  innerRing.userData = { skipRaycast: true };
  innerGroup.add(innerRing);

  const innerTicks = buildTicks(RING_RADIUS - 1.5);
  (innerTicks.material as THREE.LineBasicMaterial).opacity = 0.24;
  track(innerTicks.geometry);
  track(innerTicks.material as THREE.Material);
  innerTicks.scale.setScalar(0.985);
  innerTicks.userData = { skipRaycast: true };
  innerGroup.add(innerTicks);
  innerGroup.userData = { skipRaycast: true };
  root.add(innerGroup);

  // --- 虚线外环 ---
  const outerGeo = track(new THREE.TorusGeometry(RING_RADIUS + 1.1, 0.01, 8, 64));
  const outerEdges = track(new THREE.EdgesGeometry(outerGeo));
  const outerMat = track(
    new THREE.LineDashedMaterial({
      color: GOLD,
      dashSize: 0.25,
      gapSize: 0.3,
      transparent: true,
      opacity: 0.28,
    }),
  );
  const outerRing = new THREE.LineSegments(outerEdges, outerMat);
  outerRing.rotation.x = Math.PI / 2;
  outerRing.computeLineDistances();
  outerRing.userData = { skipRaycast: true };
  root.add(outerRing);

  // --- 宫位符号奖章（可点击进入星座） ---
  const glowTex = track(makeGlowTexture());
  const medallions = new Map<string, { sprite: THREE.Sprite; dimTex: THREE.CanvasTexture; hotTex: THREE.CanvasTexture }>();
  ZODIAC_CONSTELLATIONS.forEach((c) => {
    const dimTex = track(makeMedallionTexture(c.symbol, false));
    const hotTex = track(makeMedallionTexture(c.symbol, true));
    const mat = track(
      new THREE.SpriteMaterial({
        map: dimTex,
        transparent: true,
        opacity: 0.85,
        depthWrite: false,
      }),
    );
    const sprite = new THREE.Sprite(mat);
    const a = (c.eclipticLon * Math.PI) / 180;
    sprite.position.set(Math.cos(a) * RING_RADIUS, -1.7, Math.sin(a) * RING_RADIUS);
    sprite.scale.set(1.35, 1.35, 1);
    sprite.userData = { type: 'constellation', slug: c.slug, name: c.name };
    root.add(sprite);
    medallions.set(c.slug, { sprite, dimTex, hotTex });
  });

  // --- 中心太阳：噪声日冕球 + 脉动辉光 ---
  const coreGroup = new THREE.Group();
  const sunMat = track(makeSunMaterial());
  const sunGeo = track(new THREE.SphereGeometry(0.95, 40, 40));
  const sun = new THREE.Mesh(sunGeo, sunMat);
  sun.userData = { skipRaycast: true };
  coreGroup.add(sun);

  const coreGlow = new THREE.Sprite(
    track(
      new THREE.SpriteMaterial({
        map: glowTex,
        transparent: true,
        opacity: 0.85,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  coreGlow.scale.set(4.6, 4.6, 1);
  coreGlow.userData = { skipRaycast: true };
  coreGroup.add(coreGlow);

  const coreHalo = new THREE.Sprite(
    track(
      new THREE.SpriteMaterial({
        map: glowTex,
        color: GOLD,
        transparent: true,
        opacity: 0.35,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  coreHalo.scale.set(9, 9, 1);
  coreHalo.userData = { skipRaycast: true };
  coreGroup.add(coreHalo);

  // 中心细光芒线
  const rayPositions: number[] = [];
  const rayCount = lowPower ? 6 : 10;
  for (let i = 0; i < rayCount; i++) {
    const a = (i / rayCount) * Math.PI * 2;
    const len = 2.4 + (i % 2) * 1.1;
    rayPositions.push(0, 0, 0, Math.cos(a) * len, Math.sin(a) * len * 0.4, Math.sin(a + 1.3) * len * 0.6);
  }
  const rayGeo = track(new THREE.BufferGeometry());
  rayGeo.setAttribute('position', new THREE.Float32BufferAttribute(rayPositions, 3));
  const rays = new THREE.LineSegments(
    rayGeo,
    track(
      new THREE.LineBasicMaterial({
        color: GOLD_BRIGHT,
        transparent: true,
        opacity: 0.3,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      }),
    ),
  );
  rays.userData = { skipRaycast: true };
  coreGroup.add(rays);
  coreGroup.userData = { skipRaycast: true };
  root.add(coreGroup);

  // --- 悬停光束（太阳 → 星座主星，惰性淡入淡出） ---
  const beamTex = track(makeBeamTexture());
  const beamMat = track(
    new THREE.MeshBasicMaterial({
      map: beamTex,
      color: GOLD_BRIGHT,
      transparent: true,
      opacity: 0,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    }),
  );
  const beamGeo = track(new THREE.PlaneGeometry(1, 1));
  const beamMesh = new THREE.Mesh(beamGeo, beamMat);
  beamMesh.rotation.x = -Math.PI / 2;
  beamMesh.userData = { skipRaycast: true };
  const beamPivot = new THREE.Group();
  beamPivot.add(beamMesh);
  beamPivot.visible = false;
  beamPivot.userData = { skipRaycast: true };
  root.add(beamPivot);
  let beamTarget = 0;

  return {
    root,
    setMedallionHighlight(slug: string, on: boolean) {
      const m = medallions.get(slug);
      if (!m) return;
      const mat = m.sprite.material as THREE.SpriteMaterial;
      mat.map = on ? m.hotTex : m.dimTex;
      mat.opacity = on ? 1 : 0.85;
      mat.needsUpdate = true;
      m.sprite.scale.setScalar(on ? 1.7 : 1.35);
    },
    setBeam(slug: string | null) {
      if (!slug) {
        beamTarget = 0;
        return;
      }
      const c = ZODIAC_CONSTELLATIONS.find((x) => x.slug === slug);
      if (!c) {
        beamTarget = 0;
        return;
      }
      const [cx, , cz] = constellationCenter(c);
      const dist = Math.hypot(cx, cz);
      const a = Math.atan2(cz, cx);
      beamPivot.rotation.y = -a;
      beamMesh.scale.set(dist - 1.2, 1.1, 1);
      beamMesh.position.set((dist - 1.2) / 2 + 1.0, 0.06, 0);
      beamPivot.visible = true;
      beamTarget = 0.45;
    },
    tick(time: number) {
      innerGroup.rotation.y = -time * 0.00009;
      outerRing.rotation.z = time * 0.00004;
      equatorSpin.rotation.y = time * 0.00006;
      meridianGroup.rotation.y = time * 0.000024;
      const pulse = 0.9 + Math.sin(time * 0.0011) * 0.1;
      coreGlow.scale.set(4.6 * pulse, 4.6 * pulse, 1);
      (coreHalo.material as THREE.SpriteMaterial).opacity = 0.28 + Math.sin(time * 0.0007) * 0.09;
      rays.rotation.y = time * 0.00012;
      sunMat.uniforms.uTime.value = time;
      // 光束淡入淡出 + 呼吸
      const flow = beamTarget > 0 ? beamTarget + Math.sin(time * 0.003) * 0.08 : 0;
      beamMat.opacity += (flow - beamMat.opacity) * 0.12;
      if (beamMat.opacity < 0.01 && beamTarget === 0) beamPivot.visible = false;
    },
    dispose() {
      disposables.forEach((d) => d.dispose());
    },
  };
}
