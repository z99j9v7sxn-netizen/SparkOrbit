import { apiGet, apiPost } from './client';

export interface AppNotification {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string;
  is_read: boolean;
  created_at: string;
}

export const fetchNotifications = () => apiGet<AppNotification[]>('/api/notifications');
export const fetchUnreadCount = () => apiGet<{ count: number }>('/api/notifications/unread-count');
export const markNotificationRead = (id: string) => apiPost(`/api/notifications/${id}/read`, {});
export const markAllNotificationsRead = () => apiPost('/api/notifications/read-all', {});
