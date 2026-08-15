import { apiPost } from './client';

export interface SimilarQuestionItem {
  question: string;
  answer: string;
  explanation: string;
  difficulty: string;
}

export interface SimilarQuestionsResponse {
  source_question: string;
  items: SimilarQuestionItem[];
  fallback: boolean;
}

export interface GradeItemInput {
  question: string;
  reference_answer: string;
  student_answer: string;
}

export interface GradeItemResult {
  question: string;
  student_answer: string;
  score: number;
  is_correct: boolean;
  feedback: string;
  suggestion: string;
}

export interface GradeResponse {
  total_score: number;
  max_score: number;
  items: GradeItemResult[];
  summary: string;
  fallback: boolean;
}

export const generateSimilarQuestions = (source_question: string, count = 3, subject = '') =>
  apiPost<SimilarQuestionsResponse>('/api/ai/similar', { source_question, count, subject });

export const gradeAnswers = (items: GradeItemInput[]) =>
  apiPost<GradeResponse>('/api/ai/grade', { items });
