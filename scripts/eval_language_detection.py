#!/usr/bin/env python3
"""Score the query language detector on labelled queries (no LLM, database or embedding model needed).

Rows come from evals/queries/language_detection_v1.json (German, Italian, Portuguese, Arabic, Chinese,
Russian, and tricky English such as "kurta set" or "poncho"), plus the existing Hindi/Spanish/French
multilingual test queries and the English eval queries.

Usage:
    PYTHONPATH=. python3 scripts/eval_language_detection.py [--output evals/reports/language_detection.json]
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from app.services.query_understanding.language import detect_language

ROOT = Path(__file__).resolve().parents[1]
CODE_TO_LANGUAGE = {"hi": "Hindi", "es": "Spanish", "fr": "French"}


def load_rows() -> list[dict]:
    rows = [{**r, "set": "main"} for r in json.loads((ROOT / "evals/queries/language_detection_v1.json").read_text())["rows"]]
    rows += [{**r, "set": "holdout"} for r in
             json.loads((ROOT / "evals/queries/language_detection_holdout_v1.json").read_text())["rows"]]
    for row in json.loads((ROOT / "evals/reports/multilingual_experiment.json").read_text())["rows"]:
        rows.append({"query": row["query"], "language": CODE_TO_LANGUAGE[row["lang"]], "set": "main"})
    judgments = json.loads((ROOT / "evals/ground_truth/ground_truth_v2_real.json").read_text())["judgments"]
    rows += [{"query": j["query"], "language": "English", "set": "main"} for j in judgments if j["query"].isascii()]
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Score query language detection")
    parser.add_argument("--output", help="Write the results as JSON")
    args = parser.parse_args()

    rows = load_rows()
    per_language: dict[str, list[bool]] = defaultdict(list)
    confusion: Counter = Counter()
    errors = []
    for row in rows:
        predicted = detect_language(row["query"])
        ok = predicted == row["language"]
        per_language[row["language"]].append(ok)
        if not ok:
            confusion[(row["language"], predicted)] += 1
            errors.append({**row, "predicted": predicted})

    print(f"{'Language':<12}{'Queries':>8}{'Correct':>9}{'Accuracy':>10}")
    for language, results in sorted(per_language.items(), key=lambda kv: (kv[0] != "English", kv[0])):
        print(f"{language:<12}{len(results):>8}{sum(results):>9}{sum(results) / len(results):>10.1%}")
    total_ok = sum(sum(r) for r in per_language.values())
    print(f"{'All':<12}{len(rows):>8}{total_ok:>9}{total_ok / len(rows):>10.1%}")
    for name in ("main", "holdout"):
        subset = [r for r in rows if r["set"] == name]
        wrong = sum(1 for e in errors if e["set"] == name)
        print(f"  {name + ' set:':<14}{len(subset) - wrong}/{len(subset)} correct")
    if errors:
        print("\nMisdetected:")
        for e in errors:
            print(f"  [{e['language']} -> {e['predicted']}] ({e['set']}) {e['query']}")

    if args.output:
        Path(args.output).write_text(json.dumps({
            "total": len(rows), "correct": total_ok,
            "per_language": {l: {"queries": len(r), "correct": sum(r)} for l, r in per_language.items()},
            "errors": errors,
        }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
