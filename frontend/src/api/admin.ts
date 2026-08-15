import { apiDelete, apiDownloadBlob, apiGet, apiPatch, apiPost, apiPostForm } from './client';

export interface ApiQuota {
  deepseek_configured: boolean;
  deepseek_model: string;
  deepseek_base_url: string;
  total_extractions: number;
  total_challenges: number;
  total_tokens_7d?: number;
  total_calls_7d?: number;
}

export interface ModelConfigItem {
  key: string;
  name: string;
  model: string;
  configured: boolean;
}

export interface SystemOverview {
  deepseek_configured: boolean;
  deepseek_model: string;
  models: ModelConfigItem[];
  maintenance_enabled: boolean;
  maintenance_message: string;
  today_calls: number;
  today_tokens: number;
  today_errors: number;
  user_count: number;
}

export interface MaintenanceStatus {
  enabled: boolean;
  message: string;
}

export interface UserAdminItem {
  id: string;
  username: string;
  display_name: string;
  role: string;
  class_id: string;
  teacher_id: string;
  is_active: boolean;
  created_at: string;
}

export interface GalaxyBrief {
  id: string;
  slug: string;
  name: string;
  description: string;
  planet_count: number;
  is_active: boolean;
}

export interface PlanetBrief {
  id: string;
  slug: string;
  name: string;
  galaxy_slug: string;
  galaxy_name: string;
  difficulty: string;
  orbit_index: number;
}

export interface ApiUsageSummary {
  endpoint: string;
  calls: number;
  total_tokens: number;
  prompt_tokens: number;
  completion_tokens: number;
}

export interface ApiErrorItem {
  id: string;
  endpoint: string;
  model: string;
  user_id: string;
  error_message: string;
  created_at: string;
}

export const fetchSystemOverview = () => apiGet<SystemOverview>('/api/admin/overview');
export const fetchApiQuota = () => apiGet<ApiQuota>('/api/admin/quota');
export const fetchMaintenance = () => apiGet<MaintenanceStatus>('/api/admin/maintenance');
export const updateMaintenance = (enabled: boolean, message?: string) =>
  apiPatch<MaintenanceStatus>('/api/admin/maintenance', { enabled, message });
export const fetchSystemStatus = () => apiGet<MaintenanceStatus>('/api/system/status');

export const fetchAdminUsers = (role = '') =>
  apiGet<UserAdminItem[]>(`/api/admin/users${role ? `?role=${encodeURIComponent(role)}` : ''}`);
export const updateAdminUser = (userId: string, payload: { is_active?: boolean; display_name?: string; role?: string }) =>
  apiPatch<UserAdminItem>(`/api/admin/users/${encodeURIComponent(userId)}`, payload);

export const fetchAdminGalaxies = () => apiGet<GalaxyBrief[]>('/api/admin/galaxies');
export const fetchAdminPlanets = (galaxy_slug = '') =>
  apiGet<PlanetBrief[]>(`/api/admin/planets${galaxy_slug ? `?galaxy_slug=${encodeURIComponent(galaxy_slug)}` : ''}`);
export const deleteAdminPlanet = (slug: string) =>
  apiDelete<{ ok: boolean; slug: string }>(`/api/admin/planets/${encodeURIComponent(slug)}`);

export const fetchAdminUsage = (days = 7) => apiGet<ApiUsageSummary[]>(`/api/admin/usage?days=${days}`);
export const fetchAdminErrors = (limit = 50) => apiGet<ApiErrorItem[]>(`/api/admin/errors?limit=${limit}`);

export async function importStudentsAdmin(class_id: string, students: { username: string; display_name: string; password?: string }[]) {
  return apiPost<{ created: number; skipped: number }>('/api/admin/students/import', { class_id, students });
}

export async function forgeGalaxyFromPdf(file: File, title?: string): Promise<Record<string, unknown>> {
  const form = new FormData();
  form.append('file', file);
  if (title) form.append('title', title);
  return apiPostForm<Record<string, unknown>>('/api/admin/galaxies/forge', form);
}

export interface AgentRunSummary {
  id: string;
  user_id: string;
  user_name: string;
  scene: string;
  mode: string;
  status: string;
  topic: string;
  graph_plan: Record<string, unknown>;
  current_step: number;
  current_agent: string;
  error_message: string;
  created_at: string;
  finished_at: string;
  steps: AgentStepItem[];
}

export interface AgentStepItem {
  id: string;
  step_index: number;
  agent_role: string;
  status: string;
  parallel_group: string;
  summary: string;
  payload: Record<string, unknown>;
  started_at: string;
  finished_at: string;
}

export type AgentRunDetail = AgentRunSummary;

export function fetchAdminAgentRuns(params?: {
  limit?: number;
  scene?: string;
  mode?: string;
  status_filter?: string;
  user_id?: string;
}) {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.scene) q.set('scene', params.scene);
  if (params?.mode) q.set('mode', params.mode);
  if (params?.status_filter) q.set('status_filter', params.status_filter);
  if (params?.user_id) q.set('user_id', params.user_id);
  const qs = q.toString();
  return apiGet<AgentRunSummary[]>(`/api/admin/agent-runs${qs ? `?${qs}` : ''}`);
}

export const fetchAdminAgentRunDetail = (runId: string) =>
  apiGet<AgentRunDetail>(`/api/admin/agent-runs/${encodeURIComponent(runId)}`);

export const seedAdminAgentModes = () =>
  apiPost<{ ok: boolean; created: { id: string; mode: string; scene: string; topic: string }[]; count: number }>(
    '/api/admin/agent-runs/seed-modes',
    {},
  );

export interface DemoHealthCheck {
  id: string;
  label: string;
  ok: boolean;
  detail: string;
  advisory?: boolean;
}

export interface DemoHealth {
  ok: boolean;
  checks: DemoHealthCheck[];
  tips: string[];
  deepseek_configured?: boolean;
  llm_provider?: string;
}

export const fetchAdminDemoHealth = () => apiGet<DemoHealth>('/api/admin/demo-health');

export interface HarnessFileMeta {
  exists: boolean;
  size: number;
  path: string;
}

export interface HarnessMeta {
  root: string;
  files: Record<string, HarnessFileMeta>;
  note: string;
  reproduce: string;
}

export const fetchAdminHarnessMeta = () => apiGet<HarnessMeta>('/api/admin/harness');

export interface HarnessDimension {
  id: string;
  label: string;
  score: number | null;
  evidence_state: string;
  note?: string;
}

export interface HarnessFinding {
  id: string;
  priority: string;
  dimension: string;
  title: string;
  cause: string;
  expected: string;
  repair: string;
  acceptance?: string;
  summary?: string;
}

export interface HarnessFindingsPayload {
  status?: string;
  project?: string;
  note?: string;
  feedforward?: string[];
  dimensions?: HarnessDimension[];
  findings?: HarnessFinding[];
  priority_hints?: string[];
}

export const fetchAdminHarnessFindings = () =>
  apiGet<HarnessFindingsPayload>('/api/admin/harness/findings');

export async function fetchAdminHarnessReportHtml(): Promise<string> {
  const token = localStorage.getItem('sparkorbit_token');
  const res = await fetch('/api/admin/harness/report.html', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(await res.text());
  return res.text();
}

/* ============ 安全运营：审计 / 登录日志 ============ */

export interface AuditLogItem {
  id: string;
  user_id: string;
  username: string;
  action: string;
  target_type: string;
  target_id: string;
  detail: Record<string, unknown>;
  ip: string;
  user_agent: string;
  created_at: string;
}

export interface AuditLogPage {
  total: number;
  items: AuditLogItem[];
  actions: string[];
}

export interface LoginLogItem {
  id: string;
  user_id: string;
  username: string;
  success: boolean;
  reason: string;
  ip: string;
  user_agent: string;
  created_at: string;
}

export interface LoginLogPage {
  total: number;
  items: LoginLogItem[];
  risky_accounts: { username: string; fails: number }[];
}

export function fetchAuditLogs(params?: { action?: string; username?: string; days?: number; limit?: number; offset?: number }) {
  const q = new URLSearchParams();
  if (params?.action) q.set('action', params.action);
  if (params?.username) q.set('username', params.username);
  if (params?.days) q.set('days', String(params.days));
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  const qs = q.toString();
  return apiGet<AuditLogPage>(`/api/admin/audit-logs${qs ? `?${qs}` : ''}`);
}

export function fetchLoginLogs(params?: { username?: string; success?: string; days?: number; limit?: number; offset?: number }) {
  const q = new URLSearchParams();
  if (params?.username) q.set('username', params.username);
  if (params?.success) q.set('success', params.success);
  if (params?.days) q.set('days', String(params.days));
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  const qs = q.toString();
  return apiGet<LoginLogPage>(`/api/admin/login-logs${qs ? `?${qs}` : ''}`);
}

/* ============ 安全运营：告警中心 ============ */

export interface SystemAlertItem {
  id: string;
  level: string;
  category: string;
  title: string;
  detail: string;
  status: string;
  triage_verdict: string;
  triage_note: string;
  created_at: string;
  resolved_at: string;
}

export interface AlertsPage {
  items: SystemAlertItem[];
  open_count: number;
}

export function fetchAdminAlerts(params?: { status_filter?: string; level?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.status_filter) q.set('status_filter', params.status_filter);
  if (params?.level) q.set('level', params.level);
  if (params?.limit) q.set('limit', String(params.limit));
  const qs = q.toString();
  return apiGet<AlertsPage>(`/api/admin/alerts${qs ? `?${qs}` : ''}`);
}

export const scanAdminAlerts = () =>
  apiPost<{ ok: boolean; created: SystemAlertItem[]; count: number }>('/api/admin/alerts/scan', {});

export const updateAdminAlert = (alertId: string, status: string) =>
  apiPatch<SystemAlertItem>(`/api/admin/alerts/${encodeURIComponent(alertId)}`, { status });

export const triageAdminAlert = (alertId: string) =>
  apiPost<SystemAlertItem>(`/api/admin/alerts/${encodeURIComponent(alertId)}/triage`, {}, { timeoutMs: 90_000 });

/* ============ 安全运营：安全日报 ============ */

export interface SecurityReportItem {
  id: string;
  report_date: string;
  summary: Record<string, unknown>;
  markdown_content: string;
  generated_by: string;
  created_at: string;
}

export const fetchSecurityReports = (limit = 30) =>
  apiGet<SecurityReportItem[]>(`/api/admin/reports?limit=${limit}`);

export const fetchSecurityReportDetail = (date: string) =>
  apiGet<SecurityReportItem>(`/api/admin/reports/${encodeURIComponent(date)}`);

export const generateSecurityReport = (reportDate = '', force = false) =>
  apiPost<SecurityReportItem>('/api/admin/reports/generate', { report_date: reportDate, force }, { timeoutMs: 120_000 });

/* ============ 数据分析 ============ */

export interface AdminAnalytics {
  kpis: { dau: number; wau: number; total_users: number; new_users_7d: number };
  active_trend: { date: string; active_users: number; calls: number }[];
  registration_trend: { date: string; count: number }[];
  hour_distribution: { hour: number; calls: number }[];
  top_planets: { planet: string; galaxy: string; learners: number; lit: number }[];
  grading_trend: { date: string; count: number }[];
}

export const fetchAdminAnalytics = () => apiGet<AdminAnalytics>('/api/admin/analytics');

/* ============ 系统配置中心 ============ */

export interface SettingItem {
  key: string;
  label: string;
  type: string;
  group: string;
  description: string;
  value: string;
  default: string;
}

export const fetchAdminSettings = () => apiGet<SettingItem[]>('/api/admin/settings');
export const updateAdminSettings = (values: Record<string, string>) =>
  apiPatch<SettingItem[]>('/api/admin/settings', values);

/* ============ 定时任务心跳 ============ */

export interface JobStatusItem {
  id: string;
  label: string;
  interval: string;
  last_run: string;
  ok: boolean;
  detail: string;
}

export const fetchAdminJobs = () => apiGet<JobStatusItem[]>('/api/admin/jobs');

/* ============ 公告 / 导出 / 文件 ============ */

export const sendAdminAnnouncement = (title: string, body: string, role: string) =>
  apiPost<{ ok: boolean; sent: number }>('/api/admin/announcements', { title, body, role });

export const exportAdminCsv = (kind: 'users' | 'usage' | 'audit' | 'login', days = 30) =>
  apiDownloadBlob(`/api/admin/export/${kind}?days=${days}`, `${kind}.csv`);

export interface AdminFileItem {
  path: string;
  category: string;
  size: number;
  modified_at: string;
}

export interface AdminFilesOut {
  categories: { name: string; file_count: number; total_size: number }[];
  files: AdminFileItem[];
  total_size: number;
  total_files: number;
}

export const fetchAdminFiles = () => apiGet<AdminFilesOut>('/api/admin/files');
export const deleteAdminFile = (path: string) =>
  apiDelete<{ ok: boolean; path: string }>(`/api/admin/files?path=${encodeURIComponent(path)}`);

/* ============ 用户管理增强 ============ */

export const resetAdminUserPassword = (userId: string) =>
  apiPost<{ ok: boolean; user: UserAdminItem; temp_password: string }>(
    `/api/admin/users/${encodeURIComponent(userId)}/reset-password`,
    {},
  );

export const batchSetUserActive = (userIds: string[], isActive: boolean) =>
  apiPost<{ ok: boolean; updated: number }>('/api/admin/users/batch-active', {
    user_ids: userIds,
    is_active: isActive,
  });

export interface UserAdminDetail {
  user: {
    id: string;
    username: string;
    display_name: string;
    role: string;
    class_id: string;
    is_active: boolean;
    points: number;
    streak_days: number;
    created_at: string;
  };
  usage_7d: { calls: number; tokens: number };
  mastery: { total: number; lit: number };
  recent_agent_runs: { id: string; scene: string; mode: string; status: string; topic: string; created_at: string }[];
  recent_logins: LoginLogItem[];
}

export const fetchAdminUserDetail = (userId: string) =>
  apiGet<UserAdminDetail>(`/api/admin/users/${encodeURIComponent(userId)}/detail`);

/* ============ 反馈工单（管理端） ============ */

export interface FeedbackItem {
  id: string;
  user_id: string;
  user_name: string;
  role: string;
  category: string;
  content: string;
  status: string;
  reply: string;
  created_at: string;
  updated_at: string;
}

export interface FeedbackPage {
  items: FeedbackItem[];
  open_count: number;
}

export function fetchAdminFeedback(params?: { status_filter?: string; category?: string; limit?: number }) {
  const q = new URLSearchParams();
  if (params?.status_filter) q.set('status_filter', params.status_filter);
  if (params?.category) q.set('category', params.category);
  if (params?.limit) q.set('limit', String(params.limit));
  const qs = q.toString();
  return apiGet<FeedbackPage>(`/api/admin/feedback${qs ? `?${qs}` : ''}`);
}

export const updateAdminFeedback = (feedbackId: string, payload: { status?: string; reply?: string }) =>
  apiPatch<FeedbackItem>(`/api/admin/feedback/${encodeURIComponent(feedbackId)}`, payload);

/* ============ API 平台：余额 / 密钥管理 ============ */

export interface ProviderBalance {
  ok: boolean;
  is_available?: boolean;
  total_balance?: number;
  granted_balance?: number;
  topped_up_balance?: number;
  currency?: string;
  latency_ms?: number;
  error?: string;
  checked_at?: string;
}

export interface ProviderItem {
  id: string;
  label: string;
  description: string;
  balance_supported: boolean;
  editable: boolean;
  configured: boolean;
  key_masked: string;
  key_source: 'env' | 'override' | 'none';
  model: string;
  model_source: 'env' | 'override' | 'none';
  balance: ProviderBalance | null;
  balance_warn_threshold?: number;
}

export interface ProviderTestResult {
  ok: boolean;
  latency_ms?: number;
  detail: string;
}

export const fetchAdminProviders = () => apiGet<ProviderItem[]>('/api/admin/providers');

export const updateAdminProvider = (provider: string, payload: { api_key?: string; model?: string }) =>
  apiPatch<{ ok: boolean; error: string; provider: ProviderItem }>(
    `/api/admin/providers/${encodeURIComponent(provider)}`,
    { api_key: payload.api_key ?? '', model: payload.model ?? '' },
  );

export const testAdminProvider = (provider: string) =>
  apiPost<ProviderTestResult>(`/api/admin/providers/${encodeURIComponent(provider)}/test`, {}, { timeoutMs: 60_000 });

export const refreshAdminProviderBalance = () =>
  apiPost<ProviderBalance>('/api/admin/providers/refresh-balance', {});
