from dataclasses import dataclass, field
from era.adaptive.selector import Selection, select_next_question
from era.models.entities import AbilityState, DecisionEvent, Question
from era.psychometrics.rasch import eap_update


@dataclass
class AdaptiveEngine:
    questions: list[Question]
    min_calibration_items: int = 4
    max_calibration_items: int = 6
    max_exam_items: int = 15
    diagnostic_items: int | None = None
    calibration_target_sd: float = 0.55
    ability: AbilityState = field(default_factory=AbilityState)
    attempted_ids: set[str] = field(default_factory=set)
    events: list[DecisionEvent] = field(default_factory=list)
    calibration_count: int = 0
    _pending_selection: Selection | None = field(default=None, init=False, repr=False)
    _pending_phase: str | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.diagnostic_items is not None:
            if self.diagnostic_items <= 0 or self.diagnostic_items >= self.max_exam_items:
                raise ValueError("diagnostic_items must be positive and less than max_exam_items")
        if self.min_calibration_items < 1:
            raise ValueError("min_calibration_items must be positive")
        if self.max_calibration_items < self.min_calibration_items:
            raise ValueError("max_calibration_items must be >= min_calibration_items")
        if self.max_exam_items < self.min_calibration_items:
            raise ValueError("max_exam_items must be >= min_calibration_items")
        if self.calibration_target_sd <= 0:
            raise ValueError("calibration_target_sd must be positive")
        if len({q.question_id for q in self.questions}) != len(self.questions):
            raise ValueError("question IDs must be unique")

    @property
    def stage(self) -> str:
        """High-level exam stage, separate from psychometric calibration."""
        if self.diagnostic_items is not None and self.ability.responses < self.diagnostic_items:
            return "diagnostic"
        return "main"

    @property
    def phase(self) -> str:
        """Phase for the next question. Calibration is bounded to min..max items."""
        count = self.ability.responses
        if count < self.min_calibration_items:
            return "calibration"
        if count < self.max_calibration_items and self.ability.posterior_sd > self.calibration_target_sd:
            return "calibration"
        return "adaptive"

    def next_question(self) -> Selection | None:
        # Calling next_question repeatedly while the student is considering an
        # answer must not create duplicate selection events.
        if self._pending_selection is not None:
            return self._pending_selection
        if len(self.attempted_ids) >= self.max_exam_items:
            if not self.events or self.events[-1].event_type != "exam_stopped":
                self.events.append(DecisionEvent("exam_stopped", {"reason": "maximum_exam_length"}))
            return None
        selection = select_next_question(self.questions, self.ability.theta, self.attempted_ids)
        if selection is None:
            if not self.events or self.events[-1].event_type != "exam_stopped":
                self.events.append(DecisionEvent("exam_stopped", {"reason": "no_eligible_questions"}))
            return None
        self._pending_selection = selection
        self._pending_phase = self.phase
        self.events.append(DecisionEvent("question_selected", {
            "question_id": selection.question.question_id,
            "theta": round(self.ability.theta, 4),
            "difficulty": selection.question.difficulty,
            "fisher_information": round(selection.information, 4),
            "phase": self._pending_phase,
            "reason": selection.reason,
        }))
        return selection

    def submit_response(self, question: Question, selected_index: int) -> AbilityState:
        if question.question_id in self.attempted_ids:
            raise ValueError("question has already been attempted in this session")
        if self._pending_selection is None:
            raise ValueError("no question is currently awaiting a response")
        if question.question_id != self._pending_selection.question.question_id:
            raise ValueError("response does not match the currently selected question")
        if not 0 <= selected_index < len(question.options):
            raise ValueError("selected_index is outside the options")
        if len(self.attempted_ids) >= self.max_exam_items:
            raise ValueError("maximum exam length has already been reached")

        correct = selected_index == question.correct_index
        old_theta = self.ability.theta
        new_theta, new_sd = eap_update(old_theta, self.ability.posterior_sd, question.difficulty, correct)
        self.attempted_ids.add(question.question_id)
        self.ability = AbilityState(theta=new_theta, posterior_sd=new_sd, responses=self.ability.responses + 1)
        if self._pending_phase == "calibration":
            self.calibration_count += 1
        self.events.append(DecisionEvent("response_recorded", {
            "question_id": question.question_id,
            "correct": correct,
            "previous_theta": round(old_theta, 4),
            "updated_theta": round(new_theta, 4),
            "posterior_sd": round(new_sd, 4),
            "response_count": self.ability.responses,
            "phase": self._pending_phase or "adaptive",
        }))
        self._pending_selection = None
        self._pending_phase = None
        return self.ability
