import * as THREE from 'three';
import gsap from 'gsap';
import type { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import type { ParallaxStarfield } from './parallax-starfield';

export interface PlanetInteractionConfig {
  interactionRoot: THREE.Group;
  parallax?: ParallaxStarfield | null;
  controls?: OrbitControls | null;
  lowPower?: boolean;
  touchDevice?: boolean;
  reducedMotion?: boolean;
}

interface HoverRecord {
  mesh: THREE.Mesh;
  halo: THREE.Mesh | null;
  hoverRing: THREE.Mesh | null;
  shell: THREE.Points | null;
  fresnel: THREE.Mesh | null;
  baseFresnelIntensity: number;
  tweens: gsap.core.Animation[];
  baseEmissive: number;
  baseScale: THREE.Vector3;
}

function shaderUniforms(material: THREE.Material): Record<string, THREE.IUniform> | null {
  const uniforms = (material as THREE.ShaderMaterial).uniforms;
  return uniforms ?? null;
}

const POINTER_SMOOTH = 0.08;
const POINTER_DECAY = 0.94;

function prefersReducedMotion(): boolean {
  if (typeof window === 'undefined') return false;
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false;
  return 'ontouchstart' in window || navigator.maxTouchPoints > 0;
}

export class PlanetInteractionController {
  private readonly root: THREE.Group;
  private readonly parallax: ParallaxStarfield | null;
  private readonly controls: OrbitControls | null;
  private readonly parallaxOffsets: THREE.Vector3[] = [];
  private readonly enabled: boolean;
  private readonly tiltStrength: number;
  private readonly parallaxStrength: number;
  private readonly focusStrength: number;

  private targetX = 0;
  private targetY = 0;
  private smoothX = 0;
  private smoothY = 0;
  private paused = false;
  private hoverRecord: HoverRecord | null = null;
  private readonly tweens: gsap.core.Animation[] = [];
  private focusTarget = new THREE.Vector3();
  private focusActive = false;

  private quickTiltX: gsap.QuickToFunc;
  private quickTiltY: gsap.QuickToFunc;

  constructor(config: PlanetInteractionConfig) {
    this.root = config.interactionRoot;
    this.parallax = config.parallax ?? null;
    this.controls = config.controls ?? null;
    this.enabled = !(config.reducedMotion ?? prefersReducedMotion()) && !(config.touchDevice ?? isTouchDevice());

    const powerScale = config.lowPower ? 0.55 : 1;
    this.tiltStrength = 0.16 * powerScale;
    this.parallaxStrength = 3.6 * powerScale;
    this.focusStrength = 0.06 * powerScale;

    this.parallax?.layers.forEach(() => this.parallaxOffsets.push(new THREE.Vector3()));

    this.quickTiltX = gsap.quickTo(this.root.rotation, 'x', { duration: 0.9, ease: 'power2.out' });
    this.quickTiltY = gsap.quickTo(this.root.rotation, 'y', { duration: 0.9, ease: 'power2.out', overwrite: 'auto' });
  }

  get isEnabled(): boolean {
    return this.enabled;
  }

  setPointer(normalizedX: number, normalizedY: number): void {
    if (!this.enabled || this.paused) return;
    this.targetX = THREE.MathUtils.clamp(normalizedX, -1, 1);
    this.targetY = THREE.MathUtils.clamp(normalizedY, -1, 1);
  }

  setPaused(paused: boolean): void {
    this.paused = paused;
    if (paused) {
      this.targetX = 0;
      this.targetY = 0;
      this.quickTiltX(0);
      this.quickTiltY(0);
      this.resetParallaxOffsets(true);
      this.focusActive = false;
    }
  }

  tick(): void {
    if (!this.enabled || this.paused) return;

    this.smoothX += (this.targetX - this.smoothX) * POINTER_SMOOTH;
    this.smoothY += (this.targetY - this.smoothY) * POINTER_SMOOTH;

    if (Math.abs(this.targetX) < 0.01 && Math.abs(this.targetY) < 0.01) {
      this.smoothX *= POINTER_DECAY;
      this.smoothY *= POINTER_DECAY;
    }

    this.quickTiltX(-this.smoothY * this.tiltStrength);
    this.quickTiltY(this.smoothX * this.tiltStrength * 0.55);
    this.applyParallax();
    this.applyCameraFocus();
  }

  private applyParallax(): void {
    if (!this.parallax) return;
    this.parallax.layers.forEach(({ group }, index) => {
      const depth = (index + 1) * this.parallaxStrength;
      const offset = this.parallaxOffsets[index];
      offset.x += (this.smoothX * depth - offset.x) * 0.1;
      offset.y += (-this.smoothY * depth * 0.65 - offset.y) * 0.1;
      group.position.copy(offset);
    });
  }

  private applyCameraFocus(): void {
    if (!this.controls || !this.focusActive) return;
    this.controls.target.lerp(this.focusTarget, this.focusStrength);
  }

  private resetParallaxOffsets(animate = false): void {
    if (!this.parallax) return;
    this.parallax.layers.forEach(({ group }, index) => {
      const offset = this.parallaxOffsets[index];
      if (animate) {
        const tween = gsap.to(offset, {
          x: 0,
          y: 0,
          z: 0,
          duration: 0.8,
          ease: 'power2.out',
          onUpdate: () => group.position.copy(offset),
        });
        this.tweens.push(tween);
      } else {
        offset.set(0, 0, 0);
        group.position.set(0, 0, 0);
      }
    });
  }

  setHover(mesh: THREE.Mesh | null): void {
    if (this.hoverRecord?.mesh === mesh) return;
    this.clearHover();

    if (!mesh) {
      this.focusActive = false;
      if (this.controls) {
        const tween = gsap.to(this.controls.target, {
          x: 0,
          y: 0,
          z: 0,
          duration: 0.8,
          ease: 'power2.out',
        });
        this.tweens.push(tween);
      }
      return;
    }

    const userRing = mesh.userData.hoverRing as THREE.Mesh | undefined;
    const shell = mesh.userData.shell as THREE.Points | undefined;
    const fresnel = mesh.userData.fresnel as THREE.Mesh | undefined;
    const shellMat = shell?.material as THREE.ShaderMaterial | undefined;
    const fresnelMat = fresnel?.material as THREE.ShaderMaterial | undefined;
    const baseFresnelIntensity = (mesh.userData.baseFresnelIntensity as number) ?? (fresnelMat?.uniforms?.uIntensity?.value ?? 0.38);
    const mat = mesh.material as THREE.MeshStandardMaterial | THREE.MeshBasicMaterial;
    const baseEmissive = 'emissiveIntensity' in mat ? (mat.emissiveIntensity ?? 0.5) : 0.5;
    const baseScale = mesh.scale.clone();
    const bodyUniforms = shaderUniforms(mesh.material as THREE.Material);
    const color = (mesh.userData.baseColor as THREE.Color | undefined)?.clone()
      ?? ('emissive' in mat && mat.emissive?.clone ? mat.emissive.clone() : new THREE.Color(0x7dd3fc));

    let halo: THREE.Mesh | null = null;
    if (mesh.userData.type !== 'galaxy') {
      halo = new THREE.Mesh(
        new THREE.SphereGeometry(1.05, 24, 24),
        new THREE.MeshBasicMaterial({
          color,
          transparent: true,
          opacity: 0.14,
          blending: THREE.AdditiveBlending,
          depthWrite: false,
        }),
      );
      halo.scale.copy(mesh.scale).multiplyScalar(1.35);
      halo.position.copy(mesh.position);
      mesh.parent?.add(halo);
    }

    const tweens: gsap.core.Animation[] = [];

    if (userRing) {
      tweens.push(
        gsap.to(userRing.material, { opacity: 0.65, duration: 0.35, ease: 'power2.out' }),
        gsap.to(userRing.scale, { x: 1.08, y: 1.08, z: 1.08, duration: 0.42, ease: 'power2.out' }),
      );
    }

    if (this.enabled) {
      tweens.push(
        gsap.to(mesh.scale, {
          x: baseScale.x * 1.12,
          y: baseScale.y * 1.12,
          z: baseScale.z * 1.12,
          duration: 0.42,
          ease: 'power2.out',
        }),
      );
      if ('emissiveIntensity' in mat) {
        tweens.push(
          gsap.to(mat, {
            emissiveIntensity: baseEmissive * 2.1 + 0.35,
            duration: 0.35,
            ease: 'power2.out',
          }),
        );
      }
      if (bodyUniforms?.uHover) {
        tweens.push(
          gsap.to(bodyUniforms.uHover, { value: 1, duration: 0.4, ease: 'power2.out' }),
        );
      }
      if (shellMat?.uniforms?.uHover) {
        tweens.push(
          gsap.to(shellMat.uniforms.uHover, { value: 1, duration: 0.45, ease: 'power2.out' }),
        );
      }
      if (fresnelMat?.uniforms?.uIntensity) {
        tweens.push(
          gsap.to(fresnelMat.uniforms.uIntensity, {
            value: baseFresnelIntensity * 2.3 + 0.18,
            duration: 0.4,
            ease: 'power2.out',
          }),
        );
      }
      if (halo) {
        tweens.push(
          gsap.to(halo.scale, {
            x: baseScale.x * 1.55,
            y: baseScale.y * 1.55,
            z: baseScale.z * 1.55,
            duration: 0.55,
            ease: 'sine.out',
          }),
          gsap.to(halo.material, { opacity: 0.28, duration: 0.45, ease: 'sine.out' }),
        );
      }
    }

    const worldPos = mesh.getWorldPosition(new THREE.Vector3());
    this.focusTarget.copy(worldPos);
    this.focusActive = true;

    this.hoverRecord = {
      mesh,
      halo,
      hoverRing: userRing ?? null,
      shell: shell ?? null,
      fresnel: fresnel ?? null,
      baseFresnelIntensity,
      tweens,
      baseEmissive,
      baseScale,
    };
    this.tweens.push(...tweens);
  }

  clearHover(): void {
    if (!this.hoverRecord) return;
    const { mesh, halo, hoverRing, shell, fresnel, baseFresnelIntensity, tweens, baseEmissive, baseScale } = this.hoverRecord;

    tweens.forEach((t) => t.kill());

    const mat = mesh.material as THREE.MeshStandardMaterial;
    const restore = gsap.timeline();
    restore.to(mesh.scale, { x: baseScale.x, y: baseScale.y, z: baseScale.z, duration: 0.35, ease: 'power2.out' });
    if ('emissiveIntensity' in mat) {
      restore.to(mat, { emissiveIntensity: baseEmissive, duration: 0.3, ease: 'power2.out' }, 0);
    }

    const bodyUniforms = shaderUniforms(mesh.material as THREE.Material);
    if (bodyUniforms?.uHover) {
      restore.to(bodyUniforms.uHover, { value: 0, duration: 0.32, ease: 'power2.out' }, 0);
    }

    const shellMat = shell?.material as THREE.ShaderMaterial | undefined;
    if (shellMat?.uniforms?.uHover) {
      restore.to(shellMat.uniforms.uHover, { value: 0, duration: 0.35, ease: 'power2.out' }, 0);
    }

    const fresnelMat = fresnel?.material as THREE.ShaderMaterial | undefined;
    if (fresnelMat?.uniforms?.uIntensity) {
      restore.to(fresnelMat.uniforms.uIntensity, { value: baseFresnelIntensity, duration: 0.32, ease: 'power2.out' }, 0);
    }

    if (hoverRing) {
      restore.to(hoverRing.material, { opacity: 0, duration: 0.28, ease: 'power1.out' }, 0);
      restore.to(hoverRing.scale, { x: 1, y: 1, z: 1, duration: 0.28, ease: 'power1.out' }, 0);
    }

    if (halo) {
      restore.to(halo.material, {
        opacity: 0,
        duration: 0.28,
        ease: 'power1.out',
        onComplete: () => {
          halo.parent?.remove(halo);
          halo.geometry.dispose();
          (halo.material as THREE.Material).dispose();
        },
      }, 0);
    }

    this.tweens.push(restore);
    this.hoverRecord = null;
  }

  dispose(): void {
    this.clearHover();
    this.tweens.forEach((t) => t.kill());
    this.tweens.length = 0;
    this.root.rotation.set(0, 0, 0);
    this.resetParallaxOffsets(false);
  }
}
