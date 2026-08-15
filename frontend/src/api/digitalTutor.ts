import { apiGet, apiPost } from './client';

export type DigitalTutorCitation = {
  snippet?: string;
  citation?: string;
  book?: string;
  page?: number;
  score?: number;
  source?: string;
  text?: string;
};

export type DigitalTutorMode = 'planet' | 'mistake' | 'tutor_summary';

export type MistakeSlide = {
  title: string;
  narration: string;
  bullet_points?: string[];
  visual_hint?: string;
};

export type DigitalTutorTask = {
  task_id: string;
  status: string;
  fallback: boolean;
  error: string;
  message: string;
  planet_slug: string;
  galaxy_slug: string;
  prompt: string;
  script: string;
  summary?: string;
  slides?: MistakeSlide[];
  citations: DigitalTutorCitation[];
  video_url?: string | null;
  remote_video_url?: string | null;
  cover_image?: string | null;
  audio_url?: string | null;
  xf_task_id?: string | null;
  asset?: Record<string, unknown> | null;
  provider?: string;
  cached?: boolean;
  mode?: DigitalTutorMode | string;
  mistake_id?: string;
  reused_inflight?: boolean;
};

export type MistakeTutorPayload = {
  mistake_id?: string;
  question: string;
  student_answer?: string;
  correct_answer?: string;
  note?: string;
  subject?: string;
  planet_slug?: string;
};

export const fetchSavedDigitalTutor = (planetSlug: string) =>
  apiGet<DigitalTutorTask>(
    `/api/digital-tutor/saved?planet_slug=${encodeURIComponent(planetSlug)}`,
  );

export const fetchSavedMistakeTutor = (mistakeId: string) =>
  apiGet<DigitalTutorTask>(
    `/api/digital-tutor/saved?mistake_id=${encodeURIComponent(mistakeId)}`,
  );

export const startDigitalTutor = (
  planetSlug: string,
  prompt = '',
  opts?: { wordCount?: number; force?: boolean },
) =>
  apiPost<DigitalTutorTask>(
    '/api/digital-tutor/generate',
    {
      mode: 'planet',
      planet_slug: planetSlug,
      prompt,
      ...(opts?.wordCount != null ? { word_count: opts.wordCount } : {}),
      ...(opts?.force ? { force: true } : {}),
    },
    { timeoutMs: 90_000 },
  );

export const startMistakeTutor = (
  payload: MistakeTutorPayload,
  opts?: { wordCount?: number; force?: boolean },
) =>
  apiPost<DigitalTutorTask>(
    '/api/digital-tutor/generate',
    {
      mode: 'mistake',
      planet_slug: payload.planet_slug || '',
      mistake_id: payload.mistake_id || '',
      question: payload.question,
      student_answer: payload.student_answer || '',
      correct_answer: payload.correct_answer || '',
      note: payload.note || '',
      subject: payload.subject || '',
      ...(opts?.wordCount != null ? { word_count: opts.wordCount } : {}),
      ...(opts?.force ? { force: true } : {}),
    },
    { timeoutMs: 90_000 },
  );

/** 与 generate?mode=mistake 等价的清晰入口 */
export const explainMistakeTutor = (payload: MistakeTutorPayload, opts?: { force?: boolean }) =>
  apiPost<DigitalTutorTask>(
    '/api/digital-tutor/mistake-explain',
    {
      planet_slug: payload.planet_slug || '',
      mistake_id: payload.mistake_id || '',
      question: payload.question,
      student_answer: payload.student_answer || '',
      correct_answer: payload.correct_answer || '',
      note: payload.note || '',
      subject: payload.subject || '',
      ...(opts?.force ? { force: true } : {}),
    },
    { timeoutMs: 90_000 },
  );

export const fetchDigitalTutorTask = (taskId: string) =>
  apiGet<DigitalTutorTask>(`/api/digital-tutor/tasks/${encodeURIComponent(taskId)}`);

/** 轮询直到成功 / fallback / 失败；返回最终任务态。 */
export async function pollDigitalTutorTask(
  taskId: string,
  opts?: {
    intervalMs?: number;
    timeoutMs?: number;
    onUpdate?: (task: DigitalTutorTask) => void;
  },
): Promise<DigitalTutorTask> {
  const interval = Math.max(1500, opts?.intervalMs ?? 3000);
  const timeout = Math.max(10000, opts?.timeoutMs ?? 10 * 60 * 1000);
  const start = Date.now();
  let last: DigitalTutorTask | null = null;
  while (Date.now() - start < timeout) {
    last = await fetchDigitalTutorTask(taskId);
    opts?.onUpdate?.(last);
    const st = (last.status || '').toLowerCase();
    if (st === 'succeeded' || st === 'fallback' || st === 'failed' || st === 'error') {
      return last;
    }
    if (last.fallback && last.video_url == null && st !== 'processing' && st !== 'queued') {
      return last;
    }
    await new Promise((r) => setTimeout(r, interval));
  }
  if (last) return last;
  throw new Error('数字人任务轮询超时');
}
