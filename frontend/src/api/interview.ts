import { apiDelete, apiGet, apiPatch, apiPost, apiPostForm } from './client';

export interface InterviewJobRole {
  key: string;
  label: string;
  scenario: string;
  family: string;
  description: string;
}

export interface InterviewSessionBrief {
  id: string;
  scenario: string;
  job_role: string;
  job_role_label: string;
  difficulty: string;
  question_count: number;
  status: string;
  overall_score: number | null;
  current_turn: number;
  created_at: string;
  finished_at: string;
  user_id?: string;
  assignment_id?: string;
  student_name?: string;
  review_status?: string;
}

export interface InterviewQuestion {
  index: number;
  kind: string;
  kind_label: string;
  question: string;
}

export interface InterviewTurn {
  id: string;
  turn_index: number;
  question: string;
  question_kind: string;
  transcript: string;
  audio_url: string;
  frame_urls: string[];
  semantic_score: number | null;
  prosody_score: number | null;
  visual_score: number | null;
  fused_score: number | null;
  prosody_detail: {
    speech_rate?: number;
    filler_count?: number;
    pause_ratio?: number;
    duration_sec?: number;
    char_count?: number;
    reasons?: string[];
  };
  feedback: string;
  followup_strategy: string;
  duration_sec: number;
}

export interface InterviewPrepIntel {
  job?: { summary?: string; skills?: string[]; risks?: string[] };
  profile?: { summary?: string; hooks?: string[] };
  topics?: string[];
}

export interface InterviewReport {
  id: string;
  session_id: string;
  dimension_scores: Record<string, number>;
  dimension_labels: Record<string, string>;
  key_issues: string[];
  suggestions: string[];
  resource_refs: Record<string, unknown>[];
  council_views: Record<string, unknown>;
  teacher_comment: string;
  teacher_score: number | null;
  review_status: string;
  degraded_modalities: string[];
  summary: string;
  created_at: string;
}

export interface InterviewPortraitLatest {
  id: string;
  scenario: string;
  job_role: string;
  job_role_label: string;
  overall_score: number | null;
  created_at: string;
}

export interface InterviewPortraitScenario {
  count: number;
  avg_score: number | null;
  dimension_avg: Record<string, number>;
  dimension_latest: Record<string, number>;
  dimension_labels: Record<string, string>;
  latest_id: string;
  latest_job_role: string;
  latest_job_role_label: string;
}

export interface InterviewPortrait {
  session_count: number;
  avg_score: number | null;
  latest: InterviewPortraitLatest | null;
  job: InterviewPortraitScenario;
  academic: InterviewPortraitScenario;
  by_role: Array<{
    job_role: string;
    job_role_label: string;
    scenario: string;
    count: number;
    avg_score: number | null;
  }>;
  trend: Array<{
    id: string;
    at: string;
    overall_score: number | null;
    scenario: string;
    job_role_label: string;
  }>;
  weak_dims: Array<{
    key: string;
    label: string;
    avg: number;
    scenario: string;
  }>;
  loop_counts: Record<string, number>;
  recent_refs: Record<string, unknown>[];
}

export interface InterviewSessionDetail extends InterviewSessionBrief {
  class_id: string;
  resume_url: string;
  resume_profile: Record<string, unknown>;
  questions: InterviewQuestion[];
  turns: InterviewTurn[];
  report: InterviewReport | null;
  prep_run_id: string;
  prep_intel: InterviewPrepIntel;
  dimension_labels: Record<string, string>;
}

export interface InterviewPracticeQuestion {
  question: string;
  kind: string;
  kind_label: string;
  scenario: string;
  job_role: string;
  job_role_label: string;
}

export interface InterviewPracticeAnswer {
  id: string;
  score: number | null;
  feedback: string;
  star_hit: Record<string, boolean>;
  reasons: string[];
  created_at: string;
}

export interface InterviewPracticeRecord {
  id: string;
  scenario: string;
  job_role: string;
  job_role_label: string;
  kind: string;
  kind_label: string;
  question: string;
  transcript: string;
  score: number | null;
  feedback: string;
  star_hit: Record<string, boolean>;
  created_at: string;
}

export interface InterviewResumeResult {
  url: string;
  profile: Record<string, unknown>;
  text_preview: string;
}

export interface InterviewStreamEvent {
  role: string;
  type: string;
  content: string;
  payload: Record<string, unknown>;
}

export const fetchInterviewRoles = (scenario = '') => {
  const q = scenario ? `?scenario=${encodeURIComponent(scenario)}` : '';
  return apiGet<InterviewJobRole[]>(`/api/interview/job-roles${q}`);
};

export const uploadInterviewResume = (file: File) => {
  const form = new FormData();
  form.append('file', file);
  return apiPostForm<InterviewResumeResult>('/api/interview/resume', form);
};

export const createInterviewSession = (body: {
  scenario: string;
  job_role: string;
  difficulty?: string;
  question_count?: number;
  resume_url?: string;
  resume_profile?: Record<string, unknown>;
  assignment_id?: string;
  consent?: boolean;
}) => apiPost<InterviewSessionBrief>('/api/interview/sessions', body, { timeoutMs: 120_000 });

export interface InterviewTask {
  assignment_id: string;
  title: string;
  description: string;
  due_at: string;
  scenario: string;
  job_role: string;
  question_count: number;
  difficulty: string;
  stem: string;
  my_status: string;
  my_score: number | null;
}

export const fetchInterviewSessions = () => apiGet<InterviewSessionBrief[]>('/api/interview/sessions');

export const fetchInterviewTasks = () => apiGet<InterviewTask[]>('/api/interview/tasks');

export const deleteInterviewSession = (id: string) =>
  apiDelete<{ ok: boolean }>(`/api/interview/sessions/${encodeURIComponent(id)}`);

export const fetchInterviewSession = (id: string) =>
  apiGet<InterviewSessionDetail>(`/api/interview/sessions/${encodeURIComponent(id)}`);

export const fetchInterviewReport = (id: string) =>
  apiGet<InterviewReport>(`/api/interview/reports/${encodeURIComponent(id)}`);

export const fetchInterviewPortrait = () => apiGet<InterviewPortrait>('/api/interview/portrait');

export const fetchPracticeQuestion = (params: { scenario: string; job_role: string; kind?: string }) => {
  const q = new URLSearchParams({
    scenario: params.scenario,
    job_role: params.job_role,
    kind: params.kind || '',
  });
  return apiGet<InterviewPracticeQuestion>(`/api/interview/practice/question?${q.toString()}`);
};

export const submitPracticeAnswer = (body: {
  scenario: string;
  job_role: string;
  kind: string;
  question: string;
  transcript: string;
}) => apiPost<InterviewPracticeAnswer>('/api/interview/practice/answer', body, { timeoutMs: 60_000 });

export const fetchPracticeHistory = () =>
  apiGet<InterviewPracticeRecord[]>('/api/interview/practice/history');

export interface CareerPortal {
  id: string;
  name: string;
  group: string;
  url: string;
  intern_url: string;
  note: string;
  accent?: string;
  logo_host?: string;
}

export interface CareerWindow {
  id: string;
  title: string;
  when: string;
  season: string;
  portal_ids: string[];
  companies: string[];
  note: string;
}

export interface ResumeTemplateMeta {
  id: string;
  name: string;
  description: string;
  suitable: string;
  accent: string;
  allow_photo?: boolean;
  tier?: string;
}

export interface ResumeOpenSourceLink {
  id: string;
  name: string;
  license: string;
  url: string;
  note: string;
}

export interface CareerQuestion {
  id: string;
  company_id: string;
  company: string;
  job_role: string;
  kind: string;
  question: string;
}

export interface InterviewApplication {
  id: string;
  company: string;
  role: string;
  portal_url: string;
  status: string;
  notes: string;
  applied_at: string;
  created_at: string;
  updated_at: string;
}

export interface ResumeOptimizeResult {
  score: number;
  issues: string[];
  rewritten_markdown: string;
  ats_keywords: string[];
  degraded: boolean;
}

export interface ResumeMatchResult {
  score: number;
  matched: string[];
  gaps: string[];
  prep_suggestions: string[];
  recommended_portals: Array<{ id: string; name: string; url: string }>;
  degraded: boolean;
}

export const fetchCareerPortals = () =>
  apiGet<{ portals: CareerPortal[]; windows: CareerWindow[] }>('/api/interview/career/portals');

export const fetchCareerTemplates = () =>
  apiGet<{ templates: ResumeTemplateMeta[]; open_source: ResumeOpenSourceLink[] }>(
    '/api/interview/career/templates',
  );

export const fetchCareerQuestions = (params?: { company?: string; job_role?: string }) => {
  const q = new URLSearchParams();
  if (params?.company) q.set('company', params.company);
  if (params?.job_role) q.set('job_role', params.job_role);
  const suffix = q.toString() ? `?${q}` : '';
  return apiGet<{ companies: Array<{ id: string; name: string }>; questions: CareerQuestion[] }>(
    `/api/interview/career/questions${suffix}`,
  );
};

export const optimizeInterviewResume = (body: {
  text?: string;
  profile?: Record<string, unknown>;
  target_role?: string;
  jd?: string;
}) => apiPost<ResumeOptimizeResult>('/api/interview/resume/optimize', body, { timeoutMs: 60_000 });

export const matchInterviewResume = (body: {
  text?: string;
  profile?: Record<string, unknown>;
  target_role?: string;
  jd?: string;
}) => apiPost<ResumeMatchResult>('/api/interview/resume/match', body, { timeoutMs: 60_000 });

export async function downloadResumeExport(body: {
  template_id: string;
  fields: Record<string, unknown>;
  format: 'html' | 'docx' | 'md';
}): Promise<void> {
  const token = localStorage.getItem('sparkorbit_token');
  const res = await fetch('/api/interview/resume/export', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await res.text());
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  const ext = body.format === 'docx' ? 'docx' : body.format;
  a.download = `resume-${String(body.fields.name || 'sparkorbit')}.${ext}`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function fetchResumeHtml(body: {
  template_id: string;
  fields: Record<string, unknown>;
}): Promise<string> {
  const token = localStorage.getItem('sparkorbit_token');
  const res = await fetch('/api/interview/resume/export', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify({ ...body, format: 'html' }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.text();
}

export const fetchInterviewApplications = () =>
  apiGet<InterviewApplication[]>('/api/interview/applications');

export const createInterviewApplication = (body: {
  company: string;
  role?: string;
  portal_url?: string;
  status?: string;
  notes?: string;
}) => apiPost<InterviewApplication>('/api/interview/applications', body);

export const patchInterviewApplication = (
  id: string,
  body: Partial<Pick<InterviewApplication, 'company' | 'role' | 'portal_url' | 'status' | 'notes'>>,
) => apiPatch<InterviewApplication>(`/api/interview/applications/${encodeURIComponent(id)}`, body);

export const deleteInterviewApplication = (id: string) =>
  apiDelete<{ ok: boolean }>(`/api/interview/applications/${encodeURIComponent(id)}`);

export function interviewWsUrl(sessionId: string) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/ws/interview/${encodeURIComponent(sessionId)}`;
}

export async function consumeInterviewPrepStream(
  sessionId: string,
  onEvent: (event: InterviewStreamEvent) => void,
): Promise<void> {
  const token = localStorage.getItem('sparkorbit_token');
  const res = await fetch(`/api/interview/sessions/${encodeURIComponent(sessionId)}/prep/stream`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok || !res.body) throw new Error('面试准备流连接失败');
  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const parts = buffer.split('\n\n');
    buffer = parts.pop() || '';
    for (const part of parts) {
      const line = part.trim();
      if (!line.startsWith('data:')) continue;
      try {
        onEvent(JSON.parse(line.slice(5).trim()) as InterviewStreamEvent);
      } catch {
        /* ignore */
      }
    }
  }
}
