import pytest
from era.adaptive.engine import AdaptiveEngine
from era.data.sample_questions import SAMPLE_QUESTIONS


def test_selector_does_not_repeat_questions():
    engine = AdaptiveEngine(SAMPLE_QUESTIONS)
    first = engine.next_question()
    assert first is not None
    engine.submit_response(first.question, first.question.correct_index)
    second = engine.next_question()
    assert second is not None
    assert second.question.question_id != first.question.question_id


def test_duplicate_response_is_rejected():
    engine = AdaptiveEngine(SAMPLE_QUESTIONS)
    selected = engine.next_question()
    engine.submit_response(selected.question, selected.question.correct_index)
    with pytest.raises(ValueError, match="already been attempted"):
        engine.submit_response(selected.question, selected.question.correct_index)


def test_exam_stops_at_maximum_length():
    engine = AdaptiveEngine(SAMPLE_QUESTIONS, min_calibration_items=2, max_calibration_items=3, max_exam_items=4)
    for _ in range(4):
        selected = engine.next_question()
        assert selected is not None
        engine.submit_response(selected.question, selected.question.correct_index)
    assert engine.next_question() is None


def test_repeated_next_question_does_not_duplicate_selection_event():
    engine = AdaptiveEngine(SAMPLE_QUESTIONS)
    first = engine.next_question()
    second = engine.next_question()
    assert first == second
    assert [event.event_type for event in engine.events].count("question_selected") == 1


def test_response_phase_reflects_phase_when_question_was_selected():
    engine = AdaptiveEngine(SAMPLE_QUESTIONS, min_calibration_items=2, max_calibration_items=3, max_exam_items=4)
    for expected_phase in ("calibration", "calibration", "calibration", "adaptive"):
        selection = engine.next_question()
        assert selection is not None
        engine.submit_response(selection.question, selection.question.correct_index)
        response_event = [e for e in engine.events if e.event_type == "response_recorded"][-1]
        assert response_event.details["phase"] == expected_phase


def test_response_must_match_pending_question():
    engine = AdaptiveEngine(SAMPLE_QUESTIONS)
    selection = engine.next_question()
    other = next(q for q in SAMPLE_QUESTIONS if q.question_id != selection.question.question_id)
    with pytest.raises(ValueError, match="does not match"):
        engine.submit_response(other, other.correct_index)
