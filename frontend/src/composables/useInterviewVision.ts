import { onBeforeUnmount, ref } from 'vue';

const MAX_FRAMES = 4;
const LONG_SIDE = 512;
const JPEG_QUALITY = 0.6;
const INTERVAL_MS = 4000;

export function useInterviewVision() {
  const previewRef = ref<HTMLVideoElement | null>(null);
  const enabled = ref(false);
  const error = ref('');
  const captured = ref(0);

  let stream: MediaStream | null = null;
  let timer: number | null = null;
  let onFrame: ((dataUrl: string) => void) | null = null;
  let gateOpen = false;

  function captureFrame(): string | null {
    const video = previewRef.value;
    if (!video || video.readyState < 2 || video.videoWidth < 8) return null;
    const w = video.videoWidth;
    const h = video.videoHeight;
    const scale = LONG_SIDE / Math.max(w, h);
    const cw = Math.max(1, Math.round(w * scale));
    const ch = Math.max(1, Math.round(h * scale));
    const canvas = document.createElement('canvas');
    canvas.width = cw;
    canvas.height = ch;
    const ctx = canvas.getContext('2d');
    if (!ctx) return null;
    ctx.drawImage(video, 0, 0, cw, ch);
    return canvas.toDataURL('image/jpeg', JPEG_QUALITY);
  }

  function tick() {
    if (!gateOpen || captured.value >= MAX_FRAMES || !onFrame) return;
    const data = captureFrame();
    if (!data) return;
    captured.value += 1;
    onFrame(data);
  }

  async function start(sendFrame: (dataUrl: string) => void) {
    if (enabled.value) {
      onFrame = sendFrame;
      return;
    }
    error.value = '';
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      error.value = '摄像头需要 HTTPS 或 localhost';
      return;
    }
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { facingMode: 'user', width: { ideal: 640 }, height: { ideal: 480 } },
        audio: false,
      });
      onFrame = sendFrame;
      enabled.value = true;
      await new Promise<void>((resolve) => {
        const bind = () => {
          const el = previewRef.value;
          if (!el) {
            window.setTimeout(bind, 50);
            return;
          }
          el.srcObject = stream;
          el.muted = true;
          el.playsInline = true;
          void el.play().finally(() => resolve());
        };
        bind();
      });
      timer = window.setInterval(tick, INTERVAL_MS);
    } catch (err) {
      enabled.value = false;
      error.value =
        err instanceof DOMException && err.name === 'NotAllowedError' ? '摄像头权限被拒绝' : '无法打开摄像头';
    }
  }

  function setMicOpen(open: boolean) {
    gateOpen = open;
    if (open) {
      captured.value = 0;
      window.setTimeout(tick, 600);
    }
  }

  function stop() {
    if (timer) window.clearInterval(timer);
    timer = null;
    onFrame = null;
    gateOpen = false;
    captured.value = 0;
    stream?.getTracks().forEach((t) => t.stop());
    stream = null;
    if (previewRef.value) previewRef.value.srcObject = null;
    enabled.value = false;
  }

  onBeforeUnmount(stop);

  return { previewRef, enabled, error, captured, start, stop, setMicOpen };
}
