const REQUEST_TIMEOUT_MS = 90_000;
const TIMEOUT_MESSAGE = '请求超时，请稍后重试或检查网络';
const AI_TIMEOUT_MESSAGE = 'AI 生成超时，请稍后重试';

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('sparkorbit_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseError(response: Response): Promise<Error> {
  return new Error(await response.text());
}

type RequestOptions = RequestInit & { timeoutMs?: number; timeoutMessage?: string };

async function requestJson<T>(url: string, init: RequestOptions = {}): Promise<T> {
  const { timeoutMs = REQUEST_TIMEOUT_MS, timeoutMessage, ...fetchInit } = init;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...fetchInit, signal: controller.signal });
    if (response.status === 401 && !url.includes('/api/auth/')) {
      localStorage.removeItem('sparkorbit_token');
      localStorage.removeItem('sparkorbit_user');
      if (typeof window !== 'undefined' && !window.location.pathname.startsWith('/login')) {
        window.location.assign('/login');
      }
    }
    if (!response.ok) throw await parseError(response);
    return (await response.json()) as T;
  } catch (error) {
    if (
      (error instanceof DOMException && error.name === 'AbortError') ||
      (error instanceof Error && error.name === 'AbortError')
    ) {
      const isAiLong =
        typeof timeoutMs === 'number' && timeoutMs >= 60_000 && /\/api\//i.test(url);
      throw new Error(timeoutMessage || (isAiLong ? AI_TIMEOUT_MESSAGE : TIMEOUT_MESSAGE));
    }
    throw error;
  } finally {
    window.clearTimeout(timer);
  }
}

export async function apiPatch<T>(url: string, body: unknown, opts?: { timeoutMs?: number }): Promise<T> {
  return requestJson<T>(url, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
    timeoutMs: opts?.timeoutMs,
  });
}

export async function apiPut<T>(url: string, body: unknown, opts?: { timeoutMs?: number }): Promise<T> {
  return requestJson<T>(url, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
    timeoutMs: opts?.timeoutMs,
  });
}

export async function apiPost<T>(url: string, body: unknown, opts?: { timeoutMs?: number }): Promise<T> {
  return requestJson<T>(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(body),
    timeoutMs: opts?.timeoutMs,
  });
}

export async function apiGet<T>(url: string, opts?: { timeoutMs?: number }): Promise<T> {
  return requestJson<T>(url, { headers: { ...authHeaders() }, timeoutMs: opts?.timeoutMs });
}

export async function apiPostForm<T>(url: string, form: FormData, opts?: { timeoutMs?: number }): Promise<T> {
  return requestJson<T>(url, {
    method: 'POST',
    headers: { ...authHeaders() },
    body: form,
    timeoutMs: opts?.timeoutMs,
  });
}

export async function apiDelete<T>(url: string, opts?: { timeoutMs?: number }): Promise<T> {
  return requestJson<T>(url, {
    method: 'DELETE',
    headers: { ...authHeaders() },
    timeoutMs: opts?.timeoutMs,
  });
}

/** 下载二进制/CSV 等非 JSON 响应 */
export async function apiDownloadBlob(url: string, filename: string): Promise<void> {
  const response = await fetch(url, { headers: { ...authHeaders() } });
  if (!response.ok) throw await parseError(response);
  const blob = await response.blob();
  const objectUrl = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = objectUrl;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(objectUrl);
}
