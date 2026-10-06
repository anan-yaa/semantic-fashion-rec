#!/usr/bin/env python3
"""Measure product-embedding throughput (read-only: nothing is written to the database).

Embeds real product texts exactly as the sync does ("passage: " prefix, the
configured batch size) after one unmeasured warm-up batch.

Usage:
    PYTHONPATH=. python3 scripts/benchmark_embeddings.py --products 2000 --repeats 3 \\
        --output evals/reports/embedding_benchmark.json
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from statistics import median

from sqlalchemy import select

from app.db.database import get_session
from app.db.models.product import Product
from app.providers.factory import get_embedding_provider
from core.config import settings


def main() -> int:
    parser = argparse.ArgumentParser(description="Benchmark product embedding throughput")
    parser.add_argument("--products", type=int, default=2000)
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    session = next(get_session())
    try:
        texts = list(session.execute(
            select(Product.search_text).where(Product.search_text.is_not(None)).order_by(Product.id).limit(args.products)
        ).scalars())
        catalogue_size = session.query(Product).count()
    finally:
        session.close()

    provider = get_embedding_provider(settings, use_fake=False)
    provider.embed_passages(texts[: settings.embedding_batch_size])  # load model + warm up

    try:
        import torch
        device = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
        if torch.cuda.is_available():
            torch.cuda.reset_peak_memory_stats()
    except ImportError:
        torch, device = None, "cpu"

    rates = []
    for rep in range(args.repeats):
        start = time.perf_counter()
        provider.embed_passages(texts)
        if torch is not None and torch.cuda.is_available():
            torch.cuda.synchronize()
        elapsed = time.perf_counter() - start
        rates.append(len(texts) / elapsed)
        print(f"run {rep + 1}/{args.repeats}: {len(texts)} products in {elapsed:.1f}s = {rates[-1]:.0f} products/s", flush=True)

    rate = median(rates)
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "model": settings.embedding_model,
        "device": device,
        "batch_size": settings.embedding_batch_size,
        "products_per_run": len(texts),
        "runs_products_per_second": rates,
        "median_products_per_second": rate,
        "catalogue_size": catalogue_size,
        "projected_full_catalogue_seconds": catalogue_size / rate,
        "gpu_peak_memory_mb": (torch.cuda.max_memory_allocated() / 2**20)
        if torch is not None and torch.cuda.is_available() else None,
    }
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(f"median {rate:.0f} products/s; full catalogue ({catalogue_size}) ≈ {catalogue_size / rate / 60:.1f} min")
    return 0


if __name__ == "__main__":
    sys.exit(main())
