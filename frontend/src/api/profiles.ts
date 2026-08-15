import { apiGet, apiPatch, apiPost } from './client';

export interface ChatMessage {
  role: 'system' | 'user' | 'assistant';
  content: string;
}

export interface DimensionProfile {
  value: string;
  score: number;
  evidence: string[];
}

export interface StudentProfileExtract {
  student_name: string;
  major_background: DimensionProfile;
  prior_knowledge: DimensionProfile;
  cognitive_style: DimensionProfile;
  mistake_tendency: DimensionProfile;
  learning_goal: DimensionProfile;
  time_flexibility: DimensionProfile;
  modality_preference: DimensionProfile;
  motivation_level: DimensionProfile;
  missing_dimensions: string[];
  follow_up_questions: string[];
  summary: string;
}

export interface ProfileResponse {
  profile: StudentProfileExtract;
  raw: Record<string, unknown>;
}

export interface ProfileHistoryItem {
  id: string;
  student_name: string;
  summary: string;
  major_background: string;
  prior_knowledge: string;
  cognitive_style: string;
  mistake_tendency: string;
  learning_goal: string;
  time_flexibility: string;
  modality_preference: string;
  motivation_level: string;
  major_background_score?: number;
  prior_knowledge_score?: number;
  cognitive_style_score?: number;
  mistake_tendency_score?: number;
  learning_goal_score?: number;
  time_flexibility_score?: number;
  modality_preference_score?: number;
  motivation_level_score?: number;
  created_at?: string | null;
}

export interface ProfileWarning {
  dimension: string;
  text: string;
  source_submission_id?: string;
  created_at?: string;
}

export interface ProfileMeta {
  warnings: ProfileWarning[];
  floors: Record<string, number>;
  has_profile: boolean;
  profile_id?: string | null;
  summary?: string;
  last_sources?: Record<string, string>;
  pending_events?: number;
  layers?: Record<string, number>;
  layer_summaries?: Record<string, string>;
  update_source?: string;
  updated_at?: string;
}

export interface ProfileEvidenceItem {
  at: string;
  event_type: string;
  summary: string;
  delta_hint?: string;
  link?: string;
  dimension?: string;
  payload?: Record<string, unknown>;
}

export interface RemediationStep {
  index: number;
  title: string;
  done: boolean;
  evidence_text: string;
}

export type ImprovementGrade = 'excellent' | 'pass' | 'fail';

export interface ImprovementSubmissionView {
  id: string;
  reflection: string;
  ai_grade: ImprovementGrade | string;
  ai_feedback: string;
  ai_delta_json: Record<string, number>;
  teacher_grade?: string | null;
  teacher_feedback?: string;
  final_grade: ImprovementGrade | string;
  applied_delta: number;
  warning_text: string;
  teacher_reviewed: boolean;
  pending_review: boolean;
  created_at?: string | null;
}

export interface RemediationPlanView {
  id: string;
  user_id: string;
  simulation_run_id: string;
  target_dimension: string;
  target_dimension_label: string;
  topic: string;
  root_cause: string;
  steps: RemediationStep[];
  status: string;
  created_at?: string | null;
  submission?: ImprovementSubmissionView | null;
  student_name?: string;
  student_id?: string;
}

export async function extractProfile(student_name: string, chat_history: ChatMessage[]) {
  return apiPost<ProfileResponse>('/api/profiles/extract', {
    student_name,
    chat_history,
  });
}

export async function fetchProfileHistory(studentName?: string) {
  const query = studentName ? `?student_name=${encodeURIComponent(studentName)}` : '';
  return apiGet<ProfileHistoryItem[]>(`/api/profiles/history${query}`);
}

export async function fetchProfileMeta() {
  return apiGet<ProfileMeta>('/api/profiles/meta');
}

export async function fetchProfileEvidence(dimension = '') {
  const q = dimension ? `?dimension=${encodeURIComponent(dimension)}` : '';
  return apiGet<{
    dimension: string;
    profile_evidence: ProfileEvidenceItem[];
    events: ProfileEvidenceItem[];
    items: ProfileEvidenceItem[];
  }>(`/api/profiles/evidence${q}`);
}

export async function fetchImprovementPlans() {
  return apiGet<RemediationPlanView[]>('/api/profiles/improvement/plans');
}

export async function updateImprovementStep(
  planId: string,
  stepIndex: number,
  body: { done?: boolean; evidence_text?: string },
) {
  return apiPatch<RemediationPlanView>(
    `/api/profiles/improvement/plans/${encodeURIComponent(planId)}/steps/${stepIndex}`,
    body,
  );
}

export async function submitImprovement(planId: string, reflection: string) {
  return apiPost<RemediationPlanView>(`/api/profiles/improvement/plans/${encodeURIComponent(planId)}/submit`, {
    reflection,
  });
}

export async function syncRemediationToPath(planId: string) {
  return apiPost<{ path_id: string; title: string; steps: number; message: string }>(
    `/api/profiles/improvement/plans/${encodeURIComponent(planId)}/sync-to-path`,
    {},
  );
}

export async function fetchTeacherImprovementPending() {
  return apiGet<RemediationPlanView[]>('/api/teacher/improvement/pending');
}

export async function overrideImprovement(submissionId: string, grade: ImprovementGrade, feedback = '') {
  return apiPost<RemediationPlanView>(
    `/api/teacher/improvement/${encodeURIComponent(submissionId)}/override`,
    { grade, feedback },
  );
}
