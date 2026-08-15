export interface AdminNavItem {
  path: string;
  label: string;
  /** 16x16 stroke 图标的 SVG 内部标记（fill/stroke 由外层 svg 控制） */
  icon: string;
  /** 命令面板搜索关键字（拼音/英文别名） */
  keywords?: string;
}

export interface AdminNavGroup {
  label: string;
  items: AdminNavItem[];
}

export const ADMIN_ICONS = {
  overview:
    '<rect x="2.5" y="2.5" width="4.8" height="4.8" rx="1"/><rect x="8.7" y="2.5" width="4.8" height="4.8" rx="1"/><rect x="2.5" y="8.7" width="4.8" height="4.8" rx="1"/><rect x="8.7" y="8.7" width="4.8" height="4.8" rx="1"/>',
  users:
    '<circle cx="6" cy="5.2" r="2.4"/><path d="M1.8 13.4c.7-2.4 2.4-3.6 4.2-3.6s3.5 1.2 4.2 3.6"/><path d="M10.6 3.4a2.4 2.4 0 0 1 0 4.4M12 9.9c1.1.5 1.9 1.6 2.3 3.1"/>',
  content:
    '<path d="m8 1.8 6 3-6 3-6-3 6-3Z"/><path d="m2 8.2 6 3 6-3"/><path d="m2 11.2 6 3 6-3"/>',
  usage: '<path d="M3 13.5V9M8 13.5V2.5M13 13.5V6"/>',
  agents:
    '<circle cx="8" cy="8" r="2.2"/><circle cx="3" cy="3.2" r="1.4"/><circle cx="13" cy="3.2" r="1.4"/><circle cx="8" cy="13.6" r="1.4"/><path d="M4.1 4.3 6.4 6.4M11.9 4.3 9.6 6.4M8 10.2v2"/>',
  harness:
    '<path d="M8 1.8 13 3.8v4c0 3.1-2 5.2-5 6.2-3-1-5-3.1-5-6.2v-4l5-2Z"/><path d="m5.8 7.8 1.6 1.6 2.8-3.2"/>',
  errors:
    '<path d="M8 2.6 14.1 13H1.9L8 2.6Z"/><path d="M8 6.8v2.8"/><path d="M8 11.4h.01"/>',
  maintenance:
    '<path d="M2.5 5h11M2.5 11h11"/><circle cx="6" cy="5" r="1.7"/><circle cx="10" cy="11" r="1.7"/>',
  audit:
    '<path d="M5 2.5h7.5v11H3.5v-9l1.5-2Z"/><path d="M5 2.5v2H3.5"/><path d="M6 7h4.5M6 9.5h4.5M6 12h2.5"/>',
  alerts:
    '<path d="M8 2.2c2.6 0 4 1.9 4 4.3 0 2.8.8 3.6 1.4 4.2H2.6c.6-.6 1.4-1.4 1.4-4.2 0-2.4 1.4-4.3 4-4.3Z"/><path d="M6.6 13.2a1.5 1.5 0 0 0 2.8 0"/>',
  reports:
    '<rect x="3" y="2" width="10" height="12" rx="1.2"/><path d="M5.5 5.2h5M5.5 7.7h5M5.5 10.2h3"/>',
  analytics:
    '<path d="M2.5 13.5h11"/><path d="M4 11V7.5M7 11V4.5M10 11V6M13 11V3.5" stroke-linecap="round"/>',
  settings:
    '<circle cx="8" cy="8" r="2.2"/><path d="M8 1.8v1.8M8 12.4v1.8M1.8 8h1.8M12.4 8h1.8M3.6 3.6l1.3 1.3M11.1 11.1l1.3 1.3M12.4 3.6l-1.3 1.3M4.9 11.1l-1.3 1.3"/>',
  feedback:
    '<path d="M2.5 3.5h11v7.5H8.5L5.5 13.5v-2.5h-3v-7.5Z"/><path d="M5.5 6.2h5M5.5 8.4h3.5"/>',
} as const;

export const adminNavGroups: AdminNavGroup[] = [
  {
    label: '总览',
    items: [
      { path: '/admin', label: '系统概览', icon: ADMIN_ICONS.overview, keywords: 'overview dashboard gailan' },
    ],
  },
  {
    label: '运营',
    items: [
      { path: '/admin/users', label: '用户管理', icon: ADMIN_ICONS.users, keywords: 'user account yonghu' },
      { path: '/admin/content', label: '内容管理', icon: ADMIN_ICONS.content, keywords: 'content galaxy planet neirong' },
      { path: '/admin/usage', label: 'Token 用量', icon: ADMIN_ICONS.usage, keywords: 'usage token yongliang' },
      { path: '/admin/analytics', label: '数据分析', icon: ADMIN_ICONS.analytics, keywords: 'analytics dau trend shujufenxi' },
      { path: '/admin/feedback', label: '反馈工单', icon: ADMIN_ICONS.feedback, keywords: 'feedback ticket fankui' },
    ],
  },
  {
    label: '安全运营',
    items: [
      { path: '/admin/alerts', label: '告警中心', icon: ADMIN_ICONS.alerts, keywords: 'alert triage gaojing' },
      { path: '/admin/reports', label: '安全日报', icon: ADMIN_ICONS.reports, keywords: 'report daily ribao anquan' },
      { path: '/admin/audit', label: '审计日志', icon: ADMIN_ICONS.audit, keywords: 'audit log login shenjii rizhi' },
    ],
  },
  {
    label: 'Agent 工程',
    items: [
      { path: '/admin/agents', label: 'Agent 运行观测', icon: ADMIN_ICONS.agents, keywords: 'agent run observe guance' },
      { path: '/admin/harness', label: 'Agent 工程体检', icon: ADMIN_ICONS.harness, keywords: 'harness quality tijian' },
    ],
  },
  {
    label: '系统',
    items: [
      { path: '/admin/errors', label: '接口异常', icon: ADMIN_ICONS.errors, keywords: 'error incident yichang' },
      { path: '/admin/settings', label: '系统配置', icon: ADMIN_ICONS.settings, keywords: 'settings config quota peizhi' },
      { path: '/admin/maintenance', label: '维护模式', icon: ADMIN_ICONS.maintenance, keywords: 'maintenance weihu' },
    ],
  },
];

export const adminNavItems: AdminNavItem[] = adminNavGroups.flatMap((g) => g.items);
