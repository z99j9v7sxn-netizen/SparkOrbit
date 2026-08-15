import { apiGet, apiPost } from './client';

export type ReviewItemType = 'planet' | 'mistake' | 'word' | 'card';
export type ReviewResult = 'remember' | 'fuzzy' | 'forgot';

export interface ReviewQueueItem {
  item_type: ReviewItemType;
  item_id: string;
  front: string;
  back: string;
  meta: Record<string, unknown>;
}

export interface ReviewQueue {
  generated_at: string;
  counts: { planet: number; mistake: number; card: number };
  items: ReviewQueueItem[];
}

export interface ReviewSubmitResult {
  ok: boolean;
  item_type: string;
  result?: string;
  next_review_at?: string;
  points: number;
  supernova?: boolean;
  message?: string;
}

export const fetchReviewQueue = () => apiGet<ReviewQueue>('/api/review/queue');

export const submitReview = (item_type: ReviewItemType, item_id: string, result: ReviewResult) =>
  apiPost<ReviewSubmitResult>('/api/review/submit', { item_type, item_id, result });

export const addReviewCard = (payload: {
  kind?: 'word' | 'card';
  front: string;
  back?: string;
  extra?: string;
  source_id?: string;
}) => apiPost<{ ok: boolean; id: string; kind: string }>('/api/review/cards', payload);

export interface CalendarDay {
  date: string;
  tasks_total: number;
  tasks_done: number;
  focus_minutes: number;
  signed_in: boolean;
  practice_items: number;
  assignments_due: { id: string; title: string; submitted: boolean }[];
}

export interface StudyCalendarData {
  month: string;
  review_due_today: number;
  days: CalendarDay[];
}

export const fetchStudyCalendar = (month: string) =>
  apiGet<StudyCalendarData>(`/api/calendar?month=${encodeURIComponent(month)}`);

export interface WeeklyReport {
  week_start: string;
  week_end: string;
  focus_minutes: number;
  focus_sessions: number;
  daily_focus: { date: string; minutes: number }[];
  planets_lit: number;
  planets_permanent: number;
  reviews_done: number;
  remember_rate: number;
  practice_total: number;
  practice_correct_rate: number;
  mock_count: number;
  mock_best: number;
  sign_in_days: number;
  streak_days: number;
  points: number;
  display_name: string;
  summary: string;
}

export const fetchWeeklyReport = () => apiGet<WeeklyReport>('/api/report/weekly', { timeoutMs: 60_000 });
