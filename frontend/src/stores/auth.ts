import { defineStore } from 'pinia';
import { computed, ref } from 'vue';

export type UserRole = 'student' | 'teacher' | 'admin';

export interface AuthUser {
  id: string;
  username: string;
  role: UserRole;
  displayName: string;
  avatar?: string;
  classId?: string;
  teacherId?: string;
  petSlug?: string;
  petAffinity?: number;
  equippedTitle?: string;
  studyTheme?: string;
}

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('sparkorbit_token') ?? '');
  const user = ref<AuthUser | null>(
    localStorage.getItem('sparkorbit_user') ? JSON.parse(localStorage.getItem('sparkorbit_user') as string) : null,
  );

  const isLoggedIn = computed(() => Boolean(token.value && user.value));

  function setAuth(nextToken: string, nextUser: AuthUser) {
    token.value = nextToken;
    user.value = nextUser;
    localStorage.setItem('sparkorbit_token', nextToken);
    localStorage.setItem('sparkorbit_user', JSON.stringify(nextUser));
  }

  function logout() {
    token.value = '';
    user.value = null;
    localStorage.removeItem('sparkorbit_token');
    localStorage.removeItem('sparkorbit_user');
  }

  function switchRole(role: UserRole) {
    if (!user.value) return;
    user.value = { ...user.value, role };
    localStorage.setItem('sparkorbit_user', JSON.stringify(user.value));
  }

  return { token, user, isLoggedIn, setAuth, logout, switchRole };
});
