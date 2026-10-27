import type { QuizQuestion } from "./Quiz";

export interface MessageSource {
  original_filename: string;
  excerpt: string;
  page?: number | null;
}

export interface MessageQuiz {
  quiz_id: string;
  questions: QuizQuestion[];
}

export interface Message {
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: MessageSource[];
  agent?: string;
  quiz?: MessageQuiz;
}
