import { apiGet, apiPost } from './client';

export interface MyFeedbackItem {
  id: string;
  category: string;
  content: string;
  status: string;
  reply: string;
  created_at: string;
  updated_at: string;
}

export const submitFeedback = (category: string, content: string) =>
  apiPost<MyFeedbackItem>('/api/feedback', { category, content });

export const fetchMyFeedback = () => apiGet<MyFeedbackItem[]>('/api/feedback/mine');
