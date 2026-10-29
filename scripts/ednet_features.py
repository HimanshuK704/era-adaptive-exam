import argparse
import csv
import io
import json
import statistics
import zipfile
from collections import Counter, defaultdict
from pathlib import Path

def extract_features(stream):
    reader = csv.DictReader(io.TextIOWrapper(stream, encoding="utf-8-sig"))
    required = {
        "timestamp", "action_type", "item_id",
        "source", "user_answer", "platform"
    }
    if not required.issubset(reader.fieldnames or []):
        raise ValueError(f"Unexpected CSV columns: {reader.fieldnames}")

    events = []
    invalid_timestamps = 0

    for row in reader:
        try:
            timestamp = int(row["timestamp"])
        except (ValueError, TypeError):
            invalid_timestamps += 1
            continue

        events.append({
            **row,
            "ts": timestamp / 1000.0,
        })

    events.sort(key=lambda event: event["ts"])
    actions = Counter(e["action_type"] for e in events)
    platforms = Counter(e["platform"] for e in events if e["platform"])
    sources = Counter(e["source"] for e in events if e["source"])

    # Consecutive answer changes on the same item.
    previous_answers = {}
    answer_revisions = 0
    response_items = set()

    for event in events:
        if event["action_type"] != "respond":
            continue

        item = event["item_id"]
        answer = event["user_answer"]
        response_items.add(item)

        if item in previous_answers and answer != previous_answers[item]:
            answer_revisions += 1

        previous_answers[item] = answer

    # Split event sequences into sessions using a 30-minute inactivity threshold.
    intervals = []
    session_gaps = []
    session_durations = []
    sessions = 0
    previous_ts = None
    session_start = None
    session_end = None

    for event in events:
        ts = event["ts"]

        if previous_ts is None:
            sessions = 1
            session_start = ts
            session_end = ts
        else:
            gap = ts - previous_ts
            if gap >= 1800:
                session_durations.append(session_end - session_start)
                session_gaps.append(gap)
                sessions += 1
                session_start = ts
                session_end = ts
            else:
                intervals.append(gap)
                session_end = ts

        previous_ts = ts

    if session_start is not None:
        session_durations.append(session_end - session_start)

    def median_or_zero(values):
        return round(statistics.median(values), 3) if values else 0.0

    total_session_seconds = sum(session_durations)
    median_session_seconds = (
        round(statistics.median(session_durations), 3)
        if session_durations else 0.0
    )

    return {
        "event_count": len(events),
        "invalid_timestamps": invalid_timestamps,
        "enter_events": actions["enter"],
        "respond_events": actions["respond"],
        "submit_events": actions["submit"],
        "other_events": sum(
            count for action, count in actions.items()
            if action not in {"enter", "respond", "submit"}
        ),
        "unique_response_items": len(response_items),
        "answer_revisions": answer_revisions,
        "session_count_30min_gap": sessions,
        "observed_span_seconds": round(
            events[-1]["ts"] - events[0]["ts"], 3
        ) if len(events) >= 2 else 0.0,
        "total_session_seconds": round(total_session_seconds, 3),
        "median_session_seconds": median_session_seconds,
        "median_inter_event_seconds": median_or_zero(intervals),
        "median_session_gap_seconds": median_or_zero(session_gaps),
        "platform_distribution": json.dumps(dict(platforms), ensure_ascii=False),
        "source_distribution": json.dumps(dict(sources), ensure_ascii=False),
    }

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--zip", default="external/ednet-kt2.zip")
    parser.add_argument("--max-students", type=int, default=100)
    parser.add_argument("--output", default="data/ednet_behavior_features.csv")
    args = parser.parse_args()

    archive = Path(args.zip)
    output = Path(args.output)

    if args.max_students < 1:
        parser.error("--max-students must be at least 1")

    output.parent.mkdir(parents=True, exist_ok=True)
    rows = []
    errors = []

    with zipfile.ZipFile(archive) as z:
        names = sorted(
            name for name in z.namelist()
            if name.startswith("KT2/")
            and name.endswith(".csv")
            and "/._" not in name
        )[:args.max_students]

        print(f"Processing {len(names)} student files from archive")

        for index, name in enumerate(names, 1):
            try:
                with z.open(name) as stream:
                    features = extract_features(stream)
                features["student_file"] = Path(name).stem
                rows.append(features)
            except Exception as exc:
                errors.append({"student_file": name, "error": str(exc)})

            if index % 25 == 0:
                print(f"Processed {index}/{len(names)}")

    if rows:
        fieldnames = ["student_file"] + [
            key for key in rows[0] if key != "student_file"
        ]
        with output.open("w", newline="", encoding="utf-8-sig") as handle:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)

    print(f"\nSuccessful profiles: {len(rows)}")
    print(f"Failed files: {len(errors)}")
    print(f"Output: {output}")
    if rows:
        print("\nFirst profile:")
        print(json.dumps(rows[0], indent=2, ensure_ascii=False))
    if errors:
        print("\nFirst errors:")
        print(json.dumps(errors[:3], indent=2))

if __name__ == "__main__":
    main()
