import * as THREE from 'three';
import type { Planet } from '../api/orbit';

/**
 * 星系层知识点前置依赖可视化：
 * - 目标星球可挑战/已点亮：青色流动光弧（能量在流向下一颗星）
 * - 目标星球锁定：暗红静止虚线（表示这条前置尚未打通）
 */
export interface DependencyLines {
  group: THREE.Group;
  tick: (timeMs: number) => void;
  dispose: () => void;
}

const flowVertex = /* glsl */ `
attribute float aT;
varying float vT;
void main() {
  vT = aT;
  gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
}
`;

const flowFragment = /* glsl */ `
uniform vec3 uColor;
uniform float uTime;
uniform float uFlow;
uniform float uOpacity;
varying float vT;
void main() {
  float dash = fract(vT * 10.0 - uTime * uFlow);
  float pulse = smoothstep(0.5, 0.0, abs(dash - 0.3));
  // 两端渐隐，避免线头戳进星球
  float endFade = smoothstep(0.0, 0.08, vT) * smoothstep(1.0, 0.92, vT);
  float alpha = (0.22 + 0.78 * pulse) * uOpacity * endFade;
  gl_FragColor = vec4(uColor, alpha);
}
`;

interface LineEntry {
  line: THREE.Line;
  material: THREE.ShaderMaterial;
}

export function buildDependencyLines(
  planets: Planet[],
  positions: Map<string, THREE.Vector3>,
): DependencyLines {
  const group = new THREE.Group();
  const entries: LineEntry[] = [];
  const litSlugs = new Set(
    planets.filter((p) => p.status === 'lit' || p.is_permanent).map((p) => p.slug),
  );

  for (const planet of planets) {
    if (!planet.prerequisites?.length) continue;
    const to = positions.get(planet.slug);
    if (!to) continue;

    for (const prereqSlug of planet.prerequisites) {
      const from = positions.get(prereqSlug);
      if (!from) continue;

      const dist = from.distanceTo(to);
      const mid = from.clone().add(to).multiplyScalar(0.5);
      mid.y += 1.0 + dist * 0.16;
      const curve = new THREE.QuadraticBezierCurve3(from, mid, to);
      const pts = curve.getPoints(42);

      const geo = new THREE.BufferGeometry().setFromPoints(pts);
      const ts = new Float32Array(pts.length);
      for (let i = 0; i < pts.length; i++) ts[i] = i / (pts.length - 1);
      geo.setAttribute('aT', new THREE.BufferAttribute(ts, 1));

      const blocked = planet.status === 'locked' && !litSlugs.has(prereqSlug);
      const material = new THREE.ShaderMaterial({
        uniforms: {
          uColor: { value: blocked ? new THREE.Color(0xb0413e) : new THREE.Color(0x4fd1e8) },
          uTime: { value: 0 },
          uFlow: { value: blocked ? 0 : 0.9 },
          uOpacity: { value: blocked ? 0.5 : 0.75 },
        },
        vertexShader: flowVertex,
        fragmentShader: flowFragment,
        transparent: true,
        depthWrite: false,
        blending: THREE.AdditiveBlending,
      });

      const line = new THREE.Line(geo, material);
      group.add(line);
      entries.push({ line, material });
    }
  }

  return {
    group,
    tick(timeMs: number) {
      const t = timeMs * 0.001;
      for (const e of entries) e.material.uniforms.uTime.value = t;
    },
    dispose() {
      for (const e of entries) {
        e.line.geometry.dispose();
        e.material.dispose();
      }
      entries.length = 0;
    },
  };
}
