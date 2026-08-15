import { apiGet, apiPost, apiPostForm, apiDelete } from './client';

export type GateId = 'learn' | 'practice' | 'explain' | 'apply';

export type GateSnapshot = {
  mastery_phase: string;
  status: string;
  gates: { learn: boolean; practice: boolean; explain: boolean; apply: boolean };
  apply_required: boolean;
  learn_evidence_count: number;
  practice_questions: number;
  practice_min_correct: number;
  can_challenge: boolean;
  lit_ready: boolean;
  next_gate?: GateId | null;
  lit?: boolean;
};

export type StarAsset = {
  id: string;
  title: string;
  asset_type: string;
  galaxy_slug: string;
  planet_slug: string;
  file_url: string;
  bilibili_bvid: string;
  description: string;
  page_count: number;
  chunk_count: number;
  status: string;
  created_at: string;
  owner_id?: string;
  class_id?: string;
  meta_json?: Record<string, unknown>;
};

export type VizTrace = {
  id: string;
  title: string;
  structure: 'tree' | 'array' | 'graph' | string;
  code: string;
  steps: Array<{
    line?: number;
    narrate?: string;
    vars?: Record<string, unknown>;
    stack?: string[];
    nodes?: Array<{ id: string; label: string; x: number; y: number }>;
    edges?: Array<[string, string] | [string, string, number] | string[]>;
    bars?: number[];
    highlight?: Array<string | number>;
    predict?: {
      question?: string;
      options?: Array<{ key: string; text: string }>;
      answer?: string;
      answer_key?: string;
    };
  }>;
};

export const fetchGates = (planetSlug: string) =>
  apiGet<GateSnapshot>(`/api/mastery/${encodeURIComponent(planetSlug)}/gates`);

export const passExplainGate = (planetSlug: string, score = 0.8) =>
  apiPost<GateSnapshot>(`/api/mastery/${encodeURIComponent(planetSlug)}/gates/explain?score=${score}`, {});

export const recordLearnGate = (planetSlug: string, kind: string, detail = '') => {
  const body = new FormData();
  body.set('kind', kind);
  body.set('detail', detail);
  return apiPostForm<GateSnapshot>(`/api/mastery/${encodeURIComponent(planetSlug)}/gates/learn`, body);
};

export const listStarAssets = (galaxySlug = '', assetType = '') => {
  const q = new URLSearchParams();
  if (galaxySlug) q.set('galaxy_slug', galaxySlug);
  if (assetType) q.set('asset_type', assetType);
  const qs = q.toString();
  return apiGet<StarAsset[]>(`/api/starlib/assets${qs ? `?${qs}` : ''}`);
};

export const deleteStarAsset = (assetId: string) =>
  apiDelete<{ ok: boolean; id: string }>(`/api/starlib/assets/${encodeURIComponent(assetId)}`);

export const markStarProgress = (assetId: string, page = 1, seconds = 30) =>
  apiPost(`/api/starlib/assets/${encodeURIComponent(assetId)}/progress?page=${page}&seconds=${seconds}`, {});

export const recommendBilibili = (topic: string) =>
  apiGet<Array<{ title: string; reason: string; search_url: string; bvid?: string; embed_url?: string }>>(
    `/api/starlib/bilibili/recommend?topic=${encodeURIComponent(topic)}`,
  );

export function createBilibiliAsset(body: {
  title: string;
  bvid: string;
  galaxy_slug?: string;
  planet_slug?: string;
  description?: string;
  class_id?: string;
}) {
  return apiPost<StarAsset>('/api/starlib/bilibili', body);
}

export function uploadStarlibPdf(payload: {
  file: File;
  title?: string;
  galaxy_slug?: string;
  planet_slug?: string;
  asset_type?: string;
  description?: string;
  class_id?: string;
}) {
  const body = new FormData();
  body.set('file', payload.file);
  if (payload.title) body.set('title', payload.title);
  if (payload.galaxy_slug) body.set('galaxy_slug', payload.galaxy_slug);
  if (payload.planet_slug) body.set('planet_slug', payload.planet_slug);
  body.set('asset_type', payload.asset_type || 'book');
  if (payload.description) body.set('description', payload.description);
  if (payload.class_id) body.set('class_id', payload.class_id);
  return apiPostForm<StarAsset>('/api/starlib/upload', body);
}

export const listStarLectures = (galaxySlug = '') => {
  const q = galaxySlug ? `?galaxy_slug=${encodeURIComponent(galaxySlug)}` : '';
  return apiGet<StarAsset[]>(`/api/starlib/lectures${q}`);
};

export const listVizTraces = () =>
  apiGet<Array<{ id: string; title: string; structure: string; step_count: number }>>('/api/algo-viz/traces');

export const matchVizTrace = (planetSlug: string) =>
  apiGet<VizTrace>(`/api/algo-viz/match?planet_slug=${encodeURIComponent(planetSlug)}`);

export const getVizTrace = (traceId: string) =>
  apiGet<VizTrace>(`/api/algo-viz/traces/${encodeURIComponent(traceId)}`);

export const completeViz = (planetSlug: string, traceId: string, stepsViewed: number, totalSteps: number) => {
  const body = new FormData();
  body.set('planet_slug', planetSlug);
  body.set('trace_id', traceId);
  body.set('steps_viewed', String(stepsViewed));
  body.set('total_steps', String(totalSteps));
  return apiPostForm('/api/algo-viz/complete', body);
};

export const predictViz = (payload: {
  trace_id: string;
  step_index: number;
  answer: string;
  planet_slug?: string;
}) =>
  apiPost<{
    ok: boolean;
    correct: boolean;
    question?: string;
    expected?: string;
    apply_credit?: boolean;
    lit?: boolean;
    detail?: string;
  }>('/api/algo-viz/predict', payload);

export const generateViz = (topic: string, planetSlug = '') => {
  const body = new FormData();
  body.set('topic', topic);
  body.set('planet_slug', planetSlug);
  return apiPostForm<VizTrace>('/api/algo-viz/generate', body, { timeoutMs: 90_000 });
};

export const rerunViz = (payload: {
  structure: string;
  code?: string;
  initial: Record<string, unknown>;
  title?: string;
}) => apiPost<VizTrace>('/api/algo-viz/rerun', payload, { timeoutMs: 90_000 });

export const codelabExercise = (planetSlug: string) => {
  const body = new FormData();
  body.set('planet_slug', planetSlug);
  return apiPostForm('/api/codelab/exercise', body);
};

export const codelabHint = (planetSlug: string, code: string, question = '') => {
  const body = new FormData();
  body.set('planet_slug', planetSlug);
  body.set('code', code);
  body.set('question', question);
  return apiPostForm<{ hint?: string; next_question?: string }>('/api/codelab/hint', body);
};

export const codelabExplain = (planetSlug: string, code: string, question = '') => {
  const body = new FormData();
  body.set('planet_slug', planetSlug);
  body.set('code', code);
  body.set('question', question);
  return apiPostForm<{ explain?: string; pitfalls?: string; next_step?: string }>('/api/codelab/explain', body);
};

export const codelabPassed = (planetSlug: string, passed = 1, total = 1) => {
  const body = new FormData();
  body.set('planet_slug', planetSlug);
  body.set('passed', String(passed));
  body.set('total', String(total));
  return apiPostForm<{ ok?: boolean; lit?: boolean; gates?: GateSnapshot }>('/api/codelab/passed', body);
};

export type CodelabRunResult = {
  stdout: string;
  stderr: string;
  exit_code: number;
  runner?: string;
};

export const codelabRun = (code: string, timeout = 3) =>
  apiPost<CodelabRunResult>('/api/codelab/run', { code, timeout });

export type SelectionAskResult = {
  answer: string;
  citations?: Array<{ source: string; snippet: string; knowledge_point_id?: string }>;
  gates?: GateSnapshot;
  explain_score?: number | null;
  explain_rubric?: Record<string, unknown> | null;
};

export const selectionAsk = (payload: {
  quote?: string;
  asset_id?: string;
  page_no?: number;
  planet_slug?: string;
  question?: string;
  image_base64?: string;
  image_mime?: string;
  mode?: 'tutor' | 'feynman';
  socratic?: boolean;
}) => apiPost<SelectionAskResult>('/api/companion/selection-ask', payload, { timeoutMs: 90_000 });

export const clipNote = (planetSlug: string, block: Record<string, unknown>, title = '') =>
  apiPost('/api/notes/clip', { planet_slug: planetSlug, block, title });

export const aiSummaryNote = (planetSlug: string) =>
  apiPost('/api/notes/ai-summary', { planet_slug: planetSlug });
