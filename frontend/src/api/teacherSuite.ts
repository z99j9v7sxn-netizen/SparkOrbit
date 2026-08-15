import { apiDelete, apiGet, apiPost, apiPut } from './client';
import type { AgentRunDetail, AgentRunSummary } from './admin';

// ---------------------------------------------------------------------------
// 题库
// ---------------------------------------------------------------------------

export interface BankQuestion {
  id: string;
  class_id: string;
  stem: string;
  kind: string;
  options: string[];
  answer: string;
  explanation: string;
  difficulty: string;
  galaxy_slug: string;
  planet_slug: string;
  tags: string[];
  source: string;
  created_at: string;
}

export interface BankQuestionDraft {
  stem: string;
  kind?: string;
  options?: string[];
  answer?: string;
  explanation?: string;
  difficulty?: string;
  galaxy_slug?: string;
  planet_slug?: string;
  tags?: string[];
  class_id?: string;
  source?: string;
}

export const fetchBankQuestions = (params?: { galaxy_slug?: string; difficulty?: string; q?: string }) => {
  const qs = new URLSearchParams();
  if (params?.galaxy_slug) qs.set('galaxy_slug', params.galaxy_slug);
  if (params?.difficulty) qs.set('difficulty', params.difficulty);
  if (params?.q) qs.set('q', params.q);
  const s = qs.toString();
  return apiGet<BankQuestion[]>(`/api/teacher/question-bank${s ? `?${s}` : ''}`);
};

export const createBankQuestion = (payload: BankQuestionDraft) =>
  apiPost<BankQuestion>('/api/teacher/question-bank', payload);

export const bulkCreateBankQuestions = (payload: {
  questions: BankQuestionDraft[];
  class_id?: string;
  galaxy_slug?: string;
  source?: string;
}) => apiPost<{ ok: boolean; created: number }>('/api/teacher/question-bank/bulk', payload);

export const aiGenerateBankQuestions = (payload: {
  topic: string;
  count?: number;
  difficulty?: string;
  galaxy_slug?: string;
}) =>
  apiPost<{ ok: boolean; questions: BankQuestionDraft[]; message: string }>(
    '/api/teacher/question-bank/ai-generate',
    payload,
  );

export const importBankFromAssignment = (assignment_id: string, class_id = '') =>
  apiPost<{ ok: boolean; created: number }>('/api/teacher/question-bank/import-from-assignment', {
    assignment_id,
    class_id,
  });

export const updateBankQuestion = (id: string, payload: Partial<BankQuestionDraft>) =>
  apiPut<BankQuestion>(`/api/teacher/question-bank/${encodeURIComponent(id)}`, payload);

export const deleteBankQuestion = (id: string) =>
  apiDelete<{ ok: boolean }>(`/api/teacher/question-bank/${encodeURIComponent(id)}`);

// ---------------------------------------------------------------------------
// 成绩分析
// ---------------------------------------------------------------------------

export interface AssignmentAnalysis {
  assignment_id: string;
  title: string;
  class_id: string;
  created_at: string;
  due_at: string;
  question_count: number;
  total_students: number;
  submitted_count: number;
  graded_count: number;
  missing_count: number;
  avg_score: number | null;
  max_score: number | null;
  min_score: number | null;
  pass_rate: number | null;
  distribution: Array<{ label: string; count: number }>;
  students: Array<{
    student_id: string;
    student_name: string;
    score: number | null;
    status: string;
    submitted_at: string;
  }>;
}

export interface GradeTrends {
  trend: Array<{
    assignment_id: string;
    title: string;
    created_at: string;
    avg_score: number | null;
    graded_count: number;
  }>;
  progress: Array<{
    student_id: string;
    student_name: string;
    assignment_count: number;
    recent_avg: number;
    delta: number;
  }>;
}

export const fetchAssignmentAnalysis = (assignmentId: string) =>
  apiGet<AssignmentAnalysis>(`/api/teacher/assignments/${encodeURIComponent(assignmentId)}/analysis`);

export const fetchGradeTrends = (class_id = '') =>
  apiGet<GradeTrends>(`/api/teacher/gradebook/trends${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

// ---------------------------------------------------------------------------
// 待办中心
// ---------------------------------------------------------------------------

export interface TeacherTodoItem {
  key: string;
  label: string;
  count: number;
  link: string;
}

export const fetchTeacherTodos = (class_id = '') =>
  apiGet<{ items: TeacherTodoItem[]; total: number }>(
    `/api/teacher/todos${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );

// ---------------------------------------------------------------------------
// 一对一私信
// ---------------------------------------------------------------------------

export interface DmConversation {
  student_id: string;
  student_name: string;
  username: string;
  message_count: number;
  last_body: string;
  last_at: string;
}

export interface DmMessage {
  id: string;
  student_id: string;
  sender_role: string;
  body: string;
  created_at: string;
}

export const fetchDmConversations = (class_id = '') =>
  apiGet<DmConversation[]>(
    `/api/teacher/dm/conversations${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );

export const fetchDmMessages = (studentId: string) =>
  apiGet<DmMessage[]>(`/api/teacher/dm/${encodeURIComponent(studentId)}`);

export const sendDm = (student_id: string, body: string) =>
  apiPost<DmMessage>('/api/teacher/dm', { student_id, body });

// ---------------------------------------------------------------------------
// Agent 运行观测（教师版）
// ---------------------------------------------------------------------------

export function fetchTeacherAgentRuns(params?: {
  class_id?: string;
  limit?: number;
  scene?: string;
  mode?: string;
  status_filter?: string;
  user_id?: string;
}) {
  const q = new URLSearchParams();
  if (params?.class_id) q.set('class_id', params.class_id);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.scene) q.set('scene', params.scene);
  if (params?.mode) q.set('mode', params.mode);
  if (params?.status_filter) q.set('status_filter', params.status_filter);
  if (params?.user_id) q.set('user_id', params.user_id);
  const qs = q.toString();
  return apiGet<AgentRunSummary[]>(`/api/teacher/agent-runs${qs ? `?${qs}` : ''}`);
}

export const fetchTeacherAgentRunDetail = (runId: string) =>
  apiGet<AgentRunDetail>(`/api/teacher/agent-runs/${encodeURIComponent(runId)}`);

// ---------------------------------------------------------------------------
// 学生生成资源审核
// ---------------------------------------------------------------------------

export interface StudentGeneratedResource {
  id: string;
  student_id: string;
  student_name: string;
  kind: string;
  title: string;
  planet_slug: string;
  planet_name: string;
  content_preview: string;
  content: string;
  review_status: string;
  review_comment: string;
  created_at: string;
}

export const fetchStudentGeneratedResources = (class_id = '', review_status = '') => {
  const qs = new URLSearchParams();
  if (class_id) qs.set('class_id', class_id);
  if (review_status) qs.set('review_status', review_status);
  const s = qs.toString();
  return apiGet<StudentGeneratedResource[]>(`/api/teacher/generated-resources${s ? `?${s}` : ''}`);
};

export const reviewGeneratedResource = (id: string, status: 'approved' | 'rejected', comment = '') =>
  apiPost<{ ok: boolean }>(`/api/teacher/generated-resources/${encodeURIComponent(id)}/review`, {
    status,
    comment,
  });

export const recommendGeneratedResource = (id: string, class_id = '', galaxy_slug = '') =>
  apiPost<{ ok: boolean }>(`/api/teacher/generated-resources/${encodeURIComponent(id)}/recommend`, {
    class_id,
    galaxy_slug,
  });

// ---------------------------------------------------------------------------
// 错题热点
// ---------------------------------------------------------------------------

export interface MistakeHotspots {
  hotspots: Array<{
    planet_id: string;
    planet_slug: string;
    planet_name: string;
    galaxy_name: string;
    wrong_count: number;
    attempts: number;
    wrong_rate: number;
    affected_students: number;
    top_tags: string[];
  }>;
  subjects: Array<{ subject: string; count: number }>;
  recent_mistakes: Array<{
    id: string;
    student_name: string;
    question: string;
    subject: string;
    created_at: string;
  }>;
}

export const fetchMistakeHotspots = (class_id = '') =>
  apiGet<MistakeHotspots>(
    `/api/teacher/insight/mistakes${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );

export const dispatchHotspotReview = (class_id: string, planet_slug: string, message?: string) =>
  apiPost<{ ok: boolean; dispatched: number; message: string }>('/api/teacher/insight/mistakes/dispatch', {
    class_id,
    planet_slug,
    ...(message ? { message } : {}),
  });

// ---------------------------------------------------------------------------
// 教学日历
// ---------------------------------------------------------------------------

export interface CalendarEvent {
  id: string;
  class_id: string;
  title: string;
  event_date: string;
  kind: string;
  note: string;
}

export const fetchCalendar = (class_id = '', month = '') => {
  const qs = new URLSearchParams();
  if (class_id) qs.set('class_id', class_id);
  if (month) qs.set('month', month);
  const s = qs.toString();
  return apiGet<{ month: string; events: CalendarEvent[] }>(`/api/teacher/calendar${s ? `?${s}` : ''}`);
};

export const createCalendarEvent = (payload: {
  class_id?: string;
  title: string;
  event_date: string;
  kind?: string;
  note?: string;
}) => apiPost<CalendarEvent>('/api/teacher/calendar', payload);

export const deleteCalendarEvent = (id: string) =>
  apiDelete<{ ok: boolean }>(`/api/teacher/calendar/${encodeURIComponent(id)}`);

// ---------------------------------------------------------------------------
// 学生分组
// ---------------------------------------------------------------------------

export interface StudentGroupItem {
  id: string;
  class_id: string;
  name: string;
  note: string;
  member_ids: string[];
  members: Array<{ id: string; name: string }>;
  created_at: string;
}

export const fetchGroups = (class_id = '') =>
  apiGet<StudentGroupItem[]>(`/api/teacher/groups${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

export const createGroup = (payload: { class_id: string; name: string; member_ids: string[]; note?: string }) =>
  apiPost<StudentGroupItem>('/api/teacher/groups', payload);

export const updateGroup = (id: string, payload: { name?: string; member_ids?: string[]; note?: string }) =>
  apiPut<StudentGroupItem>(`/api/teacher/groups/${encodeURIComponent(id)}`, payload);

export const deleteGroup = (id: string) =>
  apiDelete<{ ok: boolean }>(`/api/teacher/groups/${encodeURIComponent(id)}`);

export const dispatchToGroup = (id: string, message: string, planet_slug = '') =>
  apiPost<{ ok: boolean; dispatched: number; message: string }>(
    `/api/teacher/groups/${encodeURIComponent(id)}/dispatch`,
    { message, planet_slug },
  );

// ---------------------------------------------------------------------------
// 激励系统
// ---------------------------------------------------------------------------

export interface PraiseOverview {
  records: Array<{
    id: string;
    student_id: string;
    student_name: string;
    badge: string;
    points: number;
    message: string;
    created_at: string;
  }>;
  leaderboard: Array<{
    student_id: string;
    student_name: string;
    total_points: number;
    badge_count: number;
    top_badge: string;
  }>;
}

export const fetchPraiseOverview = (class_id = '') =>
  apiGet<PraiseOverview>(`/api/teacher/praise${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

export const createPraise = (payload: {
  student_id: string;
  class_id?: string;
  badge: string;
  points?: number;
  message?: string;
}) => apiPost<{ ok: boolean; id: string }>('/api/teacher/praise', payload);

// ---------------------------------------------------------------------------
// 教学周报
// ---------------------------------------------------------------------------

export interface WeeklyReport {
  period: string;
  markdown: string;
  generated_at: string;
  stats: {
    total_students: number;
    avg_mastery_rate: number;
    assignments_this_week: number;
    high_risk_count: number;
    praise_count: number;
  };
}

export const fetchWeeklyReport = (class_id = '') =>
  apiGet<WeeklyReport>(`/api/teacher/weekly-report${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

// ---------------------------------------------------------------------------
// 模拟面试督导
// ---------------------------------------------------------------------------

export interface InterviewOverview {
  total: number;
  completed: number;
  pending_review: number;
  avg_score: number | null;
  job_count: number;
  academic_count: number;
}

export interface TeacherInterviewSession {
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
  user_id: string;
  assignment_id: string;
  student_name: string;
  review_status: string;
}

export const fetchTeacherInterviewOverview = () =>
  apiGet<InterviewOverview>('/api/teacher/interview/overview');

export const fetchTeacherInterviewSessions = () =>
  apiGet<TeacherInterviewSession[]>('/api/teacher/interview/sessions');

export const fetchTeacherInterviewSession = (id: string) =>
  apiGet<import('./interview').InterviewSessionDetail>(`/api/teacher/interview/sessions/${encodeURIComponent(id)}`);

export const reviewTeacherInterviewReport = (
  reportId: string,
  payload: { comment?: string; score?: number | null; status?: string },
) =>
  apiPost<import('./interview').InterviewReport>(
    `/api/teacher/interview/reports/${encodeURIComponent(reportId)}/review`,
    payload,
  );
