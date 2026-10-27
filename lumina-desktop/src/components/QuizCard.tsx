import { useState } from "react";
import type { QuizQuestion } from "../types/Quiz";

type OptionKey = "A" | "B" | "C" | "D";
const OPTION_KEYS: OptionKey[] = ["A", "B", "C", "D"];

function shuffle<T>(arr: T[]): T[] {
  return [...arr].sort(() => Math.random() - 0.5);
}

interface QuizCardProps {
  questions: QuizQuestion[];
  /** Called with the final score when the run completes */
  onComplete?: (score: number, total: number) => void;
  /** Offer retake / new-quiz controls inside the card */
  onNewQuiz?: () => void;
  compact?: boolean;
}

export default function QuizCard({
  questions,
  onComplete,
  onNewQuiz,
  compact = false,
}: QuizCardProps) {
  const [shuffled, setShuffled] = useState<QuizQuestion[]>(questions);
  const [index, setIndex] = useState(0);
  const [picked, setPicked] = useState<OptionKey | null>(null);
  const [score, setScore] = useState(0);
  const [done, setDone] = useState(false);

  const q = shuffled[index];

  const handlePick = (key: OptionKey) => {
    if (picked !== null) {
      return;
    }
    setPicked(key);
    if (key === q.correct) {
      setScore((s) => s + 1);
    }
  };

  const next = () => {
    if (index + 1 < shuffled.length) {
      setIndex((i) => i + 1);
      setPicked(null);
    } else {
      setDone(true);
      onComplete?.(score, shuffled.length);
    }
  };

  const retake = () => {
    setShuffled((qs) => shuffle(qs));
    setIndex(0);
    setPicked(null);
    setScore(0);
    setDone(false);
  };

  if (done) {
    return (
      <div className="quiz-card quiz-card--done">
        <p className="quiz-score">
          You got {score} / {shuffled.length} correct
        </p>
        <div className="workspace-row-line">
          <button type="button" className="btn btn--secondary" onClick={retake}>
            Retake
          </button>
          {onNewQuiz && (
            <button
              type="button"
              className="btn btn--primary"
              onClick={onNewQuiz}
            >
              New Quiz
            </button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={compact ? "quiz-card quiz-card--compact" : "quiz-card"}>
      <p className="panel-label">
        Question {index + 1} of {shuffled.length}
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
            {index + 1 < shuffled.length ? "Next Question" : "See Results"}
          </button>
        </div>
      )}
    </div>
  );
}
