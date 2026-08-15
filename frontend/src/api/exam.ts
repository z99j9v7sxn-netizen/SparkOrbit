import { apiGet, apiPost, apiPostForm } from './client';

export interface ExamTypeMeta {
  key: string;
  label: string;
}

export interface ExamMeta {
  exam_types: ExamTypeMeta[];
  sections: ExamTypeMeta[];
  mock_structure: { section: string; count: number }[];
}

export interface ExamQuestionItem {
  id: string;
  exam_type: string;
  section: string;
  question: string;
  options: Record<string, string>;
  audio_text: string;
  difficulty: string;
  source: string;
  answer?: string;
  analysis?: string;
}

export interface PracticeCheckResult {
  ok: boolean;
  correct: boolean;
  answer: string;
  analysis: string;
  question: ExamQuestionItem;
  mistake_archived?: boolean;
}

export interface MockPaper {
  run_id: string;
  paper_id: string;
  title: string;
  duration_minutes: number;
  structure: { section: string; question_ids: string[] }[];
  questions: ExamQuestionItem[];
}

export interface MockResult {
  ok: boolean;
  run_id: string;
  score: number;
  section_scores: Record<string, { total: number; correct: number; score: number }>;
  detail: {
    question_id: string;
    section: string;
    correct: boolean;
    my_answer: string;
    answer: string;
    analysis: string;
    ratio?: number;
  }[];
  mistakes_archived: number;
}

export interface MockHistoryItem {
  run_id: string;
  exam_type: string;
  score: number;
  section_scores: Record<string, { total: number; correct: number }>;
  finished_at: string;
}

export interface ExamWord {
  id: string;
  word: string;
  phonetic: string;
  meaning: string;
  example: string;
  freq_rank: number;
}

export interface EssayGradeResult {
  ok: boolean;
  score: number;
  dimensions: { name: string; score: number; comment: string }[];
  sentence_feedback: { original: string; revised: string; reason: string }[];
  highlights: string[];
  suggestions: string[];
}

export interface ListeningMaterial {
  ok: boolean;
  title: string;
  transcript: string;
  sentences: string[];
  blanks: { sentence_index: number; word: string }[];
  translation: string;
}

export interface ChallengeStatus {
  active: boolean;
  id?: string;
  name?: string;
  exam_type?: string;
  days_total?: number;
  days_done?: number;
  checkins?: string[];
  checked_today?: boolean;
  today_progress?: number;
  today_goal?: number;
  can_checkin?: boolean;
}

const AI_TIMEOUT = { timeoutMs: 180_000 };

export const fetchExamMeta = () => apiGet<ExamMeta>('/api/exam/meta');

export const fetchBankSummary = (exam_type: string) =>
  apiGet<{ exam_type: string; sections: Record<string, number> }>(
    `/api/exam/bank/summary?exam_type=${encodeURIComponent(exam_type)}`,
  );

export const generateQuestions = (exam_type: string, section: string, count = 5) =>
  apiPost<{ ok: boolean; created: number }>('/api/exam/generate', { exam_type, section, count }, AI_TIMEOUT);

export const importQuestions = (exam_type: string, file: File) => {
  const form = new FormData();
  form.append('exam_type', exam_type);
  form.append('file', file);
  return apiPostForm<{ ok: boolean; imported: number }>('/api/exam/import', form, AI_TIMEOUT);
};

export const fetchPracticeQuestions = (exam_type: string, section: string, count = 5) =>
  apiGet<{ questions: ExamQuestionItem[] }>(
    `/api/exam/practice?exam_type=${encodeURIComponent(exam_type)}&section=${encodeURIComponent(section)}&count=${count}`,
    AI_TIMEOUT,
  );

export const checkPracticeAnswer = (question_id: string, answer: string, archive_wrong = true) =>
  apiPost<PracticeCheckResult>('/api/exam/practice/check', { question_id, answer, archive_wrong });

export const logPractice = (payload: {
  exam_type?: string;
  section?: string;
  activity?: string;
  total?: number;
  correct?: number;
  meta?: Record<string, unknown>;
}) => apiPost<{ ok: boolean }>('/api/exam/practice/log', payload);

export const startMock = (exam_type: string) =>
  apiPost<MockPaper>('/api/exam/mock/start', { exam_type }, AI_TIMEOUT);

export const submitMock = (run_id: string, answers: Record<string, string>) =>
  apiPost<MockResult>('/api/exam/mock/submit', { run_id, answers }, AI_TIMEOUT);

export const fetchMockHistory = () => apiGet<MockHistoryItem[]>('/api/exam/mock/history');

export const fetchWords = (exam_type: string, offset = 0, limit = 20) =>
  apiGet<{ total: number; words: ExamWord[] }>(
    `/api/exam/words?exam_type=${encodeURIComponent(exam_type)}&offset=${offset}&limit=${limit}`,
  );

export const seedWords = (exam_type: string, count = 30) =>
  apiPost<{ ok: boolean; added: number }>('/api/exam/words/seed', { exam_type, count }, AI_TIMEOUT);

export const collectWord = (word_id: string) =>
  apiPost<{ ok: boolean; card_id: string }>(`/api/exam/words/${word_id}/collect`, {});

export const gradeEssay = (payload: { exam_type: string; kind: 'writing' | 'translation'; prompt?: string; text: string }) =>
  apiPost<EssayGradeResult>('/api/exam/essay/grade', payload, AI_TIMEOUT);

export const fetchListeningMaterial = (exam_type: string, topic = '') =>
  apiPost<ListeningMaterial>('/api/exam/listening/material', { exam_type, topic }, AI_TIMEOUT);

export const fetchChallengeStatus = () => apiGet<ChallengeStatus>('/api/exam/challenge');

export const joinChallenge = (exam_type = 'cet4') =>
  apiPost<{ ok: boolean; id: string }>('/api/exam/challenge/join', { exam_type });

export const challengeCheckin = () =>
  apiPost<{ ok: boolean; already?: boolean; days_done: number; finished?: boolean; points_earned?: number; points?: number }>(
    '/api/exam/challenge/checkin',
    {},
  );

/** 讯飞 TTS：返回可直接播放的 data URL */
export async function ttsToDataUrl(text: string): Promise<string> {
  const res = await apiPost<{ mime: string; audio_base64: string }>('/api/tts', { text }, { timeoutMs: 60_000 });
  return `data:${res.mime};base64,${res.audio_base64}`;
}
