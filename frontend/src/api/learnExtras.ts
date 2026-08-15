import { apiGet, apiPost } from './client';

export type ResourceKind = 'doc' | 'mindmap' | 'quiz' | 'reading' | 'media' | 'deck' | 'code';

export interface GeneratedResource {
  id: string;
  planet_slug: string;
  planet_name: string;
  kind: ResourceKind;
  title: string;
  content: string;
  meta_json: Record<string, unknown>;
  created_at: string;
}

export interface ResourceGenerateResult {
  run_id: string;
  status: string;
}

export interface ResourceStreamEvent {
  role: string;
  type: string;
  content: string;
  payload: Record<string, unknown>;
}

export const startResourceGeneration = (
  planet_slug: string,
  kinds: ResourceKind[],
  extra_requirements = '',
  quiz_types: string[] = [],
  deck_template = 'orbit',
) =>
  apiPost<ResourceGenerateResult>('/api/resources/generate', {
    planet_slug,
    kinds,
    extra_requirements,
    quiz_types,
    deck_template,
  });

export interface DeckTemplateMeta {
  id: string;
  name: string;
  description: string;
  suitable: string;
  dark: boolean;
  colors: { bg: string; accent: string; title: string; body: string; bar: string };
}

export const fetchDeckTemplates = () =>
  apiGet<{ templates: DeckTemplateMeta[] }>('/api/resources/deck-templates');

export const fetchLearnResources = (planet_slug = '', kind = '') => {
  const q = new URLSearchParams();
  if (planet_slug) q.set('planet_slug', planet_slug);
  if (kind) q.set('kind', kind);
  const suffix = q.toString() ? `?${q}` : '';
  return apiGet<GeneratedResource[]>(`/api/learn/resources${suffix}`);
};

export const fetchLearnResource = (id: string) => apiGet<GeneratedResource>(`/api/learn/resources/${id}`);

export function resourceStreamUrl(runId: string) {
  return `/api/resources/generate/${encodeURIComponent(runId)}/stream`;
}

export async function consumeResourceStream(
  runId: string,
  onEvent: (event: ResourceStreamEvent) => void,
): Promise<void> {
  const token = localStorage.getItem('sparkorbit_token');
  const res = await fetch(resourceStreamUrl(runId), {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok || !res.body) throw new Error('资源生成流连接失败');
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
        onEvent(JSON.parse(line.slice(5).trim()) as ResourceStreamEvent);
      } catch {
        /* ignore */
      }
    }
  }
}

export interface LearningPathStep {
  planet_slug: string;
  planet_name: string;
  action: string;
  resource_kinds: string[];
  reason: string;
  estimated_minutes: number;
  completed: boolean;
  mounted?: Array<{ kind: string; id: string; title: string; reason?: string }>;
  weak_dims?: string[];
  day?: number;
  date?: string;
}

export interface LearningPath {
  id: string;
  title: string;
  goal: string;
  steps: LearningPathStep[];
  status: string;
  progress: number;
  created_at: string;
  kind?: string;
  meta?: { exam_name?: string; exam_date?: string; days_left?: number };
}

export interface RecommendationItem {
  kind: string;
  title: string;
  reason: string;
  resource_id?: string;
  planet_slug?: string;
  planet_name?: string;
}

export interface EvaluationReport {
  summary: string;
  dimensions: Record<string, unknown>;
  strengths: string[];
  weaknesses: string[];
  suggestions: string[];
  mastery_rate: number;
  quiz_accuracy: number;
  selection_ask_count?: number;
  learn_heatmap_summary?: Record<string, unknown>;
}

export interface ProfileTimelineItem {
  id: string;
  student_name: string;
  summary: string;
  scores: Record<string, number>;
  created_at?: string;
  source: string;
}

export const generateLearningPath = (goal = '', use_evaluation = true) =>
  apiPost<LearningPath>('/api/learn/path/generate', { goal, use_evaluation });

export const applyEvaluationToPath = () =>
  apiPost<LearningPath>('/api/learn/evaluation-report/apply-to-path', {});

export interface ClosedLoopResult {
  ok: boolean;
  run_id: string;
  mode: string;
  mastery_rate: number;
  message: string;
  targets: Array<{ planet_slug: string; planet_name: string; kinds?: string[] }>;
  generated: Array<Record<string, unknown>>;
  suggestions?: string[];
  path?: LearningPath;
}

export const runClosedLoop = (top_k = 2, auto_generate = true) =>
  apiPost<ClosedLoopResult>(
    `/api/learn/closed-loop/run?top_k=${top_k}&auto_generate=${auto_generate ? 'true' : 'false'}`,
    {},
    { timeoutMs: 180_000 },
  );

export const fetchLearningPath = () => apiGet<LearningPath | null>('/api/learn/path');

export const completePathStep = (step_index: number) =>
  apiPost<LearningPath>(`/api/learn/path/steps/${step_index}/complete`, {});

export const mountPathStep = (
  step_index: number,
  payload: { kind: string; id: string; title?: string; reason?: string; unmount?: boolean },
) => apiPost<LearningPath>(`/api/learn/path/steps/${step_index}/mount`, payload);

export const fetchRecommendations = () => apiGet<RecommendationItem[]>('/api/learn/recommendations');

export const fetchSprintPath = () => apiGet<LearningPath | null>('/api/learn/sprint');

export const generateSprintPath = (exam_name: string, exam_date: string) =>
  apiPost<LearningPath>('/api/learn/sprint/generate', { exam_name, exam_date }, { timeoutMs: 120_000 });

export const completeSprintStep = (path_id: string, step_index: number) =>
  apiPost<LearningPath>(`/api/learn/sprint/${path_id}/steps/${step_index}/complete`, {});

export const fetchEvaluationReport = () => apiGet<EvaluationReport>('/api/learn/evaluation-report');

export interface MasterySeries {
  planet_slug: string;
  planet_name: string;
  labels: string[];
  scores: number[];
  sample_sparse: boolean;
}

export interface GalaxyMastery {
  galaxy_name: string;
  avg_score: number;
  planet_count: number;
}

export interface AccuracyDaily {
  date: string;
  correct_rate: number;
  attempts: number;
}

export interface WeakPlanet {
  planet_slug: string;
  planet_name: string;
  galaxy_name: string;
  score: number;
  status: string;
  recent_accuracy: number;
  trend: string;
  last_practiced_at?: string;
}

export interface MasteryOverview {
  series: MasterySeries[];
  by_galaxy: GalaxyMastery[];
  accuracy_daily: AccuracyDaily[];
  weak_planets: WeakPlanet[];
}

export const fetchMasteryOverview = () => apiGet<MasteryOverview>('/api/learn/mastery-overview');

export const fetchProfileTimeline = () => apiGet<ProfileTimelineItem[]>('/api/profiles/timeline');

export const refreshProfileManual = () => apiPost<{ ok: boolean; message: string }>('/api/profiles/refresh', {});

export async function companionChatStream(
  message: string,
  mode: 'companion' | 'tutor' = 'companion',
  planet_slug = '',
  onToken: (token: string) => void,
  socratic = true,
): Promise<void> {
  const token = localStorage.getItem('sparkorbit_token');
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), 90_000);
  try {
    const res = await fetch('/api/agents/companion/stream', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: JSON.stringify({ message, mode, planet_slug, socratic }),
      signal: controller.signal,
    });
    if (!res.ok || !res.body) throw new Error('流式对话失败');
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
          const data = JSON.parse(line.slice(5).trim()) as { token?: string };
          if (data.token) onToken(data.token);
        } catch {
          /* ignore */
        }
      }
    }
  } catch (error) {
    if (
      (error instanceof DOMException && error.name === 'AbortError') ||
      (error instanceof Error && error.name === 'AbortError')
    ) {
      throw new Error('AI 生成超时，请稍后重试');
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}
