import * as THREE from 'three';
import {
  constellationCenter,
  constellationWorldPos,
  ZODIAC_ELEMENT_META,
  type ZodiacConstellation,
} from './zodiac-data';

export interface ConstellationVisual {
  root: THREE.Group;
  slug: string;
  particles: THREE.Points;
  lines: THREE.LineSegments;
  label: THREE.Sprite;
  setHighlight: (on: boolean) => void;
  /** 入场渐显：0（隐藏）→ 1（完整） */
  setRevealFactor: (f: number) => void;
  tick: (time: number) => void;
  dispose: () => void;
}

const GOLD_BRIGHT = new THREE.Color(0xf5d76e);
const WHITE = new THREE.Color(0xffffff);

function makeGlowTexture(): THREE.Texture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.35, 'rgba(255,255,255,0.55)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  const tex = new THREE.CanvasTexture(canvas);
  tex.needsUpdate = true;
  return tex;
}

function makeCrossFlareTexture(): THREE.Texture {
  const size = 128;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const c = size / 2;
  const drawRay = (angle: number, len: number, width: number) => {
    ctx.save();
    ctx.translate(c, c);
    ctx.rotate(angle);
    const g = ctx.createLinearGradient(0, -len, 0, len);
    g.addColorStop(0, 'rgba(255,250,230,0)');
    g.addColorStop(0.5, 'rgba(255,250,230,0.95)');
    g.addColorStop(1, 'rgba(255,250,230,0)');
    ctx.fillStyle = g;
    ctx.fillRect(-width / 2, -len, width, len * 2);
    ctx.restore();
  };
  drawRay(0, c * 0.92, 3);
  drawRay(Math.PI / 2, c * 0.92, 3);
  drawRay(Math.PI / 4, c * 0.45, 1.6);
  drawRay(-Math.PI / 4, c * 0.45, 1.6);
  const g = ctx.createRadialGradient(c, c, 0, c, c, 16);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

const glowTex = makeGlowTexture();
const flareTex = makeCrossFlareTexture();

function sampleAlongEdge(
  a: THREE.Vector3,
  b: THREE.Vector3,
  t: number,
): THREE.Vector3 {
  return new THREE.Vector3().lerpVectors(a, b, t);
}

function buildParticleCloud(c: ZodiacConstellation, count: number): {
  positions: Float32Array;
  colors: Float32Array;
  sizes: Float32Array;
  starWorld: THREE.Vector3[];
} {
  const starWorld = c.stars.map((s) => {
    const [x, y, z] = constellationWorldPos(c, s.x, s.y);
    return new THREE.Vector3(x, y, z);
  });

  const positions = new Float32Array(count * 3);
  const colors = new Float32Array(count * 3);
  const sizes = new Float32Array(count);

  const elementColor = new THREE.Color(ZODIAC_ELEMENT_META[c.element].hex);
  const gold = new THREE.Color(0xd4af37);

  for (let i = 0; i < count; i++) {
    let p: THREE.Vector3;
    const roll = Math.random();
    if (roll < 0.35 && c.edges.length) {
      const [ia, ib] = c.edges[Math.floor(Math.random() * c.edges.length)];
      const sa = starWorld[ia];
      const sb = starWorld[ib];
      if (sa && sb) {
        p = sampleAlongEdge(sa, sb, Math.random());
        p.x += (Math.random() - 0.5) * 0.35;
        p.y += (Math.random() - 0.5) * 0.35;
        p.z += (Math.random() - 0.5) * 0.35;
      } else {
        const s = starWorld[Math.floor(Math.random() * starWorld.length)];
        p = s.clone().add(new THREE.Vector3((Math.random() - 0.5) * 0.5, (Math.random() - 0.5) * 0.5, (Math.random() - 0.5) * 0.5));
      }
    } else {
      const s = starWorld[Math.floor(Math.random() * starWorld.length)];
      const jitter = 0.25 + Math.random() * 0.55;
      p = s.clone().add(
        new THREE.Vector3(
          (Math.random() - 0.5) * jitter,
          (Math.random() - 0.5) * jitter * 0.7,
          (Math.random() - 0.5) * jitter,
        ),
      );
    }

    positions[i * 3] = p.x;
    positions[i * 3 + 1] = p.y;
    positions[i * 3 + 2] = p.z;

    const mix = Math.random();
    const col =
      mix < 0.3
        ? gold.clone().lerp(WHITE, mix * 2.4)
        : elementColor.clone().lerp(WHITE, (mix - 0.3) * 1.1);
    colors[i * 3] = col.r;
    colors[i * 3 + 1] = col.g;
    colors[i * 3 + 2] = col.b;
    sizes[i] = 0.8 + Math.random() * 2.2;
  }

  return { positions, colors, sizes, starWorld };
}

function makeLabel(text: string, scale = 2.4): THREE.Sprite {
  const canvas = document.createElement('canvas');
  canvas.width = 512;
  canvas.height = 128;
  const ctx = canvas.getContext('2d')!;
  ctx.clearRect(0, 0, 512, 128);
  ctx.font = '600 38px "Noto Serif SC", "Segoe UI Symbol", serif';
  ctx.fillStyle = 'rgba(243, 229, 184, 0.94)';
  ctx.shadowColor = 'rgba(212, 175, 55, 0.65)';
  ctx.shadowBlur = 12;
  ctx.textAlign = 'center';
  ctx.fillText(text, 256, 72);
  const tex = new THREE.CanvasTexture(canvas);
  const mat = new THREE.SpriteMaterial({ map: tex, transparent: true, depthTest: true });
  const sprite = new THREE.Sprite(mat);
  sprite.scale.set(scale, scale * 0.25, 1);
  return sprite;
}

export function buildConstellationVisual(c: ZodiacConstellation, lowPower = false): ConstellationVisual {
  const root = new THREE.Group();
  root.userData = { slug: c.slug, name: c.name, type: 'constellation' };

  const elementColor = new THREE.Color(ZODIAC_ELEMENT_META[c.element].hex);
  const count = lowPower ? 280 : 520;
  const { positions, colors, sizes, starWorld } = buildParticleCloud(c, count);

  const geo = new THREE.BufferGeometry();
  geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
  geo.setAttribute('size', new THREE.BufferAttribute(sizes, 1));

  const particleMat = new THREE.PointsMaterial({
    size: 0.12,
    map: glowTex,
    transparent: true,
    opacity: 0.75,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    vertexColors: true,
    sizeAttenuation: true,
  });

  const particles = new THREE.Points(geo, particleMat);
  particles.userData = { type: 'constellation', slug: c.slug, name: c.name };
  root.add(particles);

  // --- 主星 / 普通星 ---
  const starMats: THREE.SpriteMaterial[] = [];
  const flareMats: THREE.SpriteMaterial[] = [];
  c.stars.forEach((s, idx) => {
    const [x, y, z] = constellationWorldPos(c, s.x, s.y);
    const starMat = new THREE.SpriteMaterial({
      map: glowTex,
      color: s.bright ? 0xfff8e7 : elementColor.clone().lerp(WHITE, 0.45),
      transparent: true,
      opacity: s.bright ? 1 : 0.85,
      blending: THREE.AdditiveBlending,
      depthTest: true,
    });
    const star = new THREE.Sprite(starMat);
    star.position.set(x, y, z);
    star.scale.set(s.bright ? 0.72 : 0.38, s.bright ? 0.72 : 0.38, 1);
    star.userData = { type: 'constellation', slug: c.slug, name: c.name, starIndex: idx };
    root.add(star);
    starMats.push(starMat);

    if (s.bright) {
      const flareMat = new THREE.SpriteMaterial({
        map: flareTex,
        color: 0xfff4d6,
        transparent: true,
        opacity: 0.8,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
      });
      const flare = new THREE.Sprite(flareMat);
      flare.position.set(x, y, z);
      flare.scale.set(1.5, 1.5, 1);
      flare.userData = { type: 'constellation', slug: c.slug, name: c.name };
      root.add(flare);
      flareMats.push(flareMat);
    }
  });

  // --- 渐变连线（顶点色：主星端偏金白，普通端偏元素色） ---
  const linePos: number[] = [];
  const lineColors: number[] = [];
  const endColorFor = (idx: number) => {
    const bright = c.stars[idx]?.bright;
    return bright ? GOLD_BRIGHT.clone().lerp(WHITE, 0.5) : elementColor.clone().lerp(WHITE, 0.2);
  };
  c.edges.forEach(([a, b]) => {
    const sa = starWorld[a];
    const sb = starWorld[b];
    if (!sa || !sb) return;
    linePos.push(sa.x, sa.y, sa.z, sb.x, sb.y, sb.z);
    const ca = endColorFor(a);
    const cb = endColorFor(b);
    lineColors.push(ca.r, ca.g, ca.b, cb.r, cb.g, cb.b);
  });
  const lineGeo = new THREE.BufferGeometry();
  lineGeo.setAttribute('position', new THREE.Float32BufferAttribute(linePos, 3));
  lineGeo.setAttribute('color', new THREE.Float32BufferAttribute(lineColors, 3));
  const lineMat = new THREE.LineBasicMaterial({
    vertexColors: true,
    transparent: true,
    opacity: 0.6,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const lines = new THREE.LineSegments(lineGeo, lineMat);
  lines.userData = { type: 'constellation', slug: c.slug, name: c.name };
  root.add(lines);

  // --- 中心光晕（悬停时点亮） ---
  const [cx, cy, cz] = constellationCenter(c);
  const haloMat = new THREE.SpriteMaterial({
    map: glowTex,
    color: 0xd4af37,
    transparent: true,
    opacity: 0.08,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  const halo = new THREE.Sprite(haloMat);
  halo.position.set(cx, cy, cz);
  halo.scale.set(5.2, 5.2, 1);
  halo.userData = { type: 'constellation', slug: c.slug, name: c.name };
  root.add(halo);

  const label = makeLabel(`${c.symbol} ${c.name}`);
  label.position.set(cx, cy + 1.6, cz);
  root.add(label);

  let highlighted = false;
  let reveal = 1;
  const baseOpacity = 0.75;
  const baseLineOpacity = 0.6;

  function applyState() {
    particleMat.opacity = (highlighted ? 1 : baseOpacity) * reveal;
    particleMat.color.set(highlighted ? 0xf5d76e : 0xffffff);
    lineMat.opacity = (highlighted ? 0.95 : baseLineOpacity) * reveal;
    lineMat.color.set(highlighted ? 0xf5d76e : 0xffffff);
    haloMat.opacity = (highlighted ? 0.3 : 0.08) * reveal;
    starMats.forEach((m) => {
      m.opacity = Math.min(1, (highlighted ? 1.2 : 1) * reveal);
    });
    flareMats.forEach((m) => {
      m.opacity = (highlighted ? 1 : 0.8) * reveal;
      m.color.set(highlighted ? 0xf5d76e : 0xfff4d6);
    });
    (label.material as THREE.SpriteMaterial).opacity = reveal;
    label.scale.set(highlighted ? 3 : 2.4, highlighted ? 0.75 : 0.6, 1);
  }

  return {
    root,
    slug: c.slug,
    particles,
    lines,
    label,
    setHighlight(on: boolean) {
      highlighted = on;
      applyState();
    },
    setRevealFactor(f: number) {
      reveal = Math.max(0, Math.min(1, f));
      applyState();
    },
    tick(time: number) {
      const breathe = 0.92 + Math.sin(time * 0.0012 + c.eclipticLon) * 0.08;
      particles.scale.setScalar(breathe);
      if (!highlighted) {
        particleMat.opacity = (baseOpacity + Math.sin(time * 0.0015 + c.eclipticLon) * 0.08) * reveal;
        lineMat.opacity = (baseLineOpacity + Math.sin(time * 0.001 + c.eclipticLon * 0.5) * 0.12) * reveal;
      }
      flareMats.forEach((m, i) => {
        m.rotation = Math.sin(time * 0.0003 + i) * 0.12;
      });
    },
    dispose() {
      geo.dispose();
      particleMat.dispose();
      lineGeo.dispose();
      lineMat.dispose();
      starMats.forEach((m) => m.dispose());
      flareMats.forEach((m) => m.dispose());
      haloMat.dispose();
      (label.material as THREE.SpriteMaterial).map?.dispose();
      (label.material as THREE.SpriteMaterial).dispose();
    },
  };
}
