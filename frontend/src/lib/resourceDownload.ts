import type { GeneratedResource, ResourceKind } from '../api/learnExtras';

export type ResourceDownloadPayload = {
  filename: string;
  label: string;
  /** 静态文件 URL（pptx / mp4） */
  href?: string;
  /** 文本 Blob 内容 */
  text?: string;
  mime?: string;
  /** 不可下载时的原因（如 PPT 导出失败） */
  error?: string;
};

const QUIZ_TYPE_LABELS: Record<string, string> = {
  choice: '选择题',
  blank: '填空题',
  essay: '大题',
  case: '大题',
  code: '程序题',
};

const CODE_EXT: Record<string, string> = {
  python: 'py',
  py: 'py',
  javascript: 'js',
  js: 'js',
  typescript: 'ts',
  ts: 'ts',
  java: 'java',
  c: 'c',
  cpp: 'cpp',
  'c++': 'cpp',
  go: 'go',
  rust: 'rs',
  sql: 'sql',
  html: 'html',
  css: 'css',
  bash: 'sh',
  shell: 'sh',
};

function safeName(raw: string): string {
  return (raw || 'resource')
    .replace(/[<>:"/\\|?*\u0000-\u001f]/g, '_')
    .replace(/\s+/g, '_')
    .slice(0, 80);
}

function baseName(r: GeneratedResource): string {
  return safeName(r.planet_name || r.title || r.planet_slug || 'resource');
}

function resolveMediaUrl(url?: string): string {
  if (!url) return '';
  if (url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) return url;
  return url.startsWith('/') ? url : `/${url}`;
}

function parseJson(content: string): Record<string, unknown> | null {
  try {
    const v = JSON.parse(content);
    return v && typeof v === 'object' ? (v as Record<string, unknown>) : null;
  } catch {
    return null;
  }
}

function quizToMarkdown(r: GeneratedResource): string {
  const parsed = parseJson(r.content);
  const questions = Array.isArray(parsed?.questions) ? (parsed!.questions as Array<Record<string, unknown>>) : [];
  const lines: string[] = [`# ${r.title || '练习题'}`, ''];
  questions.forEach((q, i) => {
    const type = QUIZ_TYPE_LABELS[String(q.type || '').toLowerCase()] || String(q.type || '题目');
    lines.push(`## ${i + 1}. [${type}] ${q.question || ''}`);
    const opts = q.options;
    if (Array.isArray(opts) && opts.length) {
      lines.push('');
      opts.forEach((o) => lines.push(`- ${o}`));
    } else if (opts) {
      lines.push('', String(opts));
    }
    lines.push('', `**答案：** ${q.answer ?? ''}`);
    if (q.explanation) lines.push('', `**解析：** ${q.explanation}`);
    lines.push('');
  });
  if (!questions.length) lines.push('_暂无题目_');
  return lines.join('\n');
}

function readingToMarkdown(r: GeneratedResource): string {
  const parsed = parseJson(r.content);
  const lines: string[] = [`# ${r.title || '拓展阅读'}`, ''];
  const materials = Array.isArray(parsed?.materials) ? (parsed!.materials as Array<Record<string, unknown>>) : [];
  if (materials.length) {
    lines.push('## 推荐材料', '');
    materials.forEach((m, i) => {
      lines.push(`### ${i + 1}. ${m.title || '材料'}`);
      if (m.summary) lines.push(String(m.summary));
      if (m.url) lines.push(`链接：${m.url}`);
      lines.push('');
    });
  }
  const article = String(parsed?.article || '');
  if (article) {
    lines.push('## 正文', '', article);
  } else if (!materials.length) {
    lines.push(r.content || '_暂无内容_');
  }
  return lines.join('\n');
}

function mindmapJson(r: GeneratedResource): string {
  const meta = r.meta_json || {};
  if (meta.tree) return JSON.stringify(meta.tree, null, 2);
  const parsed = parseJson(r.content);
  if (parsed?.tree) return JSON.stringify(parsed.tree, null, 2);
  if (parsed) return JSON.stringify(parsed, null, 2);
  return r.content || '{}';
}

function codePayload(r: GeneratedResource): { text: string; ext: string } {
  const parsed = parseJson(r.content);
  const lang = String(parsed?.language || 'txt').toLowerCase();
  const ext = CODE_EXT[lang] || 'txt';
  const code = String(parsed?.code || r.content || '');
  const explanation = parsed?.explanation ? `\n\n# 说明\n# ${String(parsed.explanation).replace(/\n/g, '\n# ')}` : '';
  const exercise = parsed?.exercise ? `\n\n# 练习\n# ${String(parsed.exercise).replace(/\n/g, '\n# ')}` : '';
  return { text: code + explanation + exercise, ext };
}

function mediaMeta(r: GeneratedResource): { media_url?: string; slides?: unknown[] } {
  const meta = r.meta_json || {};
  const parsed = parseJson(r.content) || {};
  return {
    media_url: String(meta.media_url || parsed.media_url || '') || undefined,
    slides: Array.isArray(meta.slides)
      ? (meta.slides as unknown[])
      : Array.isArray(parsed.slides)
        ? (parsed.slides as unknown[])
        : [],
  };
}

function deckMeta(r: GeneratedResource): { pptx_url?: string; export_error?: string } {
  const meta = r.meta_json || {};
  const parsed = parseJson(r.content) || {};
  return {
    pptx_url: String(meta.pptx_url || parsed.pptx_url || '') || undefined,
    export_error: String(meta.export_error || parsed.export_error || '') || undefined,
  };
}

/** 按资源类型构建下载描述；不可下时返回带 error 的对象。 */
export function buildResourceDownload(r: GeneratedResource): ResourceDownloadPayload {
  const base = baseName(r);
  const kind = r.kind as ResourceKind;

  if (kind === 'deck') {
    const { pptx_url, export_error } = deckMeta(r);
    if (!pptx_url) {
      return {
        filename: `${base}-deck.pptx`,
        label: '下载 PPT (.pptx)',
        error: export_error || 'PPT 导出失败（请确认已安装 python-pptx）',
      };
    }
    return {
      filename: `${base}-deck.pptx`,
      label: '下载 PPT (.pptx)',
      href: resolveMediaUrl(pptx_url),
    };
  }

  if (kind === 'doc') {
    return {
      filename: `${base}-doc.md`,
      label: '下载讲义 (.md)',
      text: r.content || '',
      mime: 'text/markdown;charset=utf-8',
    };
  }

  if (kind === 'quiz') {
    return {
      filename: `${base}-quiz.md`,
      label: '下载练习题 (.md)',
      text: quizToMarkdown(r),
      mime: 'text/markdown;charset=utf-8',
    };
  }

  if (kind === 'mindmap') {
    return {
      filename: `${base}-mindmap.json`,
      label: '下载思维导图 (.json)',
      text: mindmapJson(r),
      mime: 'application/json;charset=utf-8',
    };
  }

  if (kind === 'reading') {
    return {
      filename: `${base}-reading.md`,
      label: '下载阅读材料 (.md)',
      text: readingToMarkdown(r),
      mime: 'text/markdown;charset=utf-8',
    };
  }

  if (kind === 'code') {
    const { text, ext } = codePayload(r);
    return {
      filename: `${base}-code.${ext}`,
      label: `下载代码 (.${ext})`,
      text,
      mime: 'text/plain;charset=utf-8',
    };
  }

  if (kind === 'media') {
    const { media_url, slides } = mediaMeta(r);
    if (media_url) {
      const url = resolveMediaUrl(media_url);
      const ext = url.split('?')[0].split('.').pop() || 'mp4';
      return {
        filename: `${base}-media.${ext}`,
        label: '下载视频',
        href: url,
      };
    }
    return {
      filename: `${base}-media-storyboard.json`,
      label: '下载分镜 (.json)',
      text: JSON.stringify({ title: r.title, slides }, null, 2),
      mime: 'application/json;charset=utf-8',
    };
  }

  return {
    filename: `${base}-${kind}.txt`,
    label: '下载',
    text: r.content || '',
    mime: 'text/plain;charset=utf-8',
  };
}

export function downloadBlob(filename: string, blob: Blob): void {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.rel = 'noopener';
  a.click();
  URL.revokeObjectURL(url);
}

export function downloadText(filename: string, text: string, mime = 'text/plain;charset=utf-8'): void {
  downloadBlob(filename, new Blob([text], { type: mime }));
}

/** 触发下载；若不可下返回 error 文案。 */
export function triggerResourceDownload(r: GeneratedResource): string | null {
  const payload = buildResourceDownload(r);
  if (payload.error) return payload.error;
  if (payload.href) {
    const a = document.createElement('a');
    a.href = payload.href;
    a.download = payload.filename;
    a.target = '_blank';
    a.rel = 'noopener';
    a.click();
    return null;
  }
  if (payload.text != null) {
    downloadText(payload.filename, payload.text, payload.mime);
    return null;
  }
  return '无法下载该资源';
}
