import { useState } from "react";
import { api } from "../services/api";
import type { QuizQuestion, QuizSummary } from "../types/Quiz";
import QuizCard from "./QuizCard";

interface QuizPanelProps {
  workspaceId: string | null;
  documentCount: number;
}

type Phase = "setup" | "loading" | "playing" | "done";

export default function QuizPanel({ workspaceId, documentCount }: QuizPanelProps) {
  const [phase, setPhase] = useState<Phase>("setup");
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">(
    "medium",
  );
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [activeQuizId, setActiveQuizId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  // History
  const [history, setHistory] = useState<QuizSummary[]>([]);
  const [historyLoaded, setHistoryLoaded] = useState(false);

  const loadHistory = async (workspaceId: string) => {
    try {
      setHistory(await api.fetchQuizzes(workspaceId));
    } catch {
      setHistory([]);
    } finally {
      setHistoryLoaded(true);
    }
  };

  const startQuiz = async () => {
    if (workspaceId === null) {
      return;
    }
    setError(null);
    setPhase("loading");
    try {
      const result = await api.generateQuiz(
        workspaceId,
        numQuestions,
        difficulty,
      );
      setQuestions(result.questions);
      setActiveQuizId(result.quiz_id ?? null);
      setPhase("playing");
      void loadHistory(workspaceId);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The quiz could not be generated.",
      );
      setPhase("setup");
    }
  };

  const retakeSaved = async (quizId: string) => {
    setError(null);
    setPhase("loading");
    try {
      const detail = await api.getQuiz(quizId);
      setQuestions(detail.questions);
      setActiveQuizId(quizId);
      setPhase("playing");
    } catch {
      setError("Could not load that quiz.");
      setPhase("setup");
    }
  };

  const newQuiz = () => {
    setQuestions([]);
    setActiveQuizId(null);
    setPhase("setup");
  };

  if (workspaceId === null) {
    return (
      <p className="panel-muted">Select a workspace to generate a quiz.</p>
    );
  }

  if (phase === "setup" || phase === "loading") {
    return (
      <div>
        {documentCount === 0 && (
          <p className="panel-muted">
            Upload documents first — quizzes are generated from your uploaded
            content.
          </p>
        )}
        <div className="panel-section">
          <p className="panel-label">Number of questions ({numQuestions})</p>
          <input
            type="range"
            min={1}
            max={20}
            value={numQuestions}
            onChange={(e) => setNumQuestions(Number(e.target.value))}
            className="quiz-range"
          />
        </div>
        <div className="panel-section">
          <p className="panel-label">Difficulty</p>
          <select
            className="field field--select"
            value={difficulty}
            onChange={(e) =>
              setDifficulty(e.target.value as "easy" | "medium" | "hard")
            }
          >
            <option value="easy">Easy</option>
            <option value="medium">Medium</option>
            <option value="hard">Hard</option>
          </select>
        </div>
        {error && <p className="panel-muted quiz-error">{error}</p>}
        <button
          type="button"
          className="btn btn--primary"
          onClick={() => void startQuiz()}
          disabled={documentCount === 0 || phase === "loading"}
        >
          {phase === "loading" ? "Generating…" : "Generate Quiz"}
        </button>

        <div className="panel-section" style={{ marginTop: 20 }}>
          <p className="panel-label">Saved quizzes</p>
          {!historyLoaded && (
            <button
              type="button"
              className="btn btn--secondary"
              onClick={() => void loadHistory(workspaceId)}
            >
              Load history
            </button>
          )}
          {historyLoaded && history.length === 0 && (
            <p className="panel-muted">
              No saved quizzes yet — generated quizzes are kept here with your
              scores.
            </p>
          )}
          {history.map((quiz) => (
            <div key={quiz.id} className="document-entry">
              <div className="document-entry-info">
                <span className="document-entry-name">
                  {quiz.num_questions} questions · {quiz.difficulty}
                </span>
                <span className="document-entry-date">
                  {new Date(quiz.created_at).toLocaleDateString("en-US", {
                    month: "short",
                    day: "numeric",
                    year: "numeric",
                  })}
                  {quiz.attempts > 0 && (
                    <span className="match-badge match-badge--content">
                      best {quiz.best_score}/{quiz.num_questions} ·{" "}
                      {quiz.attempts}×
                    </span>
                  )}
                </span>
              </div>
              <div>
                <button
                  type="button"
                  className="btn btn--secondary btn--small"
                  onClick={() => void retakeSaved(quiz.id)}
                >
                  Retake
                </button>
                <button
                  type="button"
                  className="sidebar-icon-btn"
                  title="Delete quiz"
                  onClick={() =>
                    void api
                      .deleteQuiz(quiz.id)
                      .then(() => loadHistory(workspaceId))
                      .catch(() => undefined)
                  }
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  // playing / done are handled inside QuizCard (done included for onNewQuiz)
  return (
    <div>
      <QuizCard
        questions={questions}
        onComplete={(score, total) => {
          if (activeQuizId) {
            void api
              .recordQuizAttempt(activeQuizId, score, total)
              .then(() => loadHistory(workspaceId))
              .catch(() => undefined);
          }
          setPhase("done");
        }}
        onNewQuiz={newQuiz}
      />
      {phase === "done" && (
        <button
          type="button"
          className="btn btn--primary"
          onClick={newQuiz}
          style={{ marginTop: 8 }}
        >
          Start over
        </button>
      )}
    </div>
  );
}
