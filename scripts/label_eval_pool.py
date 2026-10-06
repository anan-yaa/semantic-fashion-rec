#!/usr/bin/env python3
"""Interactive CLI: review/correct pre-labels on a pool to produce ground truth.

Shows each pooled candidate's product attributes and (if present) the
pre-label + rationale - never which search method(s) found it, so the
human judgment stays attribute-driven, same as the pre-labeling step.

Progress is saved incrementally to <output>.partial (same JSON shape as a
dict of {query_id: {product_id: relevance}}), so Ctrl-C / [q]uit never
loses work; --resume picks up at the first undecided candidate.

Usage:
    python -m scripts.label_eval_pool --pool evals/pools/pool_v1.json \
        --output evals/ground_truth/ground_truth_v1.json [--resume]
"""
import argparse
import json
import os
import sys
from datetime import datetime, timezone

from app.services.eval import (
    GroundTruthCandidate,
    GroundTruthEntry,
    load_pool,
    save_ground_truth,
)


def load_progress(partial_path: str) -> dict:
    if os.path.exists(partial_path):
        with open(partial_path) as f:
            return json.load(f)
    return {}


def save_progress(partial_path: str, progress: dict) -> None:
    with open(partial_path, "w") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)


def prompt_candidate(query: str, idx: int, total: int, candidate) -> str:
    """Returns 'accept' / 'flip' / 'relevant' / 'not_relevant' / 'skip' / 'quit'."""
    print(f"\nQuery: {query!r}  (candidate {idx}/{total})")
    print(f"  Product: {candidate.name}")
    print(
        f"  category={candidate.category} subcategory={candidate.subcategory} "
        f"gender={candidate.gender} color={candidate.color} season={candidate.season}"
    )
    if candidate.search_text:
        print(f"  search_text: {candidate.search_text}")

    if candidate.pre_label is not None:
        label_str = "RELEVANT" if candidate.pre_label == 1 else "NOT RELEVANT"
        print(f"  Pre-label: {label_str}" + (f"  (rationale: {candidate.pre_label_rationale})" if candidate.pre_label_rationale else ""))
        prompt = "  [Enter]=accept  [f]=flip  [s]=skip  [q]=quit & save > "
    else:
        print("  Pre-label: (none)")
        prompt = "  [y]=relevant  [n]=not relevant  [s]=skip  [q]=quit & save > "

    while True:
        choice = input(prompt).strip().lower()
        if candidate.pre_label is not None:
            if choice == "":
                return "accept"
            if choice == "f":
                return "flip"
        else:
            if choice == "y":
                return "relevant"
            if choice == "n":
                return "not_relevant"
        if choice == "s":
            return "skip"
        if choice == "q":
            return "quit"
        print("  Invalid input, try again.")


def main() -> int:
    parser = argparse.ArgumentParser(description="Interactively label an eval pool")
    parser.add_argument("--pool", type=str, required=True, help="Path to pool JSON")
    parser.add_argument("--output", type=str, required=True, help="Path to write ground truth JSON")
    parser.add_argument("--resume", action="store_true", help="Resume from a .partial progress file")
    args = parser.parse_args()

    pools = load_pool(args.pool)
    partial_path = f"{args.output}.partial"
    progress = load_progress(partial_path) if args.resume else {}

    total_candidates = sum(len(p.candidates) for p in pools)
    done_count = sum(len(v) for v in progress.values())
    print(f"Loaded {len(pools)} queries, {total_candidates} total candidates.")
    if done_count:
        print(f"Resuming: {done_count} already decided.")

    quit_requested = False
    for pool_entry in pools:
        query_progress = progress.setdefault(pool_entry.query_id, {})
        for idx, candidate in enumerate(pool_entry.candidates, start=1):
            if candidate.product_id in query_progress:
                continue  # already decided (from --resume)

            action = prompt_candidate(pool_entry.query, idx, len(pool_entry.candidates), candidate)

            if action == "quit":
                quit_requested = True
                break
            elif action == "skip":
                continue
            elif action == "accept":
                query_progress[candidate.product_id] = candidate.pre_label
            elif action == "flip":
                query_progress[candidate.product_id] = 1 - candidate.pre_label
            elif action == "relevant":
                query_progress[candidate.product_id] = 1
            elif action == "not_relevant":
                query_progress[candidate.product_id] = 0

            save_progress(partial_path, progress)

        if quit_requested:
            break

    if quit_requested:
        print(f"\nProgress saved to {partial_path}. Re-run with --resume to continue.")
        return 0

    # Check everything is decided (nothing skipped-and-never-returned-to).
    incomplete = []
    for pool_entry in pools:
        query_progress = progress.get(pool_entry.query_id, {})
        for candidate in pool_entry.candidates:
            if candidate.product_id not in query_progress:
                incomplete.append((pool_entry.query_id, candidate.product_id))

    if incomplete:
        print(f"\n{len(incomplete)} candidates still undecided (skipped). Re-run with --resume to finish them.")
        print(f"Progress saved to {partial_path}.")
        return 0

    # Build final ground truth.
    judgments = []
    for pool_entry in pools:
        query_progress = progress[pool_entry.query_id]
        all_candidates = []
        relevant_ids = []
        for candidate in pool_entry.candidates:
            relevance = query_progress[candidate.product_id]
            human_flipped = candidate.pre_label is not None and relevance != candidate.pre_label
            all_candidates.append(
                GroundTruthCandidate(
                    product_id=candidate.product_id,
                    relevance=relevance,
                    pre_label=candidate.pre_label,
                    human_flipped=human_flipped,
                )
            )
            if relevance == 1:
                relevant_ids.append(candidate.product_id)
        judgments.append(
            GroundTruthEntry(
                query_id=pool_entry.query_id,
                query=pool_entry.query,
                relevant_product_ids=relevant_ids,
                all_candidates=all_candidates,
            )
        )

    save_ground_truth(
        args.output, judgments, source_pool=args.pool, labeled_at=datetime.now(timezone.utc).isoformat()
    )
    print(f"\nAll {len(pools)} queries labeled. Ground truth written to {args.output}")

    if os.path.exists(partial_path):
        os.remove(partial_path)

    return 0


if __name__ == "__main__":
    sys.exit(main())
