export function parseApiError(err: unknown, fallback: string): string {
  if (!(err instanceof Error)) return fallback;
  const raw = err.message.trim();
  if (!raw) return fallback;
  try {
    const parsed = JSON.parse(raw) as { detail?: string | Array<{ msg?: string }> };
    if (typeof parsed.detail === 'string') return parsed.detail;
    if (Array.isArray(parsed.detail)) {
      const first = parsed.detail.find((item) => item?.msg);
      if (first?.msg) return first.msg;
    }
  } catch {
    // ignore JSON parse errors
  }
  return raw.length > 120 ? `${raw.slice(0, 120)}…` : raw;
}
