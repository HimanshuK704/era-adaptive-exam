from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Question:
    question_id: str
    subject: str
    topic: str
    text: str
    options: tuple[str, ...]
    correct_index: int
    difficulty: float
    synthetic: bool = True

    def __post_init__(self) -> None:
        if not self.question_id.strip():
            raise ValueError("question_id must not be empty")
        if len(self.options) < 2:
            raise ValueError("a question must have at least two options")
        if not 0 <= self.correct_index < len(self.options):
            raise ValueError("correct_index is outside the options")


@dataclass
class AbilityState:
    theta: float = 0.0
    posterior_sd: float = 1.0
    responses: int = 0


@dataclass
class ExamSession:
    session_id: str
    attempted_question_ids: set[str] = field(default_factory=set)
    response_count: int = 0
    complete: bool = False


@dataclass(frozen=True)
class DecisionEvent:
    event_type: str
    details: dict[str, Any]
