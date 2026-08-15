import { createRouter, createWebHistory } from 'vue-router';
import { useAuthStore } from '../stores/auth';
import LoginGateway from '../components/LoginGateway.vue';
import RegisterGateway from '../components/RegisterGateway.vue';
import StudentPortal from '../views/StudentPortal.vue';

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/', name: 'login', component: LoginGateway },
    { path: '/register', name: 'register', component: RegisterGateway },
    { path: '/student', name: 'student', component: StudentPortal, meta: { role: 'student' } },
    {
      path: '/teacher',
      component: () => import('../layouts/TeacherLayout.vue'),
      meta: { role: 'teacher' },
      children: [
        { path: '', redirect: '/teacher/dashboard' },
        {
          path: 'dashboard',
          name: 'teacher-dashboard',
          component: () => import('../components/teacher/TeacherDashboardPanel.vue'),
        },
        {
          path: 'assignments',
          name: 'teacher-assignments',
          component: () => import('../components/teacher/AssignmentPanel.vue'),
        },
        {
          path: 'improvement',
          name: 'teacher-improvement',
          component: () => import('../components/teacher/ImprovementReviewPanel.vue'),
        },
        {
          path: 'interview',
          name: 'teacher-interview',
          component: () => import('../components/teacher/InterviewReviewPanel.vue'),
        },
        {
          path: 'grades',
          name: 'teacher-grades',
          component: () => import('../components/teacher/GradebookPanel.vue'),
        },
        {
          path: 'attendance',
          name: 'teacher-attendance',
          component: () => import('../components/teacher/AttendancePanel.vue'),
        },
        {
          path: 'patrol',
          name: 'teacher-patrol',
          component: () => import('../components/teacher/PatrolPanel.vue'),
        },
        {
          path: 'messages',
          name: 'teacher-messages',
          component: () => import('../components/teacher/BroadcastPanel.vue'),
        },
        {
          path: 'knowledge',
          name: 'teacher-knowledge',
          component: () => import('../components/teacher/TeacherKnowledgePanel.vue'),
        },
        {
          path: 'insight',
          name: 'teacher-insight',
          component: () => import('../components/teacher/InsightPanel.vue'),
        },
        {
          path: 'analysis',
          name: 'teacher-analysis',
          component: () => import('../components/teacher/GradeAnalysisPanel.vue'),
        },
        {
          path: 'question-bank',
          name: 'teacher-question-bank',
          component: () => import('../components/teacher/QuestionBankPanel.vue'),
        },
        {
          path: 'agent-activity',
          name: 'teacher-agent-activity',
          component: () => import('../components/teacher/AgentActivityPanel.vue'),
        },
        {
          path: 'resource-review',
          name: 'teacher-resource-review',
          component: () => import('../components/teacher/ResourceReviewPanel.vue'),
        },
        {
          path: 'calendar',
          name: 'teacher-calendar',
          component: () => import('../components/teacher/CalendarPanel.vue'),
        },
        {
          path: 'groups',
          name: 'teacher-groups',
          component: () => import('../components/teacher/GroupsPanel.vue'),
        },
        {
          path: 'praise',
          name: 'teacher-praise',
          component: () => import('../components/teacher/PraisePanel.vue'),
        },
        {
          path: 'weekly-report',
          name: 'teacher-weekly-report',
          component: () => import('../components/teacher/WeeklyReportPanel.vue'),
        },
        {
          path: 'resources',
          redirect: '/teacher/knowledge',
        },
        {
          path: 'lesson-plan',
          redirect: '/teacher/knowledge',
        },
        {
          path: 'students',
          name: 'teacher-students',
          component: () => import('../components/teacher/StudentRosterPanel.vue'),
        },
        {
          path: 'students/:id',
          name: 'teacher-student',
          component: () => import('../views/StudentDetail.vue'),
        },
        {
          path: 'galaxy-forge',
          name: 'teacher-galaxy-forge',
          component: () => import('../components/teacher/GalaxyForgePanel.vue'),
        },
        {
          path: 'gate-policy',
          name: 'teacher-gate-policy',
          component: () => import('../components/teacher/GatePolicyPanel.vue'),
        },
      ],
    },
    {
      path: '/admin',
      component: () => import('../layouts/AdminLayout.vue'),
      meta: { role: 'admin' },
      children: [
        { path: '', name: 'admin-overview', component: () => import('../views/admin/AdminOverview.vue') },
        { path: 'users', name: 'admin-users', component: () => import('../views/admin/AdminUsers.vue') },
        { path: 'content', name: 'admin-content', component: () => import('../views/admin/AdminContent.vue') },
        { path: 'usage', name: 'admin-usage', component: () => import('../views/admin/AdminUsage.vue') },
        { path: 'agents', name: 'admin-agents', component: () => import('../views/admin/AdminAgents.vue') },
        { path: 'harness', name: 'admin-harness', component: () => import('../views/admin/AdminHarness.vue') },
        { path: 'errors', name: 'admin-errors', component: () => import('../views/admin/AdminErrors.vue') },
        { path: 'maintenance', name: 'admin-maintenance', component: () => import('../views/admin/AdminMaintenance.vue') },
        { path: 'audit', name: 'admin-audit', component: () => import('../views/admin/AdminAudit.vue') },
        { path: 'alerts', name: 'admin-alerts', component: () => import('../views/admin/AdminAlerts.vue') },
        { path: 'reports', name: 'admin-reports', component: () => import('../views/admin/AdminReports.vue') },
        { path: 'analytics', name: 'admin-analytics', component: () => import('../views/admin/AdminAnalytics.vue') },
        { path: 'settings', name: 'admin-settings', component: () => import('../views/admin/AdminSettings.vue') },
        { path: 'feedback', name: 'admin-feedback', component: () => import('../views/admin/AdminFeedback.vue') },
      ],
    },
  ],
});

router.beforeEach((to) => {
  const auth = useAuthStore();
  if (to.name === 'login' || to.name === 'register') {
    if (!auth.isLoggedIn) return true;
    if (auth.user?.role === 'student') return '/student';
    if (auth.user?.role === 'teacher') return '/teacher';
    return '/admin';
  }

  if (!auth.isLoggedIn) return '/';

  const requiredRole = [...to.matched].reverse().find((r) => r.meta.role)?.meta.role as string | undefined;
  if (requiredRole === 'student' && auth.user?.role !== 'student') {
    return auth.user?.role === 'teacher' ? '/teacher' : '/admin';
  }
  if (requiredRole === 'teacher' && auth.user?.role !== 'teacher') {
    return auth.user?.role === 'admin' ? '/admin' : '/student';
  }
  if (requiredRole === 'admin' && auth.user?.role !== 'admin') {
    return auth.user?.role === 'teacher' ? '/teacher' : '/student';
  }
  return true;
});

export default router;
