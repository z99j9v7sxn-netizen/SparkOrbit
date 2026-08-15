import { apiGet, apiPatch, apiPost } from './client';

export interface Galaxy {
  id: string;
  slug: string;
  name: string;
  description: string;
  color: string;
  orbit_radius: number;
  sort_order: number;
  planet_count: number;
  lit_count: number;
}

export type PlanetStatus = 'locked' | 'dim' | 'lit' | 'fading' | 'meteor';

export interface Planet {
  id: string;
  slug: string;
  name: string;
  description: string;
  difficulty: 'easy' | 'medium' | 'hard';
  orbit_index: number;
  angle_deg: number;
  radius_offset: number;
  prerequisites: string[];
  status: PlanetStatus;
  score: number;
  attempts: number;
  decay_state?: string;
  is_permanent?: boolean;
}

export interface GalaxyDetail extends Galaxy {
  planets: Planet[];
}

export interface ChallengeOption {
  key: string;
  text: string;
}

export interface Challenge {
  challenge_id: string;
  planet_id: string;
  planet_name: string;
  question: string;
  options: ChallengeOption[];
  difficulty: string;
  teaching_summary?: string;
  session_id?: string;
  question_index?: number;
  total_questions?: number;
  min_correct_to_lit?: number;
  mastery_phase?: string;
  gates?: { learn?: boolean; practice?: boolean; explain?: boolean; apply?: boolean };
  can_challenge?: boolean;
  lit_ready?: boolean;
}

export interface SubmitResult {
  correct: boolean;
  answer_key: string;
  explanation: string;
  planet_status: PlanetStatus;
  lit: boolean;
  points: number;
  mood: string;
  constellation?: { name: string; badge_icon: string; message: string } | null;
  consecutive_fails?: number;
  can_emit_sos?: boolean;
  session_id?: string;
  session_correct?: number;
  session_answered?: number;
  total_questions?: number;
  min_correct_to_lit?: number;
  session_done?: boolean;
  question_index?: number;
  next_challenge?: Challenge | null;
  knowledge_point_id?: string;
  cited_knowledge_point_id?: string;
  confidence?: number;
  human_review_required?: boolean;
  mastery_phase?: string;
  gates?: { learn?: boolean; practice?: boolean; explain?: boolean; apply?: boolean };
  practice_passed?: boolean;
  lit_ready?: boolean;
  review_ticket_id?: string | null;
  source_refs?: string[];
}

export interface LessonPlan {
  planet_slug: string;
  planet_name: string;
  learning_goals: string[];
  teaching_approach: string;
  example_problems: string[];
  common_mistakes: string[];
  practice_plan: string[];
  self_check: string[];
}

export interface FragmentProgress {
  fragments: { id: string; name: string; icon: string; collected: boolean }[];
  collected_count: number;
  total: number;
  complete: boolean;
  halo?: boolean;
  burst?: boolean;
  message?: string;
}

export interface Constellation {
  slug: string;
  name: string;
  description: string;
  badge_icon: string;
  planet_slugs: string[];
  lit_count: number;
  total: number;
  completed: boolean;
}

export interface SosBeacon {
  id: string;
  sender_id: string;
  sender_name: string;
  planet_slug: string;
  planet_name: string;
  status: string;
  can_respond: boolean;
  is_mine: boolean;
  responses: { responder_name: string; content: string }[];
}

export interface AssessmentState {
  assessment_id: string;
  galaxy_slug: string;
  galaxy_name: string;
  total: number;
  current_index: number;
  question: string;
  options: ChallengeOption[];
  planet_name: string;
  done?: boolean;
  correct?: boolean;
  correct_count?: number;
  lit_planets?: string[];
  message?: string;
}

export interface AvatarState {
  display_name: string;
  points: number;
  mood: string;
  streak_days: number;
  lit_count: number;
  total_planets: number;
  mastery_rate: number;
  avatar_cartoon_url?: string;
}

export interface AvatarGenerateResult {
  status: string;
  cartoon_url?: string;
  prompt?: string;
  msg: string;
}

export interface WeeklyActivity {
  labels: string[];
  hours: number[];
}

export interface MasteryTrend {
  labels: string[];
  scores: number[];
}

export interface StudentAlert {
  id: string;
  alert_type: string;
  title: string;
  message: string;
  level: string;
  planet_slug?: string;
  created_at?: string;
}

export interface OrbitPlanetSnapshot {
  slug: string;
  status: PlanetStatus;
  score: number;
  attempts: number;
}

export interface OrbitSnapshot {
  planets: OrbitPlanetSnapshot[];
  synced_at: string;
}

export interface LeaderboardItem {
  rank: number;
  user_id: string;
  display_name: string;
  lit_count: number;
  points: number;
  is_me: boolean;
}

export interface FriendItem {
  user_id: string;
  display_name: string;
  username: string;
  lit_count: number;
  points: number;
}

export const fetchGalaxies = () => apiGet<Galaxy[]>('/api/galaxies');
export const fetchGalaxyDetail = (slug: string) => apiGet<GalaxyDetail>(`/api/galaxies/${slug}`);
export const fetchAvatarState = () => apiGet<AvatarState>('/api/avatar/state');
export const fetchWeeklyActivity = () => apiGet<WeeklyActivity>('/api/avatar/weekly-activity');
export const fetchPlanetMasteryTrend = (slug: string) => apiGet<MasteryTrend>(`/api/planets/${slug}/mastery-trend`);
export const fetchStudentAlerts = () => apiGet<StudentAlert[]>('/api/alerts/student');
export const fetchOrbitSnapshot = () => apiGet<OrbitSnapshot>('/api/orbit/snapshot');

export async function generateAvatar(photo: File, description?: string): Promise<AvatarGenerateResult> {
  const token = localStorage.getItem('sparkorbit_token');
  const form = new FormData();
  form.append('photo', photo);
  if (description?.trim()) form.append('description', description.trim());
  const response = await fetch('/api/avatar/generate', {
    method: 'POST',
    headers: token ? { Authorization: `Bearer ${token}` } : {},
    body: form,
  });
  if (!response.ok) {
    const raw = await response.text();
    let message = raw;
    try {
      const parsed = JSON.parse(raw) as { detail?: unknown };
      if (typeof parsed.detail === 'string') message = parsed.detail;
    } catch {
      /* 非 JSON 响应，保留 raw */
    }
    throw new Error(message || `分身生成失败（HTTP ${response.status}）`);
  }
  return (await response.json()) as AvatarGenerateResult;
}

export const updateUserProfile = (display_name: string) =>
  apiPatch<{ display_name: string; avatar: string; avatar_cartoon_url: string }>('/api/users/me', { display_name });
export const startChallenge = (slug: string, review = false) =>
  apiPost<Challenge>(`/api/planets/${slug}/challenge${review ? '?review=true' : ''}`, {}, { timeoutMs: 90_000 });
export const generateLessonPlan = (slug: string) => apiPost<LessonPlan>(`/api/planets/${slug}/lesson-plan`, {});
export const submitChallenge = (
  challenge_id: string,
  selected_key: string,
  force_human_review = false,
  self_confidence = '',
) =>
  apiPost<SubmitResult>(
    '/api/challenges/submit',
    {
      challenge_id,
      selected_key,
      force_human_review,
      self_confidence,
    },
    { timeoutMs: 90_000 },
  );
export type TutorSourceRef = {
  galaxy: string;
  source: string;
  snippet: string;
  knowledge_point_id: string;
};

export const companionChat = (
  message: string,
  mode: 'companion' | 'tutor' | 'feynman',
  planet_slug?: string,
  socratic = true,
  supervise = false,
) =>
  apiPost<{
    reply: string;
    mode: string;
    fragment_progress?: FragmentProgress;
    socratic?: boolean;
    sources?: TutorSourceRef[];
    explain_score?: number | null;
    explain_rubric?: Record<string, unknown> | null;
    run_id?: string | null;
    intent?: string | null;
    next_actions?: { type?: string; label?: string; planet_slug?: string; kinds?: string[]; error?: string }[] | null;
    path_id?: string | null;
    resource_run_id?: string | null;
  }>(
    supervise ? '/api/agents/companion/supervise' : '/api/agents/companion',
    { message, mode, planet_slug, socratic, supervise },
    { timeoutMs: 90_000 },
  );
export const fetchLeaderboard = () => apiGet<LeaderboardItem[]>('/api/social/leaderboard');
export const fetchFriends = () => apiGet<FriendItem[]>('/api/social/friends');
export const addFriend = (username: string) => apiPost<FriendItem>('/api/social/friends', { username });

export const fetchFragments = (slug: string) => apiGet<FragmentProgress>(`/api/planets/${slug}/fragments`);
export const reviewPlanet = (slug: string, correct = true) =>
  apiPost<{ success: boolean; supernova: boolean; message: string; points: number }>(`/api/planets/${slug}/review`, { correct });
export const startAssessment = (galaxySlug: string) =>
  apiPost<AssessmentState>(`/api/galaxies/${galaxySlug}/assessment/start`, {});
export const submitAssessment = (galaxySlug: string, assessment_id: string, selected_key: string) =>
  apiPost<AssessmentState>(`/api/galaxies/${galaxySlug}/assessment/submit`, { assessment_id, selected_key });
export const fetchConstellations = () => apiGet<Constellation[]>('/api/constellations');
export const emitSos = (planet_slug: string) => apiPost<{ ok: boolean; message: string }>('/api/social/sos', { planet_slug });
export const fetchSosList = () => apiGet<SosBeacon[]>('/api/social/sos');
export const respondSos = (beaconId: string, content: string) =>
  apiPost<{ ok: boolean; message: string }>(`/api/social/sos/${beaconId}/respond`, { content });
export const fetchRescueAlerts = () => apiGet<{ id: string; message: string }[]>('/api/alerts/rescue');
