from era.adaptive.engine import AdaptiveEngine
from era.data.sample_questions import SAMPLE_QUESTIONS
from era.trace.events import render_events


def main() -> None:
    engine = AdaptiveEngine(SAMPLE_QUESTIONS)
    print("ERA adaptive examination prototype")
    print("Synthetic question bank; this is a software demo, not a validated assessment.")
    print("Enter option number 1-4. Type 'q' to stop the demo.\n")

    while len(engine.attempted_ids) < engine.max_exam_items:
        selection = engine.next_question()
        if selection is None:
            break
        question = selection.question
        print(f"\n[{question.question_id}] {question.subject} / {question.topic}")
        print(question.text)
        for index, option in enumerate(question.options, start=1):
            print(f"  {index}. {option}")
        answer = input("Answer: ").strip().lower()
        if answer == "q":
            break
        if not answer.isdigit() or not 1 <= int(answer) <= len(question.options):
            print("Please enter a valid option number.")
            continue
        engine.submit_response(question, int(answer) - 1)
        print("Response recorded.")
        # Internal trace is shown only in this developer demonstration.
        print(f"[Trace] theta={engine.ability.theta:.3f}, posterior_sd={engine.ability.posterior_sd:.3f}")

    print("\nThank You")
    print("\n--- Developer trace ---")
    print(render_events(engine.events))


if __name__ == "__main__":
    main()
