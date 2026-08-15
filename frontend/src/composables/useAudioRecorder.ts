import { onBeforeUnmount, ref } from 'vue';

const MAX_DURATION_SEC = 60;

const DEFAULT_MIME_CANDIDATES = ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4'];
const CANTONESE_MIME_CANDIDATES = ['audio/mp4', 'audio/ogg;codecs=opus', 'audio/ogg', 'audio/webm;codecs=opus', 'audio/webm'];

function pickMimeType(candidates: string[] = DEFAULT_MIME_CANDIDATES): string {
  for (const type of candidates) {
    if (typeof MediaRecorder !== 'undefined' && MediaRecorder.isTypeSupported(type)) {
      return type;
    }
  }
  return '';
}

function formatElapsed(sec: number): string {
  const m = Math.floor(sec / 60);
  const s = sec % 60;
  return `${m}:${String(s).padStart(2, '0')}`;
}

export function useAudioRecorder(options?: { preferMimeTypes?: string[] | (() => string[]) }) {
  const recording = ref(false);
  const elapsedSec = ref(0);
  const blob = ref<Blob | null>(null);
  const objectUrl = ref('');
  const error = ref('');
  const mimeType = ref('');

  let mediaStream: MediaStream | null = null;
  let recorder: MediaRecorder | null = null;
  let chunks: BlobPart[] = [];
  let tickTimer: number | null = null;
  let maxTimer: number | null = null;

  const resolveMimeCandidates = (): string[] => {
    const pref = options?.preferMimeTypes;
    if (typeof pref === 'function') {
      const resolved = pref();
      return resolved?.length ? resolved : DEFAULT_MIME_CANDIDATES;
    }
    return pref ?? DEFAULT_MIME_CANDIDATES;
  };

  function revokeUrl() {
    if (objectUrl.value) {
      URL.revokeObjectURL(objectUrl.value);
      objectUrl.value = '';
    }
  }

  function clearTimers() {
    if (tickTimer) window.clearInterval(tickTimer);
    if (maxTimer) window.clearTimeout(maxTimer);
    tickTimer = null;
    maxTimer = null;
  }

  function releaseStream() {
    mediaStream?.getTracks().forEach((t) => t.stop());
    mediaStream = null;
  }

  function reset() {
    clearTimers();
    if (recorder && recorder.state !== 'inactive') {
      try {
        recorder.stop();
      } catch {
        /* ignore */
      }
    }
    recorder = null;
    chunks = [];
    releaseStream();
    revokeUrl();
    recording.value = false;
    elapsedSec.value = 0;
    blob.value = null;
    error.value = '';
    mimeType.value = '';
  }

  async function start() {
    reset();
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      error.value = '麦克风需要 HTTPS 或 localhost 安全连接';
      return;
    }
    if (typeof MediaRecorder === 'undefined') {
      error.value = '当前浏览器不支持录音';
      return;
    }
    try {
      mediaStream = await navigator.mediaDevices.getUserMedia({
        audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
      });
      const mime = pickMimeType(resolveMimeCandidates());
      mimeType.value = mime;
      recorder = mime ? new MediaRecorder(mediaStream, { mimeType: mime }) : new MediaRecorder(mediaStream);
      chunks = [];
      recorder.ondataavailable = (ev) => {
        if (ev.data.size > 0) chunks.push(ev.data);
      };
      recorder.onstop = () => {
        const type = mimeType.value || 'audio/webm';
        const result = new Blob(chunks, { type });
        blob.value = result;
        revokeUrl();
        objectUrl.value = URL.createObjectURL(result);
        releaseStream();
        clearTimers();
        recording.value = false;
      };
      recorder.onerror = () => {
        error.value = '录音失败，请重试';
        stop();
      };
      recorder.start(250);
      recording.value = true;
      elapsedSec.value = 0;
      tickTimer = window.setInterval(() => {
        elapsedSec.value += 1;
      }, 1000);
      maxTimer = window.setTimeout(() => {
        stop();
      }, MAX_DURATION_SEC * 1000);
    } catch (err) {
      const name = err instanceof DOMException ? err.name : '';
      error.value = name === 'NotAllowedError' ? '麦克风权限被拒绝，请重新授权' : '无法访问麦克风';
      releaseStream();
      recording.value = false;
    }
  }

  function stop() {
    clearTimers();
    if (recorder && recorder.state !== 'inactive') {
      try {
        recorder.stop();
      } catch {
        recording.value = false;
        releaseStream();
      }
    } else {
      recording.value = false;
      releaseStream();
    }
  }

  onBeforeUnmount(reset);

  return {
    recording,
    elapsedSec,
    blob,
    objectUrl,
    error,
    mimeType,
    maxDurationSec: MAX_DURATION_SEC,
    formatElapsed,
    start,
    stop,
    reset,
  };
}

export { CANTONESE_MIME_CANDIDATES, DEFAULT_MIME_CANDIDATES };
