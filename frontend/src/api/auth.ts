import { apiGet, apiPost, apiPostForm } from './client';
import type { AuthUser, UserRole } from '../stores/auth';

interface AuthPayload {
  access_token: string;
  token_type: string;
  user: {
    id: string;
    username: string;
    role: UserRole;
    display_name: string;
    avatar?: string;
    avatar_cartoon_url?: string;
    class_id?: string;
    teacher_id?: string;
    pet_slug?: string;
    pet_affinity?: number;
    equipped_title?: string;
    study_theme?: string;
  };
}

export interface TeacherBrief {
  id: string;
  username: string;
  display_name: string;
}

export interface ClassBrief {
  id: string;
  name: string;
  teacher_id: string;
  teacher_name: string;
  invite_code: string;
}

export async function login(username: string, password: string, role: UserRole) {
  return apiPost<AuthPayload>('/api/auth/login', { username, password, role });
}

export async function preflightAuth(username: string, role: UserRole) {
  return apiPost<{ ok: boolean; message: string }>('/api/auth/preflight', { username, role });
}

export async function checkUsername(username: string) {
  return apiPost<{ available: boolean; message: string }>('/api/auth/check-username', { username });
}

export async function register(form: FormData) {
  return apiPostForm<AuthPayload>('/api/auth/register', form);
}

export async function fetchTeachers() {
  return apiGet<TeacherBrief[]>('/api/teachers');
}

export async function fetchClasses() {
  return apiGet<ClassBrief[]>('/api/classes');
}

export function toAuthUser(user: AuthPayload['user']): AuthUser {
  return {
    id: user.id,
    username: user.username,
    role: user.role,
    displayName: user.display_name,
    avatar: user.avatar_cartoon_url || user.avatar,
    classId: user.class_id,
    teacherId: user.teacher_id,
    petSlug: user.pet_slug,
    petAffinity: user.pet_affinity,
    equippedTitle: user.equipped_title,
    studyTheme: user.study_theme,
  };
}
