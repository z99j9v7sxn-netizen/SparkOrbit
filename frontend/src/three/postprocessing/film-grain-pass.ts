import * as THREE from 'three';
import { Pass, FullScreenQuad } from 'three/examples/jsm/postprocessing/Pass.js';
import { filmGrainFragment, filmGrainVertex } from '../shaders/film-grain.glsl';

export class FilmGrainPass extends Pass {
  readonly material: THREE.ShaderMaterial;
  private readonly quad: FullScreenQuad;
  private readonly uniforms: {
    tDiffuse: { value: THREE.Texture | null };
    uSeed: { value: number };
    uIntensity: { value: number };
  };

  constructor(intensity = 0.05) {
    super();
    this.uniforms = {
      tDiffuse: { value: null },
      uSeed: { value: 0 },
      uIntensity: { value: intensity },
    };
    this.material = new THREE.ShaderMaterial({
      uniforms: this.uniforms,
      vertexShader: filmGrainVertex,
      fragmentShader: filmGrainFragment,
    });
    this.quad = new FullScreenQuad(this.material);
  }

  setIntensity(value: number): void {
    this.uniforms.uIntensity.value = value;
  }

  render(
    renderer: THREE.WebGLRenderer,
    _writeBuffer: THREE.WebGLRenderTarget,
    readBuffer: THREE.WebGLRenderTarget,
  ): void {
    this.uniforms.tDiffuse.value = readBuffer.texture;
    // 每帧独立随机种子：噪点原地闪烁，不沿对角线漂移
    this.uniforms.uSeed.value = Math.random();
    if (this.renderToScreen) {
      renderer.setRenderTarget(null);
      this.quad.render(renderer);
      return;
    }
    renderer.setRenderTarget(this.renderToScreen ? null : _writeBuffer);
    this.quad.render(renderer);
  }

  dispose(): void {
    this.material.dispose();
    this.quad.dispose();
  }
}
