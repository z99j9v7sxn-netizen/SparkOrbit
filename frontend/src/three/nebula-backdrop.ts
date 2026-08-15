import * as THREE from 'three';
import { ZODIAC_ELEMENT_META, type ZodiacElement } from './zodiac-data';

/**
 * 深空氛围背景：星云层 + 银河带 + 分级背景星（含亮星十字光芒）+ 流星。
 * setElementTint 用于进入星座后按四元素染色星云。
 */
export interface NebulaBackdrop {
  root: THREE.Group;
  tick: (time: number) => void;
  setElementTint: (element: ZodiacElement | null) => void;
  dispose: () => void;
}

const BASE_NEBULA_COLORS = [0x3b55d9, 0x7a3fd0, 0x2277b8, 0xa85a2a, 0x5a35c0, 0x2a8a99, 0x4a3fc0, 0x1e6a9e];

/** 银河带倾斜大圆的法线（与 Points 银河带同一旋转：绕 (1,0,0.3) 轴转 0.9 rad） */
const BAND_NORMAL = new THREE.Vector3(0, 1, 0).applyAxisAngle(
  new THREE.Vector3(1, 0, 0.3).normalize(),
  0.9,
);

function makeNebulaTexture(): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  // 多个偏心径向渐变叠出云絮感
  for (let i = 0; i < 5; i++) {
    const cx = size / 2 + (Math.random() - 0.5) * size * 0.4;
    const cy = size / 2 + (Math.random() - 0.5) * size * 0.4;
    const r = size * (0.22 + Math.random() * 0.28);
    const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, r);
    g.addColorStop(0, `rgba(255,255,255,${0.16 + Math.random() * 0.12})`);
    g.addColorStop(0.55, 'rgba(255,255,255,0.05)');
    g.addColorStop(1, 'rgba(255,255,255,0)');
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, size, size);
  }
  return new THREE.CanvasTexture(canvas);
}

function makeStarSpriteTexture(): THREE.CanvasTexture {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(0.3, 'rgba(255,252,240,0.7)');
  g.addColorStop(1, 'rgba(255,250,230,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

function makeCrossFlareTexture(): THREE.CanvasTexture {
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
    g.addColorStop(0.5, 'rgba(255,250,230,0.9)');
    g.addColorStop(1, 'rgba(255,250,230,0)');
    ctx.fillStyle = g;
    ctx.fillRect(-width / 2, -len, width, len * 2);
    ctx.restore();
  };
  drawRay(0, c * 0.95, 2.4);
  drawRay(Math.PI / 2, c * 0.95, 2.4);
  drawRay(Math.PI / 4, c * 0.5, 1.4);
  drawRay(-Math.PI / 4, c * 0.5, 1.4);
  const g = ctx.createRadialGradient(c, c, 0, c, c, 14);
  g.addColorStop(0, 'rgba(255,255,255,1)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(canvas);
}

/** 深空旋涡星系：椭圆核心 + 两条对数螺旋臂上的碎星点 */
function makeGalaxyTexture(): THREE.CanvasTexture {
  const size = 256;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const ctx = canvas.getContext('2d')!;
  const c = size / 2;

  // 核心辉光
  const core = ctx.createRadialGradient(c, c, 0, c, c, size * 0.16);
  core.addColorStop(0, 'rgba(255,244,220,0.95)');
  core.addColorStop(0.5, 'rgba(255,232,190,0.4)');
  core.addColorStop(1, 'rgba(255,232,190,0)');
  ctx.fillStyle = core;
  ctx.fillRect(0, 0, size, size);

  // 两条螺旋臂
  for (let arm = 0; arm < 2; arm++) {
    const phase = arm * Math.PI;
    for (let t = 0; t < 1; t += 0.012) {
      const ang = phase + t * 4.4;
      const r = size * 0.06 + t * size * 0.4;
      const x = c + Math.cos(ang) * r;
      const y = c + Math.sin(ang) * r * 0.62;
      const alpha = (1 - t) * 0.35;
      const dotR = 1 + Math.random() * 2.2;
      ctx.fillStyle = Math.random() < 0.3
        ? `rgba(255,236,200,${alpha})`
        : `rgba(190,205,255,${alpha})`;
      ctx.beginPath();
      ctx.arc(x + (Math.random() - 0.5) * 9, y + (Math.random() - 0.5) * 7, dotR, 0, Math.PI * 2);
      ctx.fill();
    }
  }
  return new THREE.CanvasTexture(canvas);
}

function makeMeteorTexture(): THREE.CanvasTexture {
  const w = 256;
  const h = 32;
  const canvas = document.createElement('canvas');
  canvas.width = w;
  canvas.height = h;
  const ctx = canvas.getContext('2d')!;
  const g = ctx.createLinearGradient(0, 0, w, 0);
  g.addColorStop(0, 'rgba(245,215,110,0)');
  g.addColorStop(0.75, 'rgba(245,215,110,0.55)');
  g.addColorStop(0.95, 'rgba(255,255,255,0.95)');
  g.addColorStop(1, 'rgba(255,255,255,0)');
  ctx.fillStyle = g;
  ctx.beginPath();
  ctx.ellipse(w / 2, h / 2, w / 2, h / 6, 0, 0, Math.PI * 2);
  ctx.fill();
  return new THREE.CanvasTexture(canvas);
}

/** 渐变天穹：天顶深蓝 → 地平线蓝紫 + 地平辉光 + FBM 银河雾带，替代纯黑背景 */
function makeSkyDomeMaterial(lowPower = false): THREE.ShaderMaterial {
  return new THREE.ShaderMaterial({
    side: THREE.BackSide,
    depthWrite: false,
    depthTest: false,
    fog: false,
    defines: {
      FBM_OCTAVES: lowPower ? 3 : 5,
    },
    uniforms: {
      uZenith: { value: new THREE.Color(0x030718) },
      uHorizon: { value: new THREE.Color(0x131b4d) },
      uNadir: { value: new THREE.Color(0x171236) },
      uGlow: { value: new THREE.Color(0x4a4080) },
      uBandNormal: { value: BAND_NORMAL.clone() },
      uMilky: { value: lowPower ? 0.7 : 1.0 },
    },
    vertexShader: /* glsl */ `
      varying vec3 vDir;
      void main() {
        vDir = normalize(position);
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: /* glsl */ `
      uniform vec3 uZenith;
      uniform vec3 uHorizon;
      uniform vec3 uNadir;
      uniform vec3 uGlow;
      uniform vec3 uBandNormal;
      uniform float uMilky;
      varying vec3 vDir;

      float rand(vec2 co) {
        return fract(sin(dot(co, vec2(12.9898, 78.233))) * 43758.5453);
      }
      float noise2(vec2 p) {
        vec2 i = floor(p);
        vec2 f = fract(p);
        f = f * f * (3.0 - 2.0 * f);
        float a = rand(i);
        float b = rand(i + vec2(1.0, 0.0));
        float c = rand(i + vec2(0.0, 1.0));
        float d = rand(i + vec2(1.0, 1.0));
        return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
      }
      float fbm(vec2 p) {
        float v = 0.0;
        float amp = 0.5;
        for (int i = 0; i < FBM_OCTAVES; i++) {
          v += amp * noise2(p);
          p = p * 2.15 + vec2(13.7, 7.1);
          amp *= 0.52;
        }
        return v;
      }

      void main() {
        vec3 dir = normalize(vDir);
        float h = dir.y;
        vec3 color = h >= 0.0
          ? mix(uHorizon, uZenith, smoothstep(0.0, 0.55, h))
          : mix(uHorizon, uNadir, smoothstep(0.0, 0.5, -h));
        // 地平线附近的微弱辉光带
        color += uGlow * exp(-abs(h) * 5.0) * 0.34;

        // FBM 银河雾带：沿倾斜大圆分布的云絮亮带
        float bd = dot(dir, uBandNormal);
        float band = exp(-bd * bd * 26.0);
        if (band > 0.01) {
          vec3 t1 = normalize(cross(uBandNormal, vec3(0.0, 0.0, 1.0)));
          vec3 t2 = cross(uBandNormal, t1);
          vec2 buv = vec2(dot(dir, t1), dot(dir, t2)) * 5.5;
          float cloud = fbm(buv + vec2(0.0, bd * 9.0));
          float lanes = fbm(buv * 2.4 + vec2(31.0, 17.0));
          // 暗尘埃带切割亮云，形成银河纹理
          float body = cloud * (0.55 + 0.45 * cloud) * (1.0 - 0.55 * smoothstep(0.5, 0.75, lanes));
          vec3 milkyCol = vec3(0.72, 0.68, 0.62) + vec3(0.18, 0.26, 0.5) * cloud;
          color += milkyCol * body * band * 0.24 * uMilky;
        }

        // 极轻噪声抖动，消除渐变条带
        color += (rand(gl_FragCoord.xy) - 0.5) / 128.0;
        gl_FragColor = vec4(color, 1.0);
      }
    `,
  });
}

interface Meteor {
  sprite: THREE.Sprite;
  velocity: THREE.Vector3;
  life: number;
  maxLife: number;
}

function randomSpherePoint(rMin: number, rMax: number): THREE.Vector3 {
  const theta = Math.random() * Math.PI * 2;
  const phi = Math.acos(2 * Math.random() - 1);
  const r = rMin + Math.random() * (rMax - rMin);
  return new THREE.Vector3(
    r * Math.sin(phi) * Math.cos(theta),
    r * Math.sin(phi) * Math.sin(theta),
    r * Math.cos(phi),
  );
}

export function buildNebulaBackdrop(scene: THREE.Scene, lowPower = false): NebulaBackdrop {
  const root = new THREE.Group();
  root.userData = { skipRaycast: true };
  const disposables: Array<{ dispose: () => void }> = [];
  const track = <T extends { dispose: () => void }>(item: T): T => {
    disposables.push(item);
    return item;
  };

  const nebulaTex = track(makeNebulaTexture());
  const starTex = track(makeStarSpriteTexture());
  const flareTex = track(makeCrossFlareTexture());
  const meteorTex = track(makeMeteorTexture());

  // --- 渐变天穹（最先绘制，包住整个场景） ---
  const skyMat = track(makeSkyDomeMaterial(lowPower));
  const skyGeo = track(new THREE.SphereGeometry(180, 48, 32));
  const skyDome = new THREE.Mesh(skyGeo, skyMat);
  skyDome.renderOrder = -10;
  skyDome.frustumCulled = false;
  skyDome.userData = { skipRaycast: true };
  root.add(skyDome);
  const skyBaseGlow = (skyMat.uniforms.uGlow.value as THREE.Color).clone();
  const skyBaseHorizon = (skyMat.uniforms.uHorizon.value as THREE.Color).clone();

  // --- 星云层（远近两层视差：远层大而淡、近层小而饱和） ---
  const nebulaCount = lowPower ? 4 : 8;
  const nebulaSprites: Array<{ sprite: THREE.Sprite; baseColor: THREE.Color; drift: number }> = [];
  for (let i = 0; i < nebulaCount; i++) {
    const far = i < nebulaCount / 2;
    const baseColor = new THREE.Color(BASE_NEBULA_COLORS[i % BASE_NEBULA_COLORS.length]);
    const mat = track(
      new THREE.SpriteMaterial({
        map: nebulaTex,
        color: baseColor.clone(),
        transparent: true,
        opacity: (far ? 0.18 : 0.22) + Math.random() * 0.08,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        fog: false,
        rotation: Math.random() * Math.PI * 2,
      }),
    );
    const sprite = new THREE.Sprite(mat);
    sprite.position.copy(far ? randomSpherePoint(125, 155) : randomSpherePoint(95, 120));
    // 星云集中在中低纬度，避免顶部太密
    sprite.position.y *= 0.55;
    const s = far ? 75 + Math.random() * 85 : 50 + Math.random() * 60;
    sprite.scale.set(s, s * (0.6 + Math.random() * 0.5), 1);
    sprite.userData = { skipRaycast: true };
    root.add(sprite);
    nebulaSprites.push({ sprite, baseColor, drift: (Math.random() - 0.5) * (far ? 0.00004 : 0.00008) });
  }

  // --- 深空点缀：小型旋涡星系 ---
  const galaxySprites: Array<{ sprite: THREE.Sprite; drift: number }> = [];
  if (!lowPower) {
    const galaxyTex = track(makeGalaxyTexture());
    for (let i = 0; i < 3; i++) {
      const mat = track(
        new THREE.SpriteMaterial({
          map: galaxyTex,
          color: i % 2 === 0 ? 0xcfd8ff : 0xffe9c9,
          transparent: true,
          opacity: 0.4 + Math.random() * 0.15,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
          fog: false,
          rotation: Math.random() * Math.PI * 2,
        }),
      );
      const sprite = new THREE.Sprite(mat);
      sprite.position.copy(randomSpherePoint(105, 145));
      sprite.position.y = Math.abs(sprite.position.y) * 0.7 + 12;
      const s = 8 + Math.random() * 7;
      sprite.scale.set(s, s * 0.72, 1);
      sprite.userData = { skipRaycast: true };
      root.add(sprite);
      galaxySprites.push({ sprite, drift: (Math.random() < 0.5 ? -1 : 1) * (0.00004 + Math.random() * 0.00004) });
    }
  }

  // --- 银河带：倾斜大圆上的密集微星 ---
  const bandCount = lowPower ? 1400 : 3200;
  const bandPositions = new Float32Array(bandCount * 3);
  const bandColors = new Float32Array(bandCount * 3);
  const warm = new THREE.Color(0xfff4d6);
  const cool = new THREE.Color(0xdce8ff);
  for (let i = 0; i < bandCount; i++) {
    const a = Math.random() * Math.PI * 2;
    const spread = (Math.random() + Math.random() + Math.random() - 1.5) * 16; // 近似高斯
    const r = 140 + (Math.random() - 0.5) * 30;
    const v = new THREE.Vector3(Math.cos(a) * r, spread, Math.sin(a) * r);
    v.applyAxisAngle(new THREE.Vector3(1, 0, 0.3).normalize(), 0.9);
    bandPositions[i * 3] = v.x;
    bandPositions[i * 3 + 1] = v.y;
    bandPositions[i * 3 + 2] = v.z;
    const c = Math.random() < 0.4 ? warm : cool;
    const dim = 0.4 + Math.random() * 0.6;
    bandColors[i * 3] = c.r * dim;
    bandColors[i * 3 + 1] = c.g * dim;
    bandColors[i * 3 + 2] = c.b * dim;
  }
  const bandGeo = track(new THREE.BufferGeometry());
  bandGeo.setAttribute('position', new THREE.BufferAttribute(bandPositions, 3));
  bandGeo.setAttribute('color', new THREE.BufferAttribute(bandColors, 3));
  const band = new THREE.Points(
    bandGeo,
    track(
      new THREE.PointsMaterial({
        size: 0.32,
        vertexColors: true,
        transparent: true,
        opacity: 0.75,
        depthWrite: false,
        fog: false,
        blending: THREE.AdditiveBlending,
      }),
    ),
  );
  band.userData = { skipRaycast: true };
  root.add(band);

  // --- 分级背景星（3 档大小 × 3 种色温） ---
  const tierSpecs = [
    { count: lowPower ? 1500 : 2800, size: 0.26, opacity: 0.5 },
    { count: lowPower ? 700 : 1400, size: 0.45, opacity: 0.7 },
    { count: lowPower ? 240 : 480, size: 0.75, opacity: 0.9 },
  ];
  const tints = [new THREE.Color(0xfff2cf), new THREE.Color(0xe8f1ff), new THREE.Color(0xf5e9c8)];
  tierSpecs.forEach((spec) => {
    const positions = new Float32Array(spec.count * 3);
    const colors = new Float32Array(spec.count * 3);
    for (let i = 0; i < spec.count; i++) {
      const p = randomSpherePoint(85, 160);
      positions[i * 3] = p.x;
      positions[i * 3 + 1] = p.y;
      positions[i * 3 + 2] = p.z;
      const tint = tints[Math.floor(Math.random() * tints.length)];
      const dim = 0.5 + Math.random() * 0.5;
      colors[i * 3] = tint.r * dim;
      colors[i * 3 + 1] = tint.g * dim;
      colors[i * 3 + 2] = tint.b * dim;
    }
    const geo = track(new THREE.BufferGeometry());
    geo.setAttribute('position', new THREE.BufferAttribute(positions, 3));
    geo.setAttribute('color', new THREE.BufferAttribute(colors, 3));
    const points = new THREE.Points(
      geo,
      track(
        new THREE.PointsMaterial({
          size: spec.size,
          map: starTex,
          vertexColors: true,
          transparent: true,
          opacity: spec.opacity,
          depthWrite: false,
          fog: false,
          blending: THREE.AdditiveBlending,
        }),
      ),
    );
    points.userData = { skipRaycast: true };
    root.add(points);
  });

  // --- 亮星十字光芒 ---
  const flareCount = lowPower ? 8 : 18;
  const flares: THREE.Sprite[] = [];
  for (let i = 0; i < flareCount; i++) {
    const mat = track(
      new THREE.SpriteMaterial({
        map: flareTex,
        color: Math.random() < 0.35 ? 0xf5d76e : 0xffffff,
        transparent: true,
        opacity: 0.55 + Math.random() * 0.35,
        blending: THREE.AdditiveBlending,
        depthWrite: false,
        fog: false,
      }),
    );
    const sprite = new THREE.Sprite(mat);
    sprite.position.copy(randomSpherePoint(90, 150));
    const s = 2.2 + Math.random() * 3;
    sprite.scale.set(s, s, 1);
    sprite.userData = { skipRaycast: true, phase: Math.random() * Math.PI * 2 };
    root.add(sprite);
    flares.push(sprite);
  }

  // --- 流星 ---
  const meteors: Meteor[] = [];
  let nextMeteorAt = performance.now() + 4000 + Math.random() * 6000;

  function spawnMeteor() {
    const mat = new THREE.SpriteMaterial({
      map: meteorTex,
      transparent: true,
      opacity: 0,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
      fog: false,
    });
    const sprite = new THREE.Sprite(mat);
    const start = randomSpherePoint(90, 130);
    start.y = Math.abs(start.y) * 0.8 + 20;
    sprite.position.copy(start);
    const dir = new THREE.Vector3((Math.random() - 0.5) * 2, -0.6 - Math.random() * 0.5, (Math.random() - 0.5) * 2).normalize();
    const speed = 0.55 + Math.random() * 0.5;
    // 使朝向与运动方向一致
    mat.rotation = Math.atan2(-dir.y, dir.x) + Math.PI;
    sprite.scale.set(9 + Math.random() * 6, 1.1, 1);
    sprite.userData = { skipRaycast: true };
    root.add(sprite);
    meteors.push({ sprite, velocity: dir.multiplyScalar(speed), life: 0, maxLife: 90 + Math.random() * 50 });
  }

  scene.add(root);

  return {
    root,
    tick(time: number) {
      // 整个深空背景极缓慢旋转，让静止画面也有活感
      root.rotation.y = time * 0.000018;
      nebulaSprites.forEach((n, i) => {
        const mat = n.sprite.material as THREE.SpriteMaterial;
        mat.rotation += n.drift;
        mat.opacity = 0.18 + Math.sin(time * 0.00025 + i * 1.7) * 0.05 + 0.05;
      });
      galaxySprites.forEach((g) => {
        (g.sprite.material as THREE.SpriteMaterial).rotation += g.drift;
      });
      flares.forEach((f) => {
        const phase = f.userData.phase as number;
        (f.material as THREE.SpriteMaterial).opacity = 0.45 + Math.sin(time * 0.0011 + phase) * 0.3;
      });

      if (!lowPower) {
        if (time > nextMeteorAt && meteors.length < 3) {
          spawnMeteor();
          nextMeteorAt = time + 8000 + Math.random() * 7000;
        }
        for (let i = meteors.length - 1; i >= 0; i--) {
          const m = meteors[i];
          m.life += 1;
          m.sprite.position.add(m.velocity);
          const mat = m.sprite.material as THREE.SpriteMaterial;
          const t = m.life / m.maxLife;
          mat.opacity = t < 0.15 ? t / 0.15 : 1 - (t - 0.15) / 0.85;
          if (m.life >= m.maxLife) {
            root.remove(m.sprite);
            mat.dispose();
            meteors.splice(i, 1);
          }
        }
      }
    },
    setElementTint(element: ZodiacElement | null) {
      nebulaSprites.forEach((n, i) => {
        const mat = n.sprite.material as THREE.SpriteMaterial;
        if (!element) {
          mat.color.copy(n.baseColor);
          return;
        }
        const target = new THREE.Color(ZODIAC_ELEMENT_META[element].nebulaHex);
        // 保留部分原色相，避免全屏单色
        mat.color.copy(n.baseColor).lerp(target, i % 2 === 0 ? 0.75 : 0.45);
      });
    },
    dispose() {
      meteors.forEach((m) => {
        root.remove(m.sprite);
        (m.sprite.material as THREE.Material).dispose();
      });
      meteors.length = 0;
      root.parent?.remove(root);
      disposables.forEach((d) => d.dispose());
    },
  };
}
