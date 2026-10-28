"""Convert the official JEEBench dataset JSON into ERA's supported single-answer MCQ schema.

Download/unzip the official JEEBench repository's data.zip and pass the extracted
`dataset.json` path to this script. This script intentionally skips multi-correct
and numerical-answer questions until ERA supports those response types.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

OPTION_MARKER = re.compile(r"(?<!\w)(?:\(([A-D])\)|([A-D])\s*[\).])\s*", re.IGNORECASE)


def parse_options(question_text: str) -> tuple[str, tuple[str, ...]] | None:
    matches = list(OPTION_MARKER.finditer(question_text))
    if len(matches) < 2:
        return None
    # Keep only a consecutive A, B, C, D option sequence. Avoid treating labels in prose as options.
    first = matches[0].start()
    markers = [(m.group(1) or m.group(2)).upper() for m in matches]
    if markers[:2] != ["A", "B"]:
        return None
    count = 1
    while count < min(4, len(markers)) and markers[count] == chr(ord("A") + count):
        count += 1
    if count < 2:
        return None
    option_matches = matches[:count]
    stem = question_text[:first].strip()
    option_texts = []
    for i, match in enumerate(option_matches):
        end = option_matches[i + 1].start() if i + 1 < len(option_matches) else len(question_text)
        option_texts.append(question_text[match.end():end].strip().strip(" ;\n"))
    stem = re.sub(r"\s+", " ", stem)
    option_texts = [re.sub(r"\s+", " ", x) for x in option_texts]
    if not stem or any(not x for x in option_texts):
        return None
    return stem, tuple(option_texts)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path, help="Path to JEEBench dataset.json")
    parser.add_argument("--output", type=Path, default=Path("data/jeebench_mcq.json"))
    parser.add_argument("--difficulty", choices=["neutral"], default="neutral", help="Imported questions get provisional difficulty 0.0; no calibration is claimed.")
    args = parser.parse_args()
    raw = json.loads(args.input.read_text(encoding="utf-8"))
    if isinstance(raw, dict):
        raw = raw.get("data", raw.get("questions", []))
    if not isinstance(raw, list):
        raise SystemExit("Expected a JSON list (or a data/questions list in a JSON object).")

    imported, skipped = [], {}
    for row in raw:
        qtype = str(row.get("type", "")).strip().lower()
        # Official JEEBench contains multiple response formats. Keep single-correct MCQs only.
        if qtype not in {"mcq", "single-correct mcq", "single correct mcq", "single_correct_mcq"}:
            skipped[qtype or "missing type"] = skipped.get(qtype or "missing type", 0) + 1
            continue
        gold = str(row.get("gold", "")).strip().upper()
        if gold not in {"A", "B", "C", "D"}:
            skipped["unsupported answer key"] = skipped.get("unsupported answer key", 0) + 1
            continue
        text = str(row.get("question", "")).strip()
        parsed = parse_options(text)
        if not parsed:
            skipped["could not parse options"] = skipped.get("could not parse options", 0) + 1
            continue
        stem, options = parsed
        if ord(gold) - ord("A") >= len(options):
            skipped["answer key outside parsed options"] = skipped.get("answer key outside parsed options", 0) + 1
            continue
        description = str(row.get("description", "JEE Advanced"))
        index = row.get("index", len(imported) + 1)
        subject_map = {"phy": "Physics", "chem": "Chemistry", "math": "Mathematics", "physics": "Physics", "chemistry": "Chemistry", "mathematics": "Mathematics"}
        subject = subject_map.get(str(row.get("subject", "")).lower(), str(row.get("subject", "Other")))
        safe_id = re.sub(r"[^A-Za-z0-9_-]+", "-", f"JEE-{description}-{index}").strip("-")
        imported.append({
            "question_id": safe_id,
            "subject": subject,
            "topic": description,
            "text": stem,
            "options": list(options),
            "correct_index": ord(gold) - ord("A"),
            "difficulty": 0.0,
            "synthetic": False,
            "source": "JEEBench / JEE Advanced",
            "source_paper": description,
            "source_index": index,
            "difficulty_status": "provisional_uncalibrated",
        })
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps({"questions": imported, "source": "JEEBench", "citation": "Arora et al., EMNLP 2023", "difficulty_note": "Difficulty 0.0 is a neutral placeholder, not a calibrated item parameter."}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Imported {len(imported)} single-answer MCQs to {args.output}")
    print(f"Skipped {sum(skipped.values())} rows: {skipped}")
    if not imported:
        raise SystemExit("No supported questions were imported. Inspect the source schema/options formatting before using this bank.")

if __name__ == "__main__":
    main()
