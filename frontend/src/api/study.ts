import { apiDelete, apiGet, apiPost, apiPostForm } from './client';

export interface StudyConstellation {
  slug: string;
  name: string;
  symbol: string;
  room_count: number;
  total_occupancy: number;
}

export interface StudyRoom {
  id: string;
  constellation: string;
  name: string;
  size: 'large' | 'small';
  capacity: number;
  occupancy: number;
  is_full: boolean;
}

export interface StudyOccupant {
  user_id: string;
  display_name: string;
  avatar: string;
  joined_at: string;
  status?: 'focus' | 'break' | 'help';
  focus_minutes?: number;
}

export interface StudyJoinResult {
  room: StudyRoom;
  occupants: StudyOccupant[];
}

export const fetchStudyConstellations = () => apiGet<StudyConstellation[]>('/api/study/constellations');
export const fetchStudyRooms = (constellation: string) =>
  apiGet<StudyRoom[]>(`/api/study/rooms?constellation=${encodeURIComponent(constellation)}`);
export const joinStudyRoom = (roomId: string) => apiPost<StudyJoinResult>(`/api/study/rooms/${roomId}/join`, {});
export const leaveStudyRoom = (roomId: string) => apiPost<{ status: string }>(`/api/study/rooms/${roomId}/leave`, {});
export const fetchStudyOccupants = (roomId: string) => apiGet<StudyOccupant[]>(`/api/study/rooms/${roomId}/occupants`);
export const updateStudyStatus = (roomId: string, status: 'focus' | 'break' | 'help') =>
  apiPost<{ status: string }>(`/api/study/rooms/${roomId}/status`, { status });
export const fetchClassStudyPresence = () => apiGet<Array<{ user_id: string; display_name: string; room_name: string; constellation: string }>>('/api/study/class-presence');

export const reportSupervisionEvent = (kind: 'phone' | 'away', message: string, room_id = '') =>
  apiPost<{ ok: boolean; alert_id: string; alert_type: string }>('/api/study/supervision-event', {
    kind,
    message,
    room_id,
  });

export const uploadSupervisionFrame = (file: Blob) => {
  const form = new FormData();
  form.append('file', file, 'frame.jpg');
  return apiPostForm<{
    user_id: string;
    display_name: string;
    frame_url: string;
    updated_at: string;
    room_id: string;
    status: string;
    online: boolean;
  }>('/api/study/supervision-frame', form);
};

export const clearSupervisionFrame = () =>
  apiDelete<{ ok: boolean }>('/api/study/supervision-frame');

export interface PatrolStudent {
  user_id: string;
  display_name: string;
  class_id?: string;
  class_name?: string;
  room_id: string;
  room_name: string;
  constellation: string;
  status: string;
  frame_url: string;
  updated_at: string;
  online: boolean;
}

export const fetchTeacherPatrol = (class_id = '') =>
  apiGet<PatrolStudent[]>(
    `/api/teacher/patrol${class_id ? `?class_id=${encodeURIComponent(class_id)}` : ''}`,
  );

export interface RoomPomodoro {
  active: boolean;
  room_id?: string;
  minutes?: number;
  started_by?: string;
  started_by_name?: string;
  started_at?: string;
  ends_at_ts?: number;
}

export const fetchRoomPomodoro = (roomId: string) =>
  apiGet<RoomPomodoro>(`/api/study/rooms/${roomId}/pomodoro`);

export const startRoomPomodoro = (roomId: string, minutes = 25) =>
  apiPost<RoomPomodoro & { ok: boolean }>(`/api/study/rooms/${roomId}/pomodoro`, {
    action: 'start',
    minutes,
  });

export const stopRoomPomodoro = (roomId: string) =>
  apiPost<{ ok: boolean }>(`/api/study/rooms/${roomId}/pomodoro`, { action: 'stop' });

export const inviteStudyBuddy = (buddyId: string) =>
  apiPost<{ ok: boolean; room_name: string }>('/api/study/invite-buddy', { buddy_id: buddyId });

export function studyWsUrl(roomId: string) {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/ws/study/${roomId}`;
}
