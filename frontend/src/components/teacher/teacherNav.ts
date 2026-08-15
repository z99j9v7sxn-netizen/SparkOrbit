export interface TeacherNavItem {
  path: string;
  label: string;
  icon: string;
  /** 命令面板搜索关键字（拼音/英文别名） */
  keywords?: string;
}

export interface TeacherNavGroup {
  label: string;
  items: TeacherNavItem[];
}

export const teacherNavGroups: TeacherNavGroup[] = [
  {
    label: '学情',
    items: [
      { path: '/teacher/dashboard', label: '学情看板', icon: '/icons/dashboard.svg', keywords: 'dashboard kanban' },
      { path: '/teacher/insight', label: '学情洞察', icon: '/icons/growth.svg', keywords: 'insight dongcha cuoti hotspot' },
      { path: '/teacher/analysis', label: '成绩分析', icon: '/icons/grades.svg', keywords: 'analysis chengji fenxi trend' },
      { path: '/teacher/agent-activity', label: 'AI 学习动态', icon: '/icons/target.svg', keywords: 'agent activity ai dongtai' },
      { path: '/teacher/improvement', label: '画像改进', icon: '/icons/profile.svg', keywords: 'improvement huaxiang' },
      { path: '/teacher/interview', label: '模拟面试', icon: '/icons/target.svg', keywords: 'interview mianshi audition' },
    ],
  },
  {
    label: '教学',
    items: [
      { path: '/teacher/assignments', label: '作业管理', icon: '/icons/homework.svg', keywords: 'assignment zuoye' },
      { path: '/teacher/question-bank', label: '题库管理', icon: '/icons/homework.svg', keywords: 'question bank tiku' },
      { path: '/teacher/grades', label: '成绩册', icon: '/icons/grades.svg', keywords: 'grade chengji' },
      { path: '/teacher/calendar', label: '教学日历', icon: '/icons/dashboard.svg', keywords: 'calendar rili' },
      { path: '/teacher/attendance', label: '考勤', icon: '/icons/attendance.svg', keywords: 'attendance kaoqin' },
      { path: '/teacher/patrol', label: '巡查', icon: '/icons/patrol.svg', keywords: 'patrol xuncha' },
    ],
  },
  {
    label: '资源',
    items: [
      { path: '/teacher/knowledge', label: '教师知识库', icon: '/icons/archive.svg', keywords: 'knowledge zhishiku' },
      { path: '/teacher/resource-review', label: '资源审核', icon: '/icons/archive.svg', keywords: 'resource review shenhe' },
      { path: '/teacher/galaxy-forge', label: '星系锻造', icon: '/icons/forge.svg', keywords: 'forge duanzao' },
      { path: '/teacher/gate-policy', label: '闸门策略', icon: '/icons/target.svg', keywords: 'gate policy zhamen' },
    ],
  },
  {
    label: '班级',
    items: [
      { path: '/teacher/students', label: '学生名册', icon: '/icons/students.svg', keywords: 'student roster mingce' },
      { path: '/teacher/groups', label: '学生分组', icon: '/icons/students.svg', keywords: 'group fenzu xiaozu' },
      { path: '/teacher/praise', label: '星光激励', icon: '/icons/growth.svg', keywords: 'praise jiangli jili badge' },
      { path: '/teacher/messages', label: '消息中心', icon: '/icons/messages.svg', keywords: 'message broadcast dm sixin xiaoxi' },
      { path: '/teacher/weekly-report', label: '教学周报', icon: '/icons/dashboard.svg', keywords: 'weekly report zhoubao' },
    ],
  },
];

export const teacherNavItems: TeacherNavItem[] = teacherNavGroups.flatMap((g) => g.items);
