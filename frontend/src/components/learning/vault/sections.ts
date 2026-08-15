/** 语义化分区：磁盘仍用 Obsidian 编号目录，前端只做展示映射 */

export type VaultSectionId =
  | 'recent'
  | 'bookmarks'
  | 'planets'
  | 'daily'
  | 'clips'
  | 'inbox'
  | 'habits'
  | 'workshop'
  | 'canvas'
  | 'all';

export type VaultSection = {
  id: VaultSectionId;
  label: string;
  hint: string;
  /** 对应磁盘顶级目录；虚拟分区为空 */
  folder?: string;
  icon: string;
};

export const VAULT_SECTIONS: VaultSection[] = [
  { id: 'recent', label: '最近编辑', hint: '按更新时间排序', icon: '/icons/clock.svg' },
  { id: 'bookmarks', label: '我的收藏', hint: '你标星的笔记', icon: '/icons/star.svg' },
  { id: 'planets', label: '行星笔记', hint: '按星系整理的知识点', folder: '10-Planets', icon: '/icons/planet.svg' },
  { id: 'daily', label: '学习日记', hint: '每日学习记录', folder: '50-Daily', icon: '/icons/calendar.svg' },
  { id: 'clips', label: '划词剪藏', hint: '从教材 / 演武剪下的片段', folder: '20-Clips', icon: '/icons/scissors.svg' },
  { id: 'workshop', label: '工坊产物', hint: '资源工坊手动入库', folder: '70-Workshop', icon: '/icons/forge.svg' },
  { id: 'inbox', label: '收集箱', hint: '尚未归类的草稿', folder: '00-Inbox', icon: '/icons/inbox.svg' },
  { id: 'habits', label: '学情摘要', hint: 'AI 习惯与画像摘要', folder: '30-Habits', icon: '/icons/growth.svg' },
  { id: 'canvas', label: '思维画布', hint: 'Obsidian Canvas', folder: '60-Canvas', icon: '/icons/map.svg' },
  { id: 'all', label: '全部文件', hint: '文件系统视图', icon: '/icons/folder.svg' },
];

export function pathMatchesSection(path: string, section: VaultSection): boolean {
  if (!section.folder) return true;
  return path === section.folder || path.startsWith(`${section.folder}/`);
}

export function relativeTime(iso?: string): string {
  if (!iso) return '';
  const t = Date.parse(iso);
  if (Number.isNaN(t)) return '';
  const diff = Date.now() - t;
  const m = Math.floor(diff / 60000);
  if (m < 1) return '刚刚';
  if (m < 60) return `${m} 分钟前`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} 小时前`;
  const d = Math.floor(h / 24);
  if (d < 30) return `${d} 天前`;
  return new Date(t).toLocaleDateString();
}
