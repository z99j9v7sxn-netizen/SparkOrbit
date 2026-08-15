import { apiGet, apiPost } from './client';

export interface HeatItem {
  galaxy_slug: string;
  galaxy_name: string;
  planet_slug: string;
  planet_name: string;
  lit_count: number;
  total_students: number;
  mastery_rate: number;
}

export interface ClassOverview {
  total_students: number;
  total_planets: number;
  avg_mastery_rate: number;
  weakest_planets: HeatItem[];
  heatmap: HeatItem[];
}

export interface StudentRisk {
  user_id: string;
  display_name: string;
  username: string;
  lit_count: number;
  total_planets: number;
  mastery_rate: number;
  recent_wrong: number;
  risk_level: 'high' | 'medium' | 'low';
}

export interface ApiQuota {
  deepseek_configured: boolean;
  deepseek_model: string;
  deepseek_base_url: string;
  total_extractions: number;
  total_challenges: number;
}

export const fetchClassOverview = (class_id = '') =>
  apiGet<ClassOverview>(`/api/teacher/overview${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);
export const fetchStudentRisks = (class_id = '') =>
  apiGet<StudentRisk[]>(`/api/teacher/risks${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);

export interface ReviewTicket {
  id: string;
  student_id: string;
  student_name: string;
  planet_slug: string;
  planet_name: string;
  knowledge_point_id: string;
  cited_knowledge_point_id: string;
  confidence: number;
  reason: string;
  question_preview: string;
  status: string;
  created_at: string;
}

export const fetchReviewTickets = (class_id = '') =>
  apiGet<ReviewTicket[]>(
    `/api/teacher/review-tickets${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );
export const resolveReviewTicket = (ticket_id: string) =>
  apiPost<{ ok: boolean; id: string; status: string }>(`/api/teacher/review-tickets/${ticket_id}/resolve`, {});

export const dispatchTask = (student_id: string, message: string, planet_slug?: string) =>
  apiPost<{ ok: boolean; alert_id: string }>('/api/teacher/dispatch', { student_id, message, planet_slug });
export const fetchApiQuota = () => apiGet<ApiQuota>('/api/admin/quota');

export interface ProfileMatrix {
  total_students: number;
  profile_count: number;
  dimension_averages: Record<string, number>;
  explore_score: number;
  conservative_score: number;
  class_tendency: string;
  class_tendency_label: string;
}

export interface GravityWell {
  galaxy_slug: string;
  galaxy_name: string;
  planet_slug: string;
  planet_name: string;
  stuck_count: number;
  total_students: number;
  stuck_rate: number;
  severity: string;
}

export const fetchProfileMatrix = (class_id = '') =>
  apiGet<ProfileMatrix>(`/api/teacher/profile-matrix${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);
export const fetchGravityWells = (class_id = '') =>
  apiGet<GravityWell[]>(`/api/teacher/gravity-wells${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`);
export const interveneStudent = (student_id: string, message: string, planet_slug?: string) =>
  apiPost<{ ok: boolean; alert_id: string; message: string }>('/api/teacher/intervene', { student_id, message, planet_slug });

export async function forgeGalaxyFromPdf(file: File, title?: string): Promise<Record<string, unknown>> {
  const token = localStorage.getItem('sparkorbit_token');
  const form = new FormData();
  form.append('file', file);
  if (title) form.append('title', title);
  const res = await fetch('/api/admin/galaxies/forge', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}
