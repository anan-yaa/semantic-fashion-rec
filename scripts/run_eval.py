#!/usr/bin/env python3
"""Run hybrid/vector/keyword search against a ground-truth set and score them.

Usage:
    python -m scripts.run_eval --ground-truth evals/ground_truth/ground_truth_v1.json \
        --output-prefix evals/reports/report_$(date +%Y%m%d_%H%M%S) [--k 10]
"""
import argparse
import logging
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.logging import setup_logging
from app.providers.factory import get_embedding_provider
from app.services.eval import load_ground_truth, run_and_save_eval

setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and score the search evaluation")
    parser.add_argument("--ground-truth", type=str, required=True, help="Path to ground truth JSON")
    parser.add_argument("--output-prefix", type=str, required=True, help="Path prefix for .json/.md reports")
    parser.add_argument("--k", type=int, default=10, help="Cutoff for NDCG/Precision")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        judgments = load_ground_truth(args.ground_truth)
        logger.info(f"Loaded {len(judgments)} judged queries from {args.ground_truth}")

        provider = get_embedding_provider(settings, use_fake=False)

        report = run_and_save_eval(
            session,
            provider,
            judgments,
            ground_truth_source=args.ground_truth,
            output_prefix=args.output_prefix,
            k=args.k,
        )

        print("")
        print(f"Queries scored: {report.query_count} (excluded: {report.excluded_query_count})")
        print("")
        print(f"{'Method':<10}{'NDCG@10':<12}{'Precision@10':<16}{'MRR':<10}")
        for method, scores in report.per_method.items():
            print(f"{method:<10}{scores.ndcg_at_10:<12.3f}{scores.precision_at_10:<16.3f}{scores.mrr:<10.3f}")
        print("")
        logger.info(f"Reports written to {args.output_prefix}.json and {args.output_prefix}.md")
        return 0

    except Exception as e:
        logger.error(f"Eval run failed: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
