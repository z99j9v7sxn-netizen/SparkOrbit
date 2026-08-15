export interface SimEvent {
  role: 'Teacher' | 'Mirror' | 'Evaluator' | 'PathPlanner' | 'System';
  type: string;
  content: string;
  payload?: Record<string, unknown>;
}

export interface SimStartResponse {
  run_id: string;
  status: string;
  topic: string;
}

function authHeaders(): Record<string, string> {
  const token = localStorage.getItem('sparkorbit_token');
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function parseErrorDetail(res: Response, fallback: string): Promise<string> {
  try {
    const body = (await res.json()) as { detail?: string | Array<{ msg?: string }> };
    if (typeof body.detail === 'string') return body.detail;
    if (Array.isArray(body.detail)) {
      const first = body.detail.find((item) => item?.msg);
      if (first?.msg) return first.msg;
    }
  } catch {
    /* ignore */
  }
  return fallback;
}

/** 启动一次影子镜像推演，返回 run_id 供后续 SSE 订阅。
 *  topic：来自前端点击的行星/知识点（杜绝张冠李戴）。
 *  overrides：教师端「时空扭曲」沙盘的维度分数覆盖。
 *  options.userId：目标学生；options.studentProfileId：指定画像。 */
export async function startMirrorSimulation(
  topic: string,
  overrides: Record<string, number> = {},
  targetDimension?: string,
  options?: { userId?: string; studentProfileId?: string; planetSlug?: string },
): Promise<SimStartResponse> {
  const res = await fetch('/api/simulations/mirror', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({
      topic,
      dimension_overrides: overrides,
      ...(targetDimension ? { target_dimension: targetDimension } : {}),
      ...(options?.userId ? { user_id: options.userId } : {}),
      ...(options?.studentProfileId ? { student_profile_id: options.studentProfileId } : {}),
      ...(options?.planetSlug ? { planet_slug: options.planetSlug } : {}),
    }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, '推演启动失败'));
  return res.json();
}

/** 后端推演事件类型全集（event: <type>），用于文档/调试。 */
export const SIM_EVENT_TYPES = [
  'boot',
  'thinking',
  'question',
  'note',
  'system_prompt',
  'answer',
  'evaluation',
  'root_cause',
  'planning',
  'learning_path',
  'universe',
  'multiverse_result',
  'recommendation',
  'done',
] as const;

/** 启动平行宇宙推演 */
export async function startMultiverseSimulation(
  topic: string,
  overrides: Record<string, number> = {},
  targetDimension?: string,
  options?: { userId?: string; studentProfileId?: string; planetSlug?: string },
): Promise<SimStartResponse> {
  const res = await fetch('/api/simulations/multiverse', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...authHeaders(),
    },
    body: JSON.stringify({
      topic,
      dimension_overrides: overrides,
      ...(targetDimension ? { target_dimension: targetDimension } : {}),
      ...(options?.userId ? { user_id: options.userId } : {}),
      ...(options?.studentProfileId ? { student_profile_id: options.studentProfileId } : {}),
      ...(options?.planetSlug ? { planet_slug: options.planetSlug } : {}),
    }),
  });
  if (!res.ok) throw new Error(await parseErrorDetail(res, '平行宇宙推演启动失败'));
  return res.json();
}

/**
 * 订阅推演 SSE 流（fetch + Authorization，避免 EventSource 无法带 Bearer）。
 * signal 用于组件卸载时中止。
 */
export async function streamSimulation(
  runId: string,
  onEvent: (ev: SimEvent) => void,
  options: { signal?: AbortSignal } = {},
): Promise<void> {
  const res = await fetch(`/api/simulations/${encodeURIComponent(runId)}/stream`, {
    headers: { ...authHeaders(), Accept: 'text/event-stream' },
    signal: options.signal,
  });
  if (!res.ok || !res.body) {
    throw new Error(await parseErrorDetail(res, `推演流连接失败（${res.status}）`));
  }

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
      const dataLines = part
        .split('\n')
        .filter((line) => line.startsWith('data:'))
        .map((line) => line.slice(5).trim());
      if (!dataLines.length) continue;
      const raw = dataLines.join('\n');
      if (!raw || raw === '[DONE]') continue;
      try {
        const payload = JSON.parse(raw) as SimEvent;
        onEvent(payload);
        if (payload.type === 'done') return;
      } catch {
        /* 忽略解析异常 */
      }
    }
  }
}
