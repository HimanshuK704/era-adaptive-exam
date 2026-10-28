from dataclasses import dataclass
from era.models.entities import Question
from era.psychometrics.rasch import fisher_information


@dataclass(frozen=True)
class Selection:
    question: Question
    information: float
    reason: str


def select_next_question(
    questions: list[Question],
    theta: float,
    attempted_ids: set[str],
) -> Selection | None:
    candidates = [q for q in questions if q.question_id not in attempted_ids]
    if not candidates:
        return None
    scored = [(fisher_information(theta, q.difficulty), q) for q in candidates]
    # Stable tie-breaking by question ID makes runs reproducible.
    information, question = sorted(scored, key=lambda pair: (-pair[0], pair[1].question_id))[0]
    return Selection(
        question=question,
        information=information,
        reason="Highest Fisher information among eligible, unattempted questions.",
    )
