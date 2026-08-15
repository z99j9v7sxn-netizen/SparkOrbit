export function cleanSummaryText(raw: string): string {
  const text = (raw || '')
    .replace(/\[随学随新[^\]]*\]/g, '')
    .replace(/画像抽取未完成[：:].*/g, '')
    .trim();
  if (!text || text === '未知' || /^待补充/.test(text)) return '';
  return text;
}
