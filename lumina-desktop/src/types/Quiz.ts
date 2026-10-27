export interface QuizQuestion {
  question: string;
  options: { A: string; B: string; C: string; D: string };
  correct: "A" | "B" | "C" | "D";
  explanation: string;
}

export interface QuizResult {
  questions: QuizQuestion[];
  quiz_id?: string;
}

export interface QuizSummary {
  id: string;
  workspace_id: string;
  difficulty: string;
  num_questions: number;
  created_at: string;
  best_score: number | null;
  last_score: number | null;
  attempts: number;
}

export interface QuizDetail extends QuizSummary {
  questions: QuizQuestion[];
}
