/** 将已录制的音频 Blob 通过现有 /api/ws/asr 转写为文本。 */

export type AsrLang = 'zh_cn' | 'en_us';
export type AsrAccent = 'mandarin' | 'cantonese';

function asrUrl(lang: AsrLang, accent: AsrAccent) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const query = new URLSearchParams({ lang, accent });
  return `${proto}://${window.location.host}/api/ws/asr?${query}`;
}

function downsampleToPcm16(input: Float32Array, sourceRate: number, targetRate = 16000): Int16Array {
  const ratio = sourceRate / targetRate;
  const length = Math.max(1, Math.floor(input.length / ratio));
  const result = new Int16Array(length);
  for (let i = 0; i < length; i++) {
    const start = Math.floor(i * ratio);
    const end = Math.min(input.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += input[j];
    const sample = Math.max(-1, Math.min(1, sum / Math.max(1, end - start)));
    result[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff;
  }
  return result;
}

function pcmToBase64(pcm: Int16Array): string {
  const bytes = new Uint8Array(pcm.buffer);
  let binary = '';
  for (let offset = 0; offset < bytes.length; offset += 8192) {
    binary += String.fromCharCode(...bytes.subarray(offset, offset + 8192));
  }
  return btoa(binary);
}

/** 将 AudioBuffer 拆成约 40ms 的 PCM16 帧并 base64 编码。 */
function bufferToPcmFrames(buffer: AudioBuffer, frameMs = 40): string[] {
  const channel = buffer.getChannelData(0);
  const pcm = downsampleToPcm16(channel, buffer.sampleRate, 16000);
  const samplesPerFrame = Math.max(1, Math.floor((16000 * frameMs) / 1000));
  const frames: string[] = [];
  for (let offset = 0; offset < pcm.length; offset += samplesPerFrame) {
    const slice = pcm.subarray(offset, Math.min(pcm.length, offset + samplesPerFrame));
    frames.push(pcmToBase64(slice));
  }
  return frames.length ? frames : [pcmToBase64(new Int16Array(160))];
}

/**
 * 对录音 Blob 做离线转写。失败时抛出 Error，调用方可降级为空字符串。
 */
export function transcribeAudioBlob(
  blob: Blob,
  options: { lang?: AsrLang; accent?: AsrAccent; timeoutMs?: number } = {},
): Promise<string> {
  const lang = options.lang || 'zh_cn';
  const accent = options.accent || 'mandarin';
  const timeoutMs = options.timeoutMs ?? 45000;

  return new Promise((resolve, reject) => {
    let settled = false;
    let transcript = '';
    const ws = new WebSocket(asrUrl(lang, accent));
    const timer = window.setTimeout(() => {
      if (settled) return;
      settled = true;
      ws.close();
      reject(new Error('语音识别超时'));
    }, timeoutMs);

    const finish = (ok: boolean, value: string, err?: Error) => {
      if (settled) return;
      settled = true;
      window.clearTimeout(timer);
      try {
        ws.close();
      } catch {
        /* ignore */
      }
      if (ok) resolve(value);
      else reject(err || new Error('语音识别失败'));
    };

    ws.onerror = () => finish(false, '', new Error('语音识别连接失败'));
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as { type?: string; text?: string; detail?: string };
        if (data.type === 'partial' && data.text) {
          transcript += data.text;
        }
        if (data.type === 'final') {
          if (data.text) transcript = data.text;
          finish(true, transcript.trim());
        }
        if (data.type === 'error') {
          finish(false, '', new Error(data.detail || '语音识别不可用'));
        }
      } catch {
        finish(false, '', new Error('语音识别响应异常'));
      }
    };

    ws.onopen = async () => {
      try {
        const arrayBuffer = await blob.arrayBuffer();
        const audioCtx = new AudioContext();
        try {
          const decoded = await audioCtx.decodeAudioData(arrayBuffer.slice(0));
          const frames = bufferToPcmFrames(decoded);
          for (const audio of frames) {
            if (ws.readyState !== WebSocket.OPEN) break;
            ws.send(JSON.stringify({ type: 'audio', status: 1, audio }));
          }
          if (ws.readyState === WebSocket.OPEN) {
            ws.send(JSON.stringify({ type: 'end' }));
          }
        } finally {
          await audioCtx.close();
        }
      } catch (error) {
        finish(false, '', error instanceof Error ? error : new Error('音频解码失败'));
      }
    };
  });
}

export function cabinAsrOptions(cabinId: string): { lang: AsrLang; accent: AsrAccent } {
  if (cabinId === 'cantonese') return { lang: 'zh_cn', accent: 'cantonese' };
  if (
    cabinId.startsWith('cet') ||
    cabinId === 'ielts-speaking' ||
    cabinId === 'daily-english' ||
    cabinId.includes('english') ||
    cabinId.includes('listening')
  ) {
    return { lang: 'en_us', accent: 'mandarin' };
  }
  return { lang: 'zh_cn', accent: 'mandarin' };
}
