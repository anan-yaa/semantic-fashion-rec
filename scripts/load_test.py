#!/usr/bin/env python3
"""Load-test POST /search with the eval query mix.

Reports latency percentiles, throughput, error rate, LLM fallback rate and the
per-stage server timings (Server-Timing header) at each concurrency level.
Run against a backend started with RATE_LIMIT_ENABLED=false, or most requests
will be rejected with 429.

Usage:
    PYTHONPATH=. python3 scripts/load_test.py --label with_llm \\
        --concurrency 1 4 8 --requests 200 --repeats 3 \\
        --output evals/reports/load_with_llm.json [--backend-pid PID]
"""
import argparse
import json
import random
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

import httpx

from app.services.eval.system_health import RequestResult, median_of_runs, parse_server_timing, summarize

QUERY_SET = "evals/queries/query_set_v1.json"
MEDIAN_PATHS = [
    ["latency_ms", "p50"], ["latency_ms", "p95"], ["latency_ms", "p99"], ["latency_ms", "max"],
    ["throughput_rps"], ["error_rate"], ["llm_used_rate"],
] + [["stages_ms", stage, p] for stage in ("llm", "embed", "vector_db", "keyword_db", "types", "facets", "total") for p in ("p50", "p95")]


def one_request(client: httpx.Client, url: str, query: str, method: str) -> RequestResult:
    start = time.perf_counter()
    try:
        response = client.post(url, json={"query": query, "method": method, "limit": 24})
    except httpx.HTTPError as e:
        return RequestResult(status=None, latency_ms=(time.perf_counter() - start) * 1000, error=type(e).__name__)
    latency_ms = (time.perf_counter() - start) * 1000
    result = RequestResult(status=response.status_code, latency_ms=latency_ms,
                           stages=parse_server_timing(response.headers.get("server-timing")))
    if result.ok:
        understanding = response.json().get("understanding")
        if understanding is not None:
            result.used_llm = understanding["used_llm"]
            result.fallback_reason = understanding["fallback_reason"]
    return result


def rss_mb(pid: int) -> float:
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) / 1024
    return 0.0


def run_level(base_url, queries, concurrency, n_requests, method, seed, timeout, backend_pid):
    picks = random.Random(seed).choices(queries, k=n_requests)
    url = f"{base_url}/search"
    peak = {"rss_mb": 0.0}
    stop = threading.Event()

    def sample_memory():
        while not stop.is_set():
            peak["rss_mb"] = max(peak["rss_mb"], rss_mb(backend_pid))
            stop.wait(0.25)

    sampler = threading.Thread(target=sample_memory, daemon=True) if backend_pid else None
    if sampler:
        sampler.start()
    with httpx.Client(timeout=timeout) as client, ThreadPoolExecutor(max_workers=concurrency) as pool:
        start = time.perf_counter()
        results = list(pool.map(lambda q: one_request(client, url, q, method), picks))
        wall = time.perf_counter() - start
    stop.set()
    summary = summarize(results, wall)
    summary["wall_seconds"] = wall
    if sampler:
        summary["backend_peak_rss_mb"] = peak["rss_mb"]
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Load-test POST /search")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--concurrency", type=int, nargs="+", default=[1, 4, 8])
    parser.add_argument("--requests", type=int, default=200, help="Requests per concurrency level per repeat")
    parser.add_argument("--repeats", type=int, default=3)
    parser.add_argument("--warmup", type=int, default=20, help="Unmeasured requests sent first")
    parser.add_argument("--method", default="hybrid", choices=["hybrid", "vector", "keyword"])
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--backend-pid", type=int, default=None, help="Sample this process's RSS during the run")
    parser.add_argument("--label", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    queries = [q["query"] for q in json.loads(Path(QUERY_SET).read_text())["queries"]]

    with httpx.Client(timeout=args.timeout) as client:
        for q in random.Random(0).choices(queries, k=args.warmup):
            one_request(client, f"{args.base_url}/search", q, args.method)
    idle_rss = rss_mb(args.backend_pid) if args.backend_pid else None

    levels = {}
    for concurrency in args.concurrency:
        runs = []
        for rep in range(args.repeats):
            run = run_level(args.base_url, queries, concurrency, args.requests, args.method,
                            args.seed + rep, args.timeout, args.backend_pid)
            runs.append(run)
            lat = run["latency_ms"]
            print(f"[{args.label}] c={concurrency} run {rep + 1}/{args.repeats}: "
                  f"p50={lat.get('p50', 0):.0f}ms p95={lat.get('p95', 0):.0f}ms p99={lat.get('p99', 0):.0f}ms "
                  f"{run['throughput_rps']:.2f} req/s errors={run['error_rate']:.1%}", flush=True)
        levels[str(concurrency)] = {"runs": runs, "median": median_of_runs(runs, MEDIAN_PATHS)}

    commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True, text=True).stdout.strip()
    report = {
        "label": args.label,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "commit": commit,
        "config": {k: v for k, v in vars(args).items() if k not in ("output",)},
        "backend_idle_rss_mb": idle_rss,
        "levels": levels,
    }
    Path(args.output).write_text(json.dumps(report, indent=2))
    print(f"Wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
