export const TITLE_MAP: Record<string, string> = {
  'title-stargazer': '星轨领航员',
  'title-focus': '专注守望者',
};

export function titleDisplayName(titleId?: string | null): string {
  if (!titleId) return '';
  return TITLE_MAP[titleId] || titleId;
}
