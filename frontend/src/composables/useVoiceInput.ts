import { ref } from 'vue';
import { downsampleToPcm16, pcmToBase64 } from '../utils/pcm';

export interface VoiceInputOptions {
  lang?: 'zh_cn' | 'en_us';
  accent?: 'mandarin' | 'cantonese';
  durationMs?: number;
}

function asrUrl(options: VoiceInputOptions) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  const query = new URLSearchParams({
    lang: options.lang || 'zh_cn',
    accent: options.accent || 'mandarin',
  });
  return `${proto}://${window.location.host}/api/ws/asr?${query}`;
}


export function useVoiceInput() {
  const hint = ref('');
  const listening = ref(false);
  let asrWs: WebSocket | null = null;
  let stream: MediaStream | null = null;
  let audioContext: AudioContext | null = null;
  let processor: ScriptProcessorNode | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let timer: number | null = null;

  function releaseAudio() {
    if (timer) window.clearTimeout(timer);
    timer = null;
    processor?.disconnect();
    source?.disconnect();
    stream?.getTracks().forEach((track) => track.stop());
    void audioContext?.close();
    processor = null;
    source = null;
    stream = null;
    audioContext = null;
  }

  function stop() {
    listening.value = false;
    releaseAudio();
    asrWs?.close();
    asrWs = null;
  }

  async function start(onText: (text: string, final: boolean) => void, options: VoiceInputOptions = {}) {
    stop();
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      hint.value = '麦克风需要 HTTPS 或 localhost 安全连接';
      return;
    }
    listening.value = true;
    hint.value = '正在聆听…';
    let transcript = '';
    asrWs = new WebSocket(asrUrl(options));
    asrWs.onmessage = (ev) => {
      const data = JSON.parse(ev.data) as { type?: string; text?: string; detail?: string };
      if (data.type === 'partial' && data.text) {
        transcript += data.text;
        onText(transcript, false);
      }
      if (data.type === 'final') {
        if (data.text && !transcript.endsWith(data.text)) transcript += data.text;
        onText(transcript, true);
      }
      if (data.type === 'error') {
        hint.value = data.detail || '语音识别不可用，请检查讯飞配置';
        stop();
      }
      if (data.type === 'final') {
        hint.value = '识别完成';
        stop();
      }
    };
    asrWs.onerror = () => {
      hint.value = '语音识别连接失败';
      stop();
    };
    asrWs.onopen = async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
        });
        audioContext = new AudioContext();
        source = audioContext.createMediaStreamSource(stream);
        processor = audioContext.createScriptProcessor(4096, 1, 1);
        processor.onaudioprocess = (event) => {
          if (!asrWs || asrWs.readyState !== WebSocket.OPEN || !audioContext) return;
          const pcm = downsampleToPcm16(event.inputBuffer.getChannelData(0), audioContext.sampleRate);
          asrWs.send(JSON.stringify({ type: 'audio', status: 1, audio: pcmToBase64(pcm) }));
        };
        source.connect(processor);
        processor.connect(audioContext.destination);
        timer = window.setTimeout(() => {
          releaseAudio();
          asrWs?.send(JSON.stringify({ type: 'end' }));
          hint.value = '正在识别…';
        }, options.durationMs || 7000);
      } catch (error) {
        const name = error instanceof DOMException ? error.name : '';
        hint.value = name === 'NotAllowedError' ? '麦克风权限被拒绝，请重新授权' : '无法访问麦克风';
        stop();
      }
    };
  }

  return { hint, listening, start, stop };
}
