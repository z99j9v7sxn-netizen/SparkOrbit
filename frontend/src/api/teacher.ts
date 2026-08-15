import { apiDelete, apiDownloadBlob, apiGet, apiPost, apiPostForm, apiPut } from './client';

export interface TeacherClass {
  id: string;
  name: string;
  invite_code: string;
}

export interface AssignmentItem {
  id: string;
  class_id: string;
  title: string;
  description: string;
  galaxy_slug: string;
  due_at: string;
  created_at: string;
  submission_count: number;
  my_status?: string;
  my_score?: number | null;
  submission_id?: string;
  questions?: AssignmentQuestion[];
  source_resource_id?: string;
}

export interface AssignmentQuestion {
  index?: number;
  stem: string;
  kind?: string;
  options?: string[];
  answer?: string;
  score?: number;
  scenario?: string;
  job_role?: string;
  question_count?: number;
  difficulty?: string;
}

export interface AssignmentExtractResult {
  title_suggestion: string;
  raw_text_preview: string;
  questions: AssignmentQuestion[];
  provider: string;
  message: string;
}

export interface SubmissionItem {
  id: string;
  student_id: string;
  student_name: string;
  content: string;
  attachment_url: string;
  score: number | null;
  feedback: string;
  status: string;
  submitted_at: string;
}

export interface GradebookRow {
  user_id: string;
  display_name: string;
  username: string;
  mastery_rate: number;
  quiz_accuracy: number;
  assignment_avg: number | null;
  lit_count: number;
  total_planets: number;
}

export interface BroadcastItem {
  id: string;
  class_id: string;
  title: string;
  body: string;
  recipient_count: number;
  created_at: string;
}

export interface AttendanceRow {
  student_id: string;
  display_name: string;
  status: string;
}

export interface StudentDetail {
  user_id: string;
  display_name: string;
  username: string;
  class_id: string;
  mastery_rate: number;
  focus_minutes: number;
  profile_id?: string;
  profile: { id?: string; student_name: string; summary: string; dimensions: Record<string, unknown> } | null;
  mastery: Array<{ planet_slug: string; planet_name: string; status: string; score: number }>;
  alerts: Array<{ id: string; type: string; message: string; created_at: string }>;
  mistakes: Array<{ id: string; question: string; subject: string; created_at: string }>;
  assignments: Array<{ assignment_title: string; status: string; score: number | null; submitted_at: string }>;
}

export interface ImportStudentItem {
  username: string;
  display_name: string;
  password?: string;
}

export interface ImportStudentsResult {
  created: number;
  skipped: number;
}

export interface ForgeGalaxyResult {
  ok: boolean;
  galaxy_name?: string;
  galaxy_slug?: string;
  planet_count?: number;
  [key: string]: unknown;
}

export const fetchTeacherClasses = () => apiGet<TeacherClass[]>('/api/teacher/classes');

export const fetchTeacherAssignments = (class_id = '') =>
  apiGet<AssignmentItem[]>(`/api/teacher/assignments${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

export const createAssignment = (payload: {
  class_id: string;
  title: string;
  description: string;
  galaxy_slug?: string;
  due_at?: string;
  questions?: AssignmentQuestion[];
  source_resource_id?: string;
}) => apiPost<AssignmentItem>('/api/teacher/assignments', payload);

export const extractAssignmentQuestions = (file: File, hint_title = '') => {
  const form = new FormData();
  form.append('file', file);
  if (hint_title) form.append('hint_title', hint_title);
  return apiPostForm<AssignmentExtractResult>('/api/teacher/assignments/extract-questions', form);
};

export const extractAssignmentFromResource = (resource_id: string) => {
  const form = new FormData();
  form.append('resource_id', resource_id);
  return apiPostForm<AssignmentExtractResult>('/api/teacher/assignments/extract-from-resource', form);
};

export const fetchSubmissions = (assignmentId: string) =>
  apiGet<SubmissionItem[]>(`/api/teacher/assignments/${assignmentId}/submissions`);

export const gradeSubmission = (
  assignmentId: string,
  submissionId: string,
  score: number,
  feedback: string,
) => apiPost(`/api/teacher/assignments/${assignmentId}/submissions/${submissionId}/grade`, { score, feedback });

export const fetchGradebook = (class_id = '') =>
  apiGet<GradebookRow[]>(`/api/teacher/gradebook${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

export const sendBroadcast = (class_id: string, title: string, body: string) =>
  apiPost<BroadcastItem>('/api/teacher/broadcast', { class_id, title, body });

export const fetchBroadcasts = (class_id = '') =>
  apiGet<BroadcastItem[]>(`/api/teacher/broadcasts${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

export const fetchAttendance = (class_id: string, record_date = '') =>
  apiGet<AttendanceRow[]>(
    `/api/teacher/attendance?class_id=${encodeURIComponent(class_id)}${record_date ? `&record_date=${record_date}` : ''}`,
  );

export const setAttendance = (class_id: string, student_id: string, status: string, record_date = '') =>
  apiPost('/api/teacher/attendance/checkin', { class_id, student_id, status, record_date });

export const fetchStudentDetail = (studentId: string, class_id = '') =>
  apiGet<StudentDetail>(
    `/api/teacher/students/${studentId}/detail${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );

function teacherStudentFocusQs(class_id = '') {
  return class_id ? `?class_id=${encodeURIComponent(class_id)}` : '';
}

export const fetchTeacherStudentFocusSummary = (studentId: string, class_id = '') =>
  apiGet<{ today_minutes: number; week_minutes: number; sessions: number }>(
    `/api/teacher/students/${studentId}/focus/summary${teacherStudentFocusQs(class_id)}`,
  );

export const fetchTeacherStudentFocusHeatmap = (studentId: string, class_id = '', week_offset = 0) => {
  const qs = new URLSearchParams();
  if (class_id) qs.set('class_id', class_id);
  if (week_offset) qs.set('week_offset', String(week_offset));
  const q = qs.toString();
  return apiGet<{
    cells: Array<{ day: number; slot: string; minutes: number }>;
    total_minutes: number;
    week_start: string;
    week_end: string;
  }>(`/api/teacher/students/${studentId}/focus/heatmap${q ? `?${q}` : ''}`);
};

export const fetchTeacherStudentFocusYearly = (studentId: string, class_id = '') =>
  apiGet<{ cells: { date: string; minutes: number; sessions?: number }[]; total_minutes: number }>(
    `/api/teacher/students/${studentId}/focus/yearly${teacherStudentFocusQs(class_id)}`,
  );

export const fetchTeacherStudentLearnHeatmap = (studentId: string, class_id = '') => {
  const q = class_id ? `?class_id=${encodeURIComponent(class_id)}` : '';
  return apiGet<{
    student_id: string;
    display_name: string;
    selection_ask_count: number;
    learn_heatmap_summary: {
      by_kind?: Record<string, number>;
      by_day?: Record<string, number>;
      total_evidence?: number;
    };
  }>(`/api/teacher/students/${studentId}/learn-heatmap${q}`);
};

export interface InsightOverview {
  class_id: string;
  total_students: number;
  avg_mastery_rate: number;
  avg_quiz_accuracy: number;
  active_students_7d: number;
  total_evidence: number;
  risk_count: number;
  evidence_by_kind: Record<string, number>;
  students: Array<{
    user_id: string;
    display_name: string;
    username: string;
    mastery_rate: number;
    quiz_accuracy: number;
    evidence_7d: number;
    evidence_total: number;
    selection_ask_count: number;
    focus_minutes: number;
  }>;
}

export const fetchInsightOverview = (class_id = '') =>
  apiGet<InsightOverview>(
    `/api/teacher/insight/overview${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );

export const fetchTeacherStudentEvaluation = (studentId: string, class_id = '') => {
  const q = class_id ? `?class_id=${encodeURIComponent(class_id)}` : '';
  return apiGet<{
    summary: string;
    dimensions: Record<string, unknown>;
    strengths: string[];
    weaknesses: string[];
    suggestions: string[];
    mastery_rate: number;
    quiz_accuracy: number;
    selection_ask_count: number;
    learn_heatmap_summary: {
      by_kind?: Record<string, number>;
      by_day?: Record<string, number>;
      total_evidence?: number;
    };
  }>(`/api/teacher/students/${studentId}/evaluation-report${q}`);
};

export type VaultTreeNode = {
  name: string;
  path?: string;
  type?: 'file' | 'dir' | string;
  children?: VaultTreeNode[];
};

export const fetchTeacherStudentVaultTree = (studentId: string, class_id = '') => {
  const q = class_id ? `?class_id=${encodeURIComponent(class_id)}` : '';
  return apiGet<{ tree: VaultTreeNode[]; student_id: string }>(
    `/api/teacher/students/${studentId}/vault/tree${q}`,
  );
};

export const fetchTeacherStudentVaultFile = (studentId: string, path: string, class_id = '') => {
  const qs = new URLSearchParams({ path });
  if (class_id) qs.set('class_id', class_id);
  return apiGet<{
    path: string;
    title: string;
    content: string;
    body: string;
    tags: string[];
    updated_at: string;
    word_count: number;
  }>(`/api/teacher/students/${studentId}/vault/file?${qs}`);
};

export const searchTeacherStudentVault = (studentId: string, q: string, class_id = '') => {
  const qs = new URLSearchParams();
  if (q) qs.set('q', q);
  if (class_id) qs.set('class_id', class_id);
  const suffix = qs.toString() ? `?${qs}` : '';
  return apiGet<{
    results: Array<{ path: string; title: string; snippet: string; tags: string[]; updated_at: string }>;
    student_id: string;
  }>(`/api/teacher/students/${studentId}/vault/search${suffix}`);
};

export const importStudents = (class_id: string, students: ImportStudentItem[]) =>
  apiPost<ImportStudentsResult>('/api/teacher/students/import', { class_id, students });

export const forgeTeacherGalaxy = (file: File, title = '') => {
  const form = new FormData();
  form.append('file', file);
  if (title) form.append('title', title);
  return apiPostForm<ForgeGalaxyResult>('/api/teacher/galaxies/forge', form);
};

export const deletePlanet = (slug: string) => apiDelete<{ ok: boolean; slug: string }>(`/api/teacher/planets/${encodeURIComponent(slug)}`);

export interface GatePolicy {
  id?: string;
  class_id: string;
  galaxy_slug: string;
  practice_questions: number;
  practice_min_correct: number;
  explain_pass_threshold: number;
  apply_required_default: boolean;
  learn_evidence_min: number;
  decay_days: { fading: number; meteor: number; dim: number };
  created_at?: string;
  updated_at?: string;
}

export const fetchGatePolicy = (class_id: string, galaxy_slug = '') => {
  const qs = new URLSearchParams({ class_id });
  if (galaxy_slug) qs.set('galaxy_slug', galaxy_slug);
  return apiGet<GatePolicy>(`/api/teacher/gate-policy?${qs}`);
};

export const saveGatePolicy = (payload: Partial<GatePolicy> & { class_id: string }) =>
  apiPut<GatePolicy>('/api/teacher/gate-policy', payload);

export interface ReviewScanResult {
  ok: boolean;
  class_id: string;
  students_scanned: number;
  students_needing_review: number;
  tasks_created: number;
  planets_flagged: number;
  details: Array<{
    user_id: string;
    display_name: string;
    review_planets: number;
    tasks_created: number;
  }>;
}

export const runReviewScan = (class_id: string) =>
  apiPost<ReviewScanResult>('/api/teacher/review-scan', { class_id });

export interface LearningStory extends StudentDetail {
  narrative: string;
  weak_dimensions: string[];
  gate_progress: Array<{
    planet_slug: string;
    planet_name: string;
    status: string;
    decay_state: string;
    next_gate: string | null;
    gates: Record<string, boolean>;
    lit: boolean;
  }>;
  review_planets: Array<{
    planet_slug: string;
    planet_name: string;
    decay_state: string;
    score: number;
  }>;
  recent_agent_runs: Array<{
    id: string;
    scene: string;
    mode: string;
    status: string;
    topic: string;
    current_agent: string;
    created_at: string;
  }>;
  pending_tickets: Array<{
    id: string;
    planet_slug: string;
    planet_name: string;
    confidence: number;
    reason: string;
    created_at: string;
  }>;
  action_hints: string[];
}

export const fetchLearningStory = (student_id: string, class_id = '') => {
  const qs = class_id ? `?class_id=${encodeURIComponent(class_id)}` : '';
  return apiGet<LearningStory>(`/api/teacher/students/${encodeURIComponent(student_id)}/learning-story${qs}`);
};

export const exportGradesCsv = (class_id: string) =>
  apiDownloadBlob(
    `/api/teacher/grades/export?class_id=${encodeURIComponent(class_id)}`,
    `班级成绩_${new Date().toISOString().slice(0, 10)}.csv`,
  );

export const importRosterCsv = (class_id: string, file: File) => {
  const form = new FormData();
  form.append('class_id', class_id);
  form.append('file', file);
  return apiPostForm<{ ok: boolean; created: number; skipped: number; parsed: number; filename: string }>(
    '/api/teacher/roster/import',
    form,
  );
};

export const fetchStudentAssignments = () => apiGet<AssignmentItem[]>('/api/assignments');

export const submitAssignment = (assignmentId: string, content: string, attachment_url = '') =>
  apiPost(`/api/assignments/${assignmentId}/submit`, { content, attachment_url });
