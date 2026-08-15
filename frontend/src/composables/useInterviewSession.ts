import { onBeforeUnmount, ref } from 'vue';
import { useAuthStore } from '../stores/auth';
import { interviewWsUrl, type InterviewTurn } from '../api/interview';
import { downsampleToPcm16, pcmToBase64 } from '../utils/pcm';

export type MicGate = 'closed' | 'open';
export type InterviewPhase = 'idle' | 'asking' | 'answering' | 'scoring' | 'finishing';

export interface InterviewQuestionEvent {
  index: number;
  total: number;
  kind: string;
  kind_label: string;
  text: string;
}

export interface AgentStepLog {
  role: string;
  content: string;
}

export function useInterviewSession() {
  const auth = useAuthStore();
  const connected = ref(false);
  const micGate = ref<MicGate>('closed');
  const caption = ref('');
  const question = ref<InterviewQuestionEvent | null>(null);
  const lastTurn = ref<InterviewTurn | null>(null);
  const reportId = ref('');
  const overallScore = ref<number | null>(null);
  const statusHint = ref('');
  const error = ref('');
  const speaking = ref(false);
  const followupHint = ref('');
  const phase = ref<InterviewPhase>('idle');
  const progressText = ref('');
  const sessionEnded = ref(false);
  const agentLog = ref<AgentStepLog[]>([]);

  let ws: WebSocket | null = null;
  let heartbeatTimer: number | null = null;
  let reconnectTimer: number | null = null;
  let intentionalClose = false;
  let sessionId = '';
  let mediaStream: MediaStream | null = null;
  let audioContext: AudioContext | null = null;
  let source: MediaStreamAudioSourceNode | null = null;
  let worklet: AudioWorkletNode | null = null;

  function send(payload: Record<string, unknown>) {
    if (!ws || ws.readyState !== WebSocket.OPEN) return;
    ws.send(JSON.stringify({ ...payload, token: auth.token }));
  }

  async function startMic() {
    if (mediaStream) return;
    if (!window.isSecureContext || !navigator.mediaDevices?.getUserMedia) {
      error.value = '麦克风需要 HTTPS 或 localhost 安全连接';
      return;
    }
    mediaStream = await navigator.mediaDevices.getUserMedia({
      audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true },
    });
    audioContext = new AudioContext();
    await audioContext.audioWorklet.addModule('/worklets/pcm-worklet.js');
    source = audioContext.createMediaStreamSource(mediaStream);
    worklet = new AudioWorkletNode(audioContext, 'interview-pcm');
    worklet.port.onmessage = (ev: MessageEvent<Float32Array>) => {
      if (micGate.value !== 'open' || !audioContext) return;
      const pcm = downsampleToPcm16(ev.data, audioContext.sampleRate);
      send({ type: 'audio', audio: pcmToBase64(pcm), status: 1 });
    };
    source.connect(worklet);
    const mute = audioContext.createGain();
    mute.gain.value = 0;
    worklet.connect(mute);
    mute.connect(audioContext.destination);
  }

  function stopMic() {
    worklet?.disconnect();
    source?.disconnect();
    mediaStream?.getTracks().forEach((t) => t.stop());
    void audioContext?.close();
    worklet = null;
    source = null;
    mediaStream = null;
    audioContext = null;
  }

  function disconnect() {
    intentionalClose = true;
    if (heartbeatTimer) window.clearInterval(heartbeatTimer);
    if (reconnectTimer) window.clearTimeout(reconnectTimer);
    heartbeatTimer = null;
    reconnectTimer = null;
    stopMic();
    ws?.close();
    ws = null;
    connected.value = false;
  }

  function connect(id: string) {
    disconnect();
    intentionalClose = false;
    sessionId = id;
    error.value = '';
    reportId.value = '';
    overallScore.value = null;
    lastTurn.value = null;
    caption.value = '';
    question.value = null;
    sessionEnded.value = false;
    agentLog.value = [];
    phase.value = 'idle';
    progressText.value = '';
    ws = new WebSocket(interviewWsUrl(id));
    ws.onopen = () => {
      connected.value = true;
      send({ type: 'start' });
      heartbeatTimer = window.setInterval(() => send({ type: 'heartbeat' }), 25000);
    };
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data) as Record<string, unknown>;
        const type = String(data.type || '');
        if (type === 'question') {
          question.value = {
            index: Number(data.index || 0),
            total: Number(data.total || 0),
            kind: String(data.kind || ''),
            kind_label: String(data.kind_label || ''),
            text: String(data.text || ''),
          };
          caption.value = '';
          lastTurn.value = null;
          followupHint.value = '';
          phase.value = 'asking';
          progressText.value = '';
          statusHint.value = '面试官正在提问';
        } else if (type === 'mic_gate') {
          micGate.value = data.state === 'open' ? 'open' : 'closed';
          if (micGate.value === 'open') {
            phase.value = 'answering';
            statusHint.value = '请开始回答';
          } else {
            statusHint.value = '面试官讲话中';
          }
        } else if (type === 'caption') {
          caption.value = String(data.text || '');
        } else if (type === 'turn_progress') {
          phase.value = 'scoring';
          progressText.value = String(data.content || '正在评分…');
          statusHint.value = progressText.value;
        } else if (type === 'turn_score') {
          lastTurn.value = (data.turn || null) as InterviewTurn | null;
          phase.value = 'scoring';
          statusHint.value = lastTurn.value?.fused_score != null
            ? `第 ${(lastTurn.value.turn_index ?? 0) + 1} 题 · 综合 ${lastTurn.value.fused_score} 分`
            : '本轮已评分';
        } else if (type === 'session_end') {
          sessionEnded.value = true;
          phase.value = 'finishing';
          micGate.value = 'closed';
          stopMic();
          statusHint.value = '本场面试已结束，正在生成报告…';
          progressText.value = statusHint.value;
        } else if (type === 'report_ready') {
          reportId.value = String(data.report_id || '');
          const score = data.overall_score;
          overallScore.value = typeof score === 'number' ? score : Number(score || 0) || null;
          statusHint.value = '报告已生成';
          intentionalClose = true;
        } else if (type === 'followup') {
          followupHint.value = String(data.question || '面试官将追问一题');
          statusHint.value = '进入追问';
        } else if (type === 'error') {
          error.value = String(data.detail || '面试通道异常');
        } else if (type === 'agent_step') {
          const role = String(data.role || '');
          const content = String(data.content || '');
          statusHint.value = content;
          if (content) agentLog.value = [...agentLog.value.slice(-7), { role, content }];
        }
      } catch {
        /* ignore */
      }
    };
    ws.onclose = () => {
      connected.value = false;
      if (intentionalClose || sessionEnded.value || !sessionId) return;
      reconnectTimer = window.setTimeout(() => connect(sessionId), 1500);
    };
    ws.onerror = () => {
      error.value = '面试通道连接失败';
    };
  }

  async function notifySpeakDone() {
    speaking.value = false;
    try {
      await startMic();
    } catch (err) {
      error.value = err instanceof DOMException && err.name === 'NotAllowedError' ? '麦克风权限被拒绝' : '无法访问麦克风';
    }
    send({ type: 'speak_done' });
  }

  function submitAnswer() {
    send({ type: 'answer_end' });
    micGate.value = 'closed';
    phase.value = 'scoring';
    progressText.value = '正在评分…';
    statusHint.value = '正在评分…';
  }

  function submitTextFallback(text: string) {
    send({ type: 'caption_override', text });
    submitAnswer();
  }

  function sendFrame(dataUrl: string) {
    send({ type: 'frame', data: dataUrl });
  }

  onBeforeUnmount(disconnect);

  return {
    connected,
    micGate,
    caption,
    question,
    lastTurn,
    reportId,
    overallScore,
    statusHint,
    error,
    speaking,
    followupHint,
    phase,
    progressText,
    sessionEnded,
    agentLog,
    connect,
    disconnect,
    notifySpeakDone,
    submitAnswer,
    submitTextFallback,
    sendFrame,
    stopMic,
  };
}
