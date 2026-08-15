/** 伴学 → 资源工坊 SSE：跨挂载竞态用 pending，避免事件丢弃。 */

const STORAGE_KEY = 'sparkorbit_pending_resource_stream';

export type PendingResourceStream = {
  runId: string;
  planetSlug?: string;
  kinds?: string[];
  queuedAt: number;
};

/** 只写 sessionStorage，不广播（忙时排队用，避免同步重入）。 */
export function writePendingResourceStream(detail: {
  runId: string;
  planetSlug?: string;
  kinds?: string[];
}): PendingResourceStream {
  const payload: PendingResourceStream = {
    runId: detail.runId,
    planetSlug: detail.planetSlug,
    kinds: detail.kinds,
    queuedAt: Date.now(),
  };
  try {
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(payload));
  } catch {
    // ignore quota
  }
  return payload;
}

/**
 * 写入 pending；默认广播事件。
 * `broadcast: false` 仅落盘，供 ResourceStudio 忙时排队（禁止同步 re-enter）。
 */
export function setPendingResourceStream(
  detail: {
    runId: string;
    planetSlug?: string;
    kinds?: string[];
  },
  opts?: { broadcast?: boolean },
): void {
  const payload = writePendingResourceStream(detail);
  if (opts?.broadcast === false) return;
  window.dispatchEvent(
    new CustomEvent('sparkorbit:start-resource-stream', {
      detail: {
        runId: payload.runId,
        planetSlug: payload.planetSlug,
        kinds: payload.kinds,
      },
    }),
  );
}

export function peekPendingResourceStream(): PendingResourceStream | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as PendingResourceStream;
    if (!parsed?.runId) return null;
    // 超过 10 分钟视为过期
    if (Date.now() - (parsed.queuedAt || 0) > 10 * 60_000) {
      clearPendingResourceStream();
      return null;
    }
    return parsed;
  } catch {
    return null;
  }
}

export function clearPendingResourceStream(): void {
  try {
    sessionStorage.removeItem(STORAGE_KEY);
  } catch {
    // ignore
  }
}

export function takePendingResourceStream(): PendingResourceStream | null {
  const hit = peekPendingResourceStream();
  if (hit) clearPendingResourceStream();
  return hit;
}
