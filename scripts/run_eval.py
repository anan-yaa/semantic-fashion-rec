#!/usr/bin/env python3
"""Run hybrid/vector/keyword search against a ground-truth set and score them.

Usage:
    python -m scripts.run_eval --ground-truth evals/ground_truth/ground_truth_v1.json \
        --output-prefix evals/reports/report_$(date +%Y%m%d_%H%M%S) [--k 10] \
        [--use-query-understanding] [--throttle-seconds 4.5]
"""
import argparse
import logging
import sys
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.logging import setup_logging
from app.providers.factory import get_embedding_provider
from app.providers.llm_factory import get_llm_provider
from app.services.eval import load_ground_truth, run_and_save_eval

setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Run and score the search evaluation")
    parser.add_argument("--ground-truth", type=str, required=True, help="Path to ground truth JSON")
    parser.add_argument("--output-prefix", type=str, required=True, help="Path prefix for .json/.md reports")
    parser.add_argument("--k", type=int, default=10, help="Cutoff for NDCG/Precision")
    parser.add_argument(
        "--use-query-understanding",
        action="store_true",
        help="Route each query through the real LLM provider's query understanding "
        "(cleaned keyword query + inferred filters) before search, exactly as "
        "POST /search does. Makes real, billed LLM API calls. Omit for the "
        "original, query-understanding-free baseline behavior.",
    )
    parser.add_argument(
        "--throttle-seconds",
        type=float,
        default=None,
        help="When using --use-query-understanding, enforce a minimum interval "
        "(in seconds) between consecutive LLM API calls to stay under provider "
        "rate limits (e.g. Gemini free tier: 15 req/min = 4s minimum spacing). "
        "If not specified, no throttling is applied. Set to 4.5 to leave margin.",
    )
    args = parser.parse_args()

    # Validate throttle + understand_query compatibility
    if args.throttle_seconds is not None and not args.use_query_understanding:
        logger.error("--throttle-seconds requires --use-query-understanding")
        return 1

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        judgments = load_ground_truth(args.ground_truth)
        logger.info(f"Loaded {len(judgments)} judged queries from {args.ground_truth}")

        provider = get_embedding_provider(settings, use_fake=False)
        llm_provider = get_llm_provider(settings, use_fake=False) if args.use_query_understanding else None
        if llm_provider is not None:
            logger.info("Query understanding ENABLED for this eval run - making real LLM API calls")
        if args.throttle_seconds is not None:
            logger.info(f"Throttling: {args.throttle_seconds}s between consecutive LLM calls "
                       f"(~{len(judgments) / 15 * 60:.0f}s total for {len(judgments)} queries at 15 req/min)")

        report = run_and_save_eval(
            session,
            provider,
            judgments,
            ground_truth_source=args.ground_truth,
            output_prefix=args.output_prefix,
            k=args.k,
            llm_provider=llm_provider,
            throttle_seconds=args.throttle_seconds,
        )

        print("")
        print(f"Queries scored: {report.query_count} (excluded: {report.excluded_query_count})")
        print(f"Query understanding enabled: {report.query_understanding_enabled}")
        print("")
        print(f"{'Method':<10}{'NDCG@10':<12}{'Precision@10':<16}{'MRR':<10}")
        for method, scores in report.per_method.items():
            print(f"{method:<10}{scores.ndcg_at_10:<12.3f}{scores.precision_at_10:<16.3f}{scores.mrr:<10.3f}")
        print("")

        if report.query_understanding:
            fallback_count = sum(1 for r in report.query_understanding if not r.used_llm)
            print(f"Query understanding: {len(report.query_understanding)} calls, "
                  f"{fallback_count} real, {fallback_count} fell back to the original query")
            print("")

            # If any fallback occurred during a throttled run, fail loudly so the partial
            # run is never mistaken for a clean one.
            if fallback_count > 0 and args.throttle_seconds is not None:
                print("⚠️  WARNING: Throttled run had fallbacks (rate limits). Results are INCOMPLETE.", file=sys.stderr)
                logger.error(f"Throttled eval had {fallback_count} fallback(s) - results are incomplete")
                return 1

        logger.info(f"Reports written to {args.output_prefix}.json and {args.output_prefix}.md")
        return 0

    except Exception as e:
        logger.error(f"Eval run failed: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
