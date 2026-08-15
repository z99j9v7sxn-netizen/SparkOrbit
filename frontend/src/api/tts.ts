import { apiPost } from './client';

export type TtsResponse = {
  mime: string;
  audio_base64: string;
  chars: number;
};

export async function synthesizeSpeech(text: string, vcn?: string): Promise<Blob> {
  const res = await apiPost<TtsResponse>('/api/tts', {
    text: text.slice(0, 800),
    ...(vcn ? { vcn } : {}),
  });
  const binary = atob(res.audio_base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
  return new Blob([bytes], { type: res.mime || 'audio/mpeg' });
}
