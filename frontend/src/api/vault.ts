import { apiDelete, apiGet, apiPost, apiPut } from './client';

export type VaultTreeNode = {
  name: string;
  path: string;
  type: 'dir' | 'file';
  children?: VaultTreeNode[];
};

export type VaultFile = {
  path: string;
  title: string;
  content: string;
  body?: string;
  frontmatter?: Record<string, unknown>;
  tags?: string[];
  updated_at?: string;
  word_count?: number;
};

export type VaultGraph = {
  mode: string;
  nodes: Array<{
    id: string;
    name: string;
    path: string;
    category: string;
    symbolSize: number;
    value: number;
    tags?: string[];
    created_at?: string;
  }>;
  edges: Array<{ source: string; target: string; type: string }>;
  categories: Array<{ name: string }>;
};

export type VaultBacklinks = {
  path: string;
  backlinks: Array<{ path: string; title: string; type: string }>;
  outgoing: Array<{ path: string; title: string; type: string; exists: boolean }>;
  unlinked_mentions: Array<{ path: string; title: string }>;
};

export type VaultOpenHint = {
  vault_name: string;
  folder_name?: string;
  export_name?: string;
  launch_vault_name?: string;
  local_path?: string;
  obsidian_uri: string;
  obsidian_uri_by_path?: string;
  download_path: string;
  install_url: string;
  revision: number;
  tip?: string;
};

export type VaultSearchHit = {
  path: string;
  title: string;
  tags?: string[];
  snippet?: string;
  updated_at?: string;
  word_count?: number;
};

export type VaultCanvasData = {
  nodes: Array<{
    id: string;
    type?: string;
    x: number;
    y: number;
    width?: number;
    height?: number;
    text?: string;
    file?: string;
    label?: string;
    color?: string;
  }>;
  edges: Array<{ id: string; fromNode: string; toNode: string; label?: string }>;
};

export const fetchVaultMeta = () => apiGet<{ vault_name: string; revision: number }>('/api/vault/meta');
export const fetchVaultTree = () => apiGet<{ tree: VaultTreeNode[] }>('/api/vault/tree');
export const fetchVaultFile = (path: string) =>
  apiGet<VaultFile>(`/api/vault/file?path=${encodeURIComponent(path)}`);
export const saveVaultFile = (path: string, content: string) =>
  apiPut<VaultFile>('/api/vault/file', { path, content });
export const createVaultFile = (path: string, content = '') =>
  apiPost<VaultFile>('/api/vault/file', { path, content });
export const deleteVaultFile = (path: string) =>
  apiDelete<{ ok: boolean }>(`/api/vault/file?path=${encodeURIComponent(path)}`);
export const searchVault = (q: string) =>
  apiGet<VaultSearchHit[]>(`/api/vault/search?q=${encodeURIComponent(q)}`);
export const fetchVaultGraph = (params: {
  mode?: string;
  path?: string;
  depth?: number;
  show_orphans?: boolean;
  existing_only?: boolean;
}) => {
  const q = new URLSearchParams();
  if (params.mode) q.set('mode', params.mode);
  if (params.path) q.set('path', params.path);
  if (params.depth != null) q.set('depth', String(params.depth));
  if (params.show_orphans != null) q.set('show_orphans', String(params.show_orphans));
  if (params.existing_only != null) q.set('existing_only', String(params.existing_only));
  return apiGet<VaultGraph>(`/api/vault/graph?${q.toString()}`);
};
export const fetchVaultBacklinks = (path: string) =>
  apiGet<VaultBacklinks>(`/api/vault/backlinks?path=${encodeURIComponent(path)}`);
export const fetchVaultOpenHint = () => apiGet<VaultOpenHint>('/api/vault/open-hint');
export const updateVaultName = (vault_name: string) =>
  apiPost<VaultOpenHint>('/api/vault/vault-name', { vault_name });
export const migrateVaultNotes = () =>
  apiPost<{ imported: number; skipped: number; total: number }>('/api/vault/migrate-notes', {});
export const analyzeVault = () =>
  apiPost<{ ok: boolean; summary: string; profile_refreshed: boolean; status?: string }>(
    '/api/vault/analyze',
    {},
  );
export const ingestWorkshopToVault = (resource_id: string) =>
  apiPost<{ ok: boolean; path: string; title: string; kind: string }>('/api/vault/ingest-workshop', {
    resource_id,
  });
export const clipToVault = (body: {
  title?: string;
  content: string;
  planet_slug?: string;
  galaxy_slug?: string;
  source?: string;
}) => apiPost<VaultFile>('/api/vault/clip', body);

export const fetchVaultTemplates = () =>
  apiGet<Array<{ path: string; name: string }>>('/api/vault/templates');
export const applyVaultTemplate = (body: {
  template_path: string;
  dest_path?: string;
  vars?: Record<string, string>;
}) => apiPost<VaultFile>('/api/vault/templates/apply', body);
export const createDailyNote = (day = '') =>
  apiPost<VaultFile>(`/api/vault/daily${day ? `?day=${encodeURIComponent(day)}` : ''}`, {});
export const fetchVaultBookmarks = () =>
  apiGet<Array<{ path: string; title: string; at?: string }>>('/api/vault/bookmarks');
export const toggleVaultBookmark = (path: string, title = '') =>
  apiPost<{ added: boolean; bookmarks: Array<{ path: string; title: string }> }>('/api/vault/bookmarks/toggle', {
    path,
    title,
  });
export const fetchVaultCanvas = (path = '60-Canvas/默认画布.canvas') =>
  apiGet<{ path: string; data: VaultCanvasData }>(`/api/vault/canvas?path=${encodeURIComponent(path)}`);
export const saveVaultCanvas = (path: string, data: VaultCanvasData) =>
  apiPut<{ path: string; data: VaultCanvasData }>('/api/vault/canvas', { path, data });
export const previewVaultNote = (q: string) =>
  apiGet<{ path: string; title: string; snippet: string; exists: boolean }>(
    `/api/vault/preview?q=${encodeURIComponent(q)}`,
  );

export function downloadVaultZip() {
  const token = localStorage.getItem('sparkorbit_token');
  return fetch('/api/vault/export.zip', {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  }).then(async (res) => {
    if (!res.ok) throw new Error(await res.text());
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'SparkOrbit-Vault.zip';
    a.click();
    URL.revokeObjectURL(url);
  });
}
