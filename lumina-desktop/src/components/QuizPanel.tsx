import { useState } from "react";
import { api } from "../services/api";
import type { QuizQuestion } from "../types/Quiz";

interface QuizPanelProps {
  workspaceId: string | null;
  documentCount: number;
}

type Phase = "setup" | "loading" | "playing" | "done";

type OptionKey = "A" | "B" | "C" | "D";
const OPTION_KEYS: OptionKey[] = ["A", "B", "C", "D"];

function shuffle<T>(arr: T[]): T[] {
  return [...arr].sort(() => Math.random() - 0.5);
}

export default function QuizPanel({ workspaceId, documentCount }: QuizPanelProps) {
  const [phase, setPhase] = useState<Phase>("setup");
  const [numQuestions, setNumQuestions] = useState(5);
  const [difficulty, setDifficulty] = useState<"easy" | "medium" | "hard">(
    "medium",
  );
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<OptionKey | null>(null);
  const [score, setScore] = useState(0);
  const [error, setError] = useState<string | null>(null);

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
      setIndex(0);
      setPicked(null);
      setScore(0);
      setPhase("playing");
    } catch (e) {
      setError(
        e instanceof Error ? e.message : "The quiz could not be generated.",
      );
      setPhase("setup");
    }
  };

  const retake = () => {
    setQuestions((q) => shuffle(q));
    setIndex(0);
    setPicked(null);
    setScore(0);
    setPhase("playing");
  };

  const newQuiz = () => {
    setQuestions([]);
    setIndex(0);
    setPicked(null);
    setScore(0);
    setPhase("setup");
  };

  const handlePick = (key: OptionKey) => {
    if (picked !== null) {
      return;
    }
    setPicked(key);
    if (key === questions[index].correct) {
      setScore((s) => s + 1);
    }
  };

  const next = () => {
    if (index + 1 < questions.length) {
      setIndex((i) => i + 1);
      setPicked(null);
    } else {
      setPhase("done");
    }
  };

  if (workspaceId === null) {
    return (
      <p className="panel-muted">Select a workspace to generate a quiz.</p>
    );
  }

  if (phase === "setup") {
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
          disabled={documentCount === 0}
        >
          Generate Quiz
        </button>
      </div>
    );
  }

  if (phase === "loading") {
    return (
      <p className="panel-muted">
        Generating your quiz from this workspace's documents…
      </p>
    );
  }

  if (phase === "done") {
    return (
      <div>
        <p className="panel-label">Quiz complete</p>
        <p className="quiz-score">
          You got {score} / {questions.length} correct
        </p>
        <div className="workspace-row-line">
          <button type="button" className="btn btn--secondary" onClick={retake}>
            Retake
          </button>
          <button type="button" className="btn btn--primary" onClick={newQuiz}>
            New Quiz
          </button>
        </div>
      </div>
    );
  }

  // phase === "playing"
  const q = questions[index];
  return (
    <div>
      <p className="panel-label">
        Question {index + 1} of {questions.length}
      </p>
      <p className="quiz-question">{q.question}</p>
      <div className="quiz-options">
        {OPTION_KEYS.map((key) => {
          let cls = "quiz-option";
          if (picked !== null) {
            if (key === q.correct) {
              cls += " quiz-option--correct";
            } else if (key === picked) {
              cls += " quiz-option--wrong";
            }
          }
          return (
            <button
              key={key}
              type="button"
              className={cls}
              onClick={() => handlePick(key)}
              disabled={picked !== null}
            >
              <span className="quiz-option-key">{key}</span>
              <span className="quiz-option-text">{q.options[key]}</span>
            </button>
          );
        })}
      </div>
      {picked !== null && (
        <div>
          <p className="quiz-verdict">
            {picked === q.correct
              ? "Correct"
              : `Wrong — the correct answer is ${q.correct}`}
          </p>
          {q.explanation && (
            <p className="panel-muted quiz-explanation">{q.explanation}</p>
          )}
          <button type="button" className="btn btn--primary" onClick={next}>
            {index + 1 < questions.length ? "Next Question" : "See Results"}
          </button>
        </div>
      )}
    </div>
  );
}
