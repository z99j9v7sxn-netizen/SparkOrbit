import { apiDelete, apiGet, apiPost } from './client';

export interface ChatRoom {
  id: string;
  room_type: string;
  title: string;
  class_id: string;
  created_by?: string;
  last_message: string;
}

export interface ChatReaction {
  emoji: string;
  count: number;
  reacted_by_me: boolean;
}

export interface ChatMessage {
  id: string;
  room_id: string;
  sender_id: string;
  sender_name: string;
  sender_avatar?: string;
  content: string;
  created_at: string;
  reactions?: ChatReaction[];
}

export const fetchChatRooms = () => apiGet<ChatRoom[]>('/api/chat/rooms');
export const fetchChatMessages = (roomId: string) => apiGet<ChatMessage[]>(`/api/chat/rooms/${roomId}/messages`);
export const sendChatMessage = (roomId: string, content: string) =>
  apiPost<ChatMessage>(`/api/chat/rooms/${roomId}/messages`, { content });
export const createPrivateChat = (targetUserId: string) =>
  apiPost<ChatRoom>('/api/chat/private', { target_user_id: targetUserId });
export const createTopicRoom = (title: string) => apiPost<ChatRoom>('/api/chat/topics', { title });
export const deleteTopicRoom = (roomId: string) => apiDelete<{ ok: boolean }>(`/api/chat/topics/${roomId}`);
export const createGroupChat = (title: string, member_ids: string[]) =>
  apiPost<ChatRoom>('/api/chat/groups', { title, member_ids });
export const inviteToGroup = (roomId: string, targetUserId: string) =>
  apiPost(`/api/chat/groups/${roomId}/invite`, { target_user_id: targetUserId });
export const toggleMessageReaction = (messageId: string, emoji: string) =>
  apiPost<ChatReaction[]>(`/api/chat/messages/${messageId}/reactions`, { emoji });
export const fetchChatSummary = (roomId: string) =>
  apiGet<{ summary: string; message_count: number }>(`/api/chat/rooms/${roomId}/summary`);
export const fetchClassmates = () => apiGet<{ id: string; username: string; display_name: string; avatar?: string }[]>('/api/chat/classmates');

export function chatWsUrl(roomId: string): string {
  const proto = window.location.protocol === 'https:' ? 'wss' : 'ws';
  return `${proto}://${window.location.host}/api/ws/chat/${roomId}`;
}
