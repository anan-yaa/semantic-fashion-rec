#!/usr/bin/env python3
"""Interactive ground truth reviewer - approve or flip labels."""
import json
import sys
from pathlib import Path


def load_ground_truth(path: str) -> dict:
    """Load ground truth JSON file."""
    with open(path) as f:
        return json.load(f)


def save_ground_truth(path: str, data: dict):
    """Save ground truth JSON file."""
    with open(path, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"\n✅ Saved to {path}")


def display_query(query, idx: int, total: int):
    """Display a query with relevance labels."""
    print(f"\n{'='*80}")
    print(f"[{idx}/{total}] {query['query_id'].upper()}")
    print(f"Query: {query['query']}")
    print(f"{'='*80}\n")

    relevant_ids = set(query['relevant_product_ids'])

    print(f"{'#':<4} {'Label':<8} {'Product ID (first 8 chars)':<32}")
    print("-" * 80)

    for i, candidate in enumerate(query['all_candidates']):
        product_id = candidate['product_id']
        is_relevant = product_id in relevant_ids
        label = "✓" if is_relevant else "✗"

        print(f"{i+1:<4} {label:<8} {product_id[:8]:<32}")

    print(f"\n✓ Relevant: {len(relevant_ids)} | ✗ Non-relevant: {len(query['all_candidates']) - len(relevant_ids)}")


def flip_label(query, product_idx: int) -> bool:
    """Flip a product's relevance label."""
    if product_idx < 0 or product_idx >= len(query['all_candidates']):
        print("❌ Invalid product number (1-40)")
        return False

    candidate = query['all_candidates'][product_idx]
    product_id = candidate['product_id']
    relevant_ids = query['relevant_product_ids']

    if product_id in relevant_ids:
        relevant_ids.remove(product_id)
        candidate['human_flipped'] = not candidate.get('human_flipped', False)
        print(f"   → {product_id[:8]}... marked as ✗ non-relevant")
    else:
        relevant_ids.append(product_id)
        candidate['human_flipped'] = not candidate.get('human_flipped', False)
        print(f"   → {product_id[:8]}... marked as ✓ relevant")

    return True


def main():
    gt_path = Path("evals/ground_truth/ground_truth_v2_auto.json")

    if not gt_path.exists():
        print(f"❌ Ground truth file not found: {gt_path}")
        sys.exit(1)

    ground_truth = load_ground_truth(str(gt_path))
    judgments = ground_truth.get('judgments', [])

    print(f"\n📊 Loaded {len(judgments)} queries")
    print("💡 Just press ENTER to approve and move to next")
    print("   Or type a NUMBER (1-40) to flip that product's label")
    print("   Or type [save] to finish, or [quit] to exit without saving\n")

    idx = 0

    while True:
        query = judgments[idx]
        display_query(query, idx + 1, len(judgments))

        cmd = input("\n→ ").strip().lower()

        if cmd == '':
            # Just press enter = approve and move to next
            if idx < len(judgments) - 1:
                idx += 1
            else:
                print("✓ Reached last query. Type 'save' to finish reviewing.")

        elif cmd == 'p':
            if idx > 0:
                idx -= 1
            else:
                print("Already at first query")

        elif cmd.isdigit():
            product_num = int(cmd) - 1
            flip_label(query, product_num)

        elif cmd == 'stats':
            total_rel = sum(len(q['relevant_product_ids']) for q in judgments)
            total_products = sum(len(q['all_candidates']) for q in judgments)
            total_non_rel = total_products - total_rel
            print(f"\n📈 Overall Stats:")
            print(f"   Queries: {len(judgments)}")
            print(f"   ✓ Relevant products: {total_rel}")
            print(f"   ✗ Non-relevant products: {total_non_rel}")

        elif cmd == 'save':
            save_ground_truth(str(gt_path), ground_truth)
            print("💾 Ground truth saved. Ready to run eval!\n")
            break

        elif cmd == 'quit':
            print("Exiting without saving changes.")
            break

        else:
            print("Commands: [ENTER]=next, [p]=prev, [#]=flip product, [stats], [save], [quit]")


if __name__ == '__main__':
    main()
