#!/usr/bin/env python3
"""Build a labeling pool: run all 3 search methods per query, union candidates.

Usage:
    python -m scripts.build_eval_pool --query-set evals/queries/query_set_v1.json \
        --output evals/pools/pool_v1.json [--k-per-method 20]
"""
import argparse
import logging
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from core.config import settings
from core.logging import setup_logging
from app.providers.factory import get_embedding_provider
from app.services.eval import build_and_save_pool, load_query_set

setup_logging()
logger = logging.getLogger(__name__)


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a search-eval labeling pool")
    parser.add_argument("--query-set", type=str, required=True, help="Path to query set JSON")
    parser.add_argument("--output", type=str, required=True, help="Path to write the pool JSON")
    parser.add_argument("--k-per-method", type=int, default=20, help="Results per method per query")
    args = parser.parse_args()

    engine = create_engine(settings.database_url)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    session = SessionLocal()

    try:
        queries = load_query_set(args.query_set)
        logger.info(f"Loaded {len(queries)} queries from {args.query_set}")

        provider = get_embedding_provider(settings, use_fake=False)

        stats = build_and_save_pool(
            session,
            provider,
            queries,
            output_path=args.output,
            source_query_set=args.query_set,
            k_per_method=args.k_per_method,
        )

        logger.info(f"Pool built: {stats.query_count} queries, {stats.total_candidates} total candidates")
        logger.info(f"Elapsed: {stats.total_time_ms:.0f}ms")
        logger.info(f"Written to {args.output}")
        return 0

    except Exception as e:
        logger.error(f"Pool build failed: {e}", exc_info=True)
        return 1
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
