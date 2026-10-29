import csv
import json
import math
import statistics
from collections import Counter
from pathlib import Path

INPUT = Path("data/ednet_behavior_features.csv")
REPORT_DIR = Path("reports")
REPORT_DIR.mkdir(exist_ok=True)

NUMERIC_FIELDS = [
    "event_count",
    "enter_events",
    "respond_events",
    "submit_events",
    "unique_response_items",
    "answer_revisions",
    "session_count_30min_gap",
    "observed_span_seconds",
    "total_session_seconds",
    "median_session_seconds",
    "median_inter_event_seconds",
    "median_session_gap_seconds",
]

with INPUT.open("r", encoding="utf-8-sig", newline="") as f:
    rows = list(csv.DictReader(f))

if not rows:
    raise SystemExit("No feature profiles found. Run ednet_features.py first.")

for row in rows:
    for field in NUMERIC_FIELDS:
        row[field] = float(row[field])

def describe(values):
    values = sorted(values)
    return {
        "count": len(values),
        "mean": round(statistics.mean(values), 3),
        "median": round(statistics.median(values), 3),
        "min": round(min(values), 3),
        "max": round(max(values), 3),
    }

def pearson(xs, ys):
    if len(xs) < 2:
        return None
    mx, my = statistics.mean(xs), statistics.mean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    denom = math.sqrt(sum(x*x for x in dx) * sum(y*y for y in dy))
    if denom == 0:
        return None
    return round(sum(x*y for x, y in zip(dx, dy)) / denom, 4)

summary = {
    "dataset": "EdNet-KT2",
    "profiles_analyzed": len(rows),
    "features": {},
    "source_event_counts": Counter(),
    "platform_event_counts": Counter(),
    "correlations": {},
    "limitations": [
        "EdNet-KT2 originates from TOEIC learning activity, not JEE Advanced.",
        "The analyzed profiles are a capped subset, not necessarily representative of all EdNet users.",
        "A 30-minute inactivity threshold is a heuristic for segmenting sessions.",
        "Session duration is elapsed time within inferred sessions, not verified active study time.",
        "Behavioral associations do not establish causation or predict JEE performance.",
    ],
}

for field in NUMERIC_FIELDS:
    summary["features"][field] = describe([r[field] for r in rows])

for row in rows:
    for field, counter_key in [
        ("source_distribution", "source_event_counts"),
        ("platform_distribution", "platform_event_counts"),
    ]:
        try:
            distribution = json.loads(row[field] or "{}")
            summary[counter_key].update({
                k: int(v) for k, v in distribution.items()
            })
        except (ValueError, TypeError):
            pass

for a, b in [
    ("event_count", "answer_revisions"),
    ("event_count", "unique_response_items"),
    ("session_count_30min_gap", "total_session_seconds"),
    ("median_inter_event_seconds", "answer_revisions"),
]:
    summary["correlations"][f"{a}__{b}"] = pearson(
        [r[a] for r in rows], [r[b] for r in rows]
    )

summary["source_event_counts"] = dict(summary["source_event_counts"])
summary["platform_event_counts"] = dict(summary["platform_event_counts"])

json_path = REPORT_DIR / "ednet_research_summary.json"
json_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

md = [
    "# ERA: EdNet Behavioral Feature Analysis",
    "",
    f"**Profiles analyzed:** {len(rows)}",
    "",
    "## Method",
    "",
    "Behavioral features were extracted from EdNet-KT2 event logs. "
    "Numeric features are summarized using count, mean, median, minimum, "
    "and maximum. Pearson correlations are descriptive associations only.",
    "",
    "## Descriptive statistics",
    "",
    "| Feature | Count | Mean | Median | Minimum | Maximum |",
    "|---|---:|---:|---:|---:|---:|",
]

for field, stats in summary["features"].items():
    md.append(
        f"| {field} | {stats['count']} | {stats['mean']} | "
        f"{stats['median']} | {stats['min']} | {stats['max']} |"
    )

md += [
    "",
    "## Exploratory correlations",
    "",
    "| Feature pair | Pearson correlation |",
    "|---|---:|",
]

for pair, value in summary["correlations"].items():
    md.append(f"| {pair.replace('__', ' vs ')} | {value} |")

md += [
    "",
    "## Event source counts",
    "",
    "| Source | Events across analyzed profiles |",
    "|---|---:|",
]

for source, count in sorted(summary["source_event_counts"].items()):
    md.append(f"| {source} | {count} |")

md += [
    "",
    "## Interpretation and limitations",
    "",
    "- These results describe recorded activity in the analyzed subset.",
    "- Event counts and response revisions can reflect different usage patterns; "
    "they are not direct measures of ability, effort, or intelligence.",
    "- Session boundaries depend on the chosen 30-minute inactivity heuristic.",
    "- EdNet-KT2 contains TOEIC-learning activity, not JEE Advanced responses. "
    "Its behavioral patterns must not be presented as validated JEE predictors.",
    "- ERA may use this analysis to motivate hypotheses for adaptive assessment, "
    "but any transfer to JEE requires validation on relevant data.",
    "",
    "## Reproducibility",
    "",
    f"Input: `{INPUT.as_posix()}`",
    f"Machine-readable output: `{json_path.as_posix()}`",
    "",
]

md_path = REPORT_DIR / "ednet_research_summary.md"
md_path.write_text("\n".join(md) + "\n", encoding="utf-8")

print(f"Profiles analyzed: {len(rows)}")
print(f"Markdown report: {md_path}")
print(f"JSON summary: {json_path}")
print("\nKey descriptive statistics:")
for field in [
    "event_count",
    "answer_revisions",
    "session_count_30min_gap",
    "total_session_seconds",
    "median_session_seconds",
]:
    print(f"  {field}: {summary['features'][field]}")
print("\nExploratory correlations:")
for pair, value in summary["correlations"].items():
    print(f"  {pair}: {value}")
