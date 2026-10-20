"""Quiz persistence: saved quizzes + attempt history."""

from __future__ import annotations

import json

from sqlalchemy.orm import Session

from db import crud
from db.models import Quiz
from db.schemas import QuizDetailOut, QuizOut


def save_quiz(
    db: Session, workspace_id: str, questions: list[dict], difficulty: str
) -> Quiz:
    return crud.create_quiz(
        db, workspace_id, json.dumps(questions), difficulty
    )


def list_quizzes(db: Session, workspace_id: str) -> list[QuizOut]:
    results: list[QuizOut] = []
    for quiz in crud.list_quizzes(db, workspace_id):
        questions = json.loads(quiz.questions_json)
        attempts = crud.list_attempts(db, quiz.id)
        scores = [a.score for a in attempts]
        results.append(
            QuizOut(
                id=quiz.id,
                workspace_id=quiz.workspace_id,
                difficulty=quiz.difficulty,
                num_questions=len(questions),
                created_at=quiz.created_at,
                best_score=max(scores) if scores else None,
                last_score=scores[0] if scores else None,
                attempts=len(attempts),
            )
        )
    return results


def get_quiz_detail(db: Session, quiz_id: str) -> QuizDetailOut | None:
    quiz = crud.get_quiz(db, quiz_id)
    if quiz is None:
        return None
    attempts = crud.list_attempts(db, quiz.id)
    scores = [a.score for a in attempts]
    return QuizDetailOut(
        id=quiz.id,
        workspace_id=quiz.workspace_id,
        difficulty=quiz.difficulty,
        created_at=quiz.created_at,
        questions=json.loads(quiz.questions_json),
        best_score=max(scores) if scores else None,
        last_score=scores[0] if scores else None,
        attempts=len(attempts),
    )


def record_attempt(
    db: Session, quiz_id: str, score: int, total: int
) -> QuizDetailOut | None:
    if crud.get_quiz(db, quiz_id) is None:
        return None
    crud.add_attempt(db, quiz_id, score, total)
    return get_quiz_detail(db, quiz_id)


def delete_quiz(db: Session, quiz_id: str) -> bool:
    return crud.delete_quiz(db, quiz_id)
