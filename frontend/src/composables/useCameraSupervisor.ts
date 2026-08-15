import { onBeforeUnmount, ref, shallowRef } from 'vue';
import { clearSupervisionFrame, reportSupervisionEvent, uploadSupervisionFrame } from '../api/study';

type Detection = { class: string; score: number };
type ObjectDetection = { detect: (video: HTMLVideoElement) => Promise<Detection[]> };

type TfGlobal = {
  ready: () => Promise<void>;
  setBackend: (name: string) => Promise<boolean> | boolean;
  getBackend: () => string;
};

type CocoSsdGlobal = {
  load: (config?: { base?: string; modelUrl?: string }) => Promise<ObjectDetection>;
};

declare global {
  interface Window {
    tf?: TfGlobal;
    cocoSsd?: CocoSsdGlobal;
  }
}

const SCRIPT_TF = '/vendor/tf.min.js';
const SCRIPT_COCO = '/vendor/coco-ssd.min.js';
const MODEL_URL = '/models/coco-ssd/model.json';
/** 向教师端巡查上传截图的间隔（毫秒） */
const FRAME_UPLOAD_MS = 3500;

const scriptPromises = new Map<string, Promise<void>>();

function loadScript(src: string): Promise<void> {
  const existing = scriptPromises.get(src);
  if (existing) return existing;

  const promise = new Promise<void>((resolve, reject) => {
    const found = document.querySelector<HTMLScriptElement>(`script[data-spark-vendor="${src}"]`);
    if (found) {
      if (found.dataset.loaded === '1') {
        resolve();
        return;
      }
      found.addEventListener('load', () => resolve(), { once: true });
      found.addEventListener('error', () => reject(new Error(`脚本加载失败: ${src}`)), { once: true });
      return;
    }
    const el = document.createElement('script');
    el.src = src;
    el.async = true;
    el.dataset.sparkVendor = src;
    el.onload = () => {
      el.dataset.loaded = '1';
      resolve();
    };
    el.onerror = () => reject(new Error(`脚本加载失败: ${src}`));
    document.head.appendChild(el);
  });

  scriptPromises.set(src, promise);
  return promise;
}

async function loadModelViaUmd(): Promise<ObjectDetection> {
  await loadScript(SCRIPT_TF);
  await loadScript(SCRIPT_COCO);

  const tf = window.tf;
  const cocoSsd = window.cocoSsd;
  if (!tf || !cocoSsd) {
    throw new Error('TensorFlow.js 全局对象未挂载，请确认 /vendor 脚本可访问');
  }

  try {
    await tf.setBackend('webgl');
    await tf.ready();
  } catch (webglErr) {
    console.warn('WebGL backend unavailable, falling back to CPU:', webglErr);
    await tf.setBackend('cpu');
    await tf.ready();
  }
  console.info('coco-ssd tfjs backend (UMD):', tf.getBackend());

  return cocoSsd.load({
    base: 'lite_mobilenet_v2',
    modelUrl: MODEL_URL,
  });
}

export function useCameraSupervisor(onWarn: (message: string) => void) {
  const active = ref(false);
  const warning = ref('');
  const mediaStream = shallowRef<MediaStream | null>(null);
  let video: HTMLVideoElement | null = null;
  let stream: MediaStream | null = null;
  let raf = 0;
  let model: ObjectDetection | null = null;
  let phoneFrames = 0;
  let awayFrames = 0;
  let lastWarn = 0;
  let detecting = false;
  let frameTimer: number | null = null;
  let uploadingFrame = false;
  let captureCanvas: HTMLCanvasElement | null = null;

  function report(kind: 'phone' | 'away', message: string) {
    onWarn(message);
    void reportSupervisionEvent(kind, message).catch((err) => {
      console.warn('supervision report failed:', err);
    });
  }

  function captureFrameBlob(): Promise<Blob | null> {
    if (!video || video.readyState < 2) return Promise.resolve(null);
    const width = video.videoWidth || 320;
    const height = video.videoHeight || 240;
    if (!captureCanvas) captureCanvas = document.createElement('canvas');
    captureCanvas.width = width;
    captureCanvas.height = height;
    const ctx = captureCanvas.getContext('2d');
    if (!ctx) return Promise.resolve(null);
    ctx.drawImage(video, 0, 0, width, height);
    return new Promise((resolve) => {
      captureCanvas!.toBlob((blob) => resolve(blob), 'image/jpeg', 0.72);
    });
  }

  async function uploadFrameOnce() {
    if (!active.value || uploadingFrame) return;
    uploadingFrame = true;
    try {
      const blob = await captureFrameBlob();
      if (!blob || !active.value) return;
      await uploadSupervisionFrame(blob);
    } catch (err) {
      console.warn('supervision frame upload failed:', err);
    } finally {
      uploadingFrame = false;
    }
  }

  function startFrameUploads() {
    stopFrameUploads();
    void uploadFrameOnce();
    frameTimer = window.setInterval(() => {
      void uploadFrameOnce();
    }, FRAME_UPLOAD_MS);
  }

  function stopFrameUploads() {
    if (frameTimer) {
      window.clearInterval(frameTimer);
      frameTimer = null;
    }
  }

  async function start() {
    if (active.value) return;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      warning.value = '摄像头需要安全连接，请使用 https 地址或本机 localhost 访问';
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: 320, height: 240 },
        audio: false,
      });
      mediaStream.value = stream;
      video = document.createElement('video');
      video.srcObject = stream;
      video.muted = true;
      video.playsInline = true;
      await video.play();
      active.value = true;
      warning.value = '';
      startFrameUploads();
      try {
        model = model ?? (await loadModelViaUmd());
        loop();
      } catch (err) {
        console.error('coco-ssd model load failed:', err);
        const detail =
          err instanceof Error ? err.message : typeof err === 'string' ? err : String(err ?? 'unknown');
        warning.value = `检测模型加载失败：${detail}，已保留摄像头画面`;
      }
    } catch (error) {
      const name = error instanceof DOMException ? error.name : '';
      const messages: Record<string, string> = {
        NotAllowedError: '摄像头权限被拒绝，请在浏览器地址栏中重新授权',
        NotFoundError: '未检测到可用摄像头，请检查设备连接',
        NotReadableError: '摄像头正被其他程序占用，请关闭后重试',
        OverconstrainedError: '摄像头不支持所需画面参数',
        SecurityError: '浏览器安全策略阻止了摄像头访问',
      };
      warning.value = messages[name] || '摄像头启动失败，请刷新页面后重试';
      stream?.getTracks().forEach((track) => track.stop());
      stream = null;
      mediaStream.value = null;
    }
  }

  function stop() {
    active.value = false;
    stopFrameUploads();
    cancelAnimationFrame(raf);
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    mediaStream.value = null;
    video = null;
    phoneFrames = 0;
    awayFrames = 0;
    warning.value = '';
    void clearSupervisionFrame().catch((err) => {
      console.warn('clear supervision frame failed:', err);
    });
  }

  async function loop() {
    if (!active.value || !video || !model || detecting) {
      if (active.value) raf = requestAnimationFrame(loop);
      return;
    }
    detecting = true;
    try {
      const preds = await model.detect(video);
      const phone = preds.some((p) => p.class === 'cell phone' && p.score > 0.45);
      const person = preds.some((p) => p.class === 'person' && p.score > 0.35);

      if (phone) {
        phoneFrames += 1;
        if (phoneFrames > 6 && Date.now() - lastWarn > 12000) {
          lastWarn = Date.now();
          warning.value = '检测到手机，请回到学习状态';
          report('phone', '检测到你在使用手机，快回来学习吧！');
          phoneFrames = 0;
        }
      } else {
        phoneFrames = Math.max(0, phoneFrames - 1);
        if (phoneFrames === 0 && warning.value.includes('手机') && person) {
          warning.value = '';
        }
      }

      if (!person) {
        awayFrames += 1;
        if (awayFrames > 45 && Date.now() - lastWarn > 12000) {
          lastWarn = Date.now();
          warning.value = '似乎离开了摄像头视野';
          report('away', '检测到你离开了学习区域，请保持专注');
          awayFrames = 0;
        }
      } else {
        awayFrames = 0;
        if (warning.value.includes('离开') || warning.value.includes('视野')) {
          warning.value = '';
        }
        if (!phone && phoneFrames === 0 && warning.value.includes('手机')) {
          warning.value = '';
        }
      }
    } catch {
      /* ignore frame errors */
    } finally {
      detecting = false;
      if (active.value) raf = requestAnimationFrame(loop);
    }
  }

  onBeforeUnmount(stop);

  return { active, warning, mediaStream, start, stop };
}
