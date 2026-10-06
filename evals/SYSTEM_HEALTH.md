# System health and search quality

Measured 2026-10-06 on commit `c818e43` plus the uncommitted measurement changes (`Server-Timing` header, MRR@10 / Recall@10, load-test and benchmark scripts). Raw results are in [`reports/`](reports/) (`health_*` files).

## Summary

| Metric | Result |
|---|---|
| Search quality, Hybrid + TinyLlama (NDCG@10 / Recall@50) | 0.832 / 0.704 |
| Search latency p50 / p95 / p99, one user at a time | 502 ms / 825 ms / 1104 ms |
| Search latency p50 / p95 / p99, 8 concurrent requests | 2846 ms / 3430 ms / 3672 ms |
| Throughput, 8 concurrent requests | 3.1 searches/s |
| LLM latency p50 / p95 | 316 ms / 423 ms |
| Query embedding latency p50 / p95 | 19 ms / 37 ms |
| DB latency p50 (vector + keyword + type detection, sum of each stage's median) | 91 ms |
| Error rate under load | 0.0% (0 of 1800 requests) |
| Error rate while the LLM hangs | 0.0% (search falls back to plain search) |
| Embedding throughput | 144 products/s (NVIDIA GeForce GTX 1650); full catalogue ≈ 5.1 min |
| Successful ingestion rate | 100.0% (44,072 of 44,072 feed records) |
| Catalogue sync, no changes | 75 s |

Latencies are the median of 3 runs (one-at-a-time numbers come from the concurrency-1 runs). All are client-side wall time except the per-stage figures, which come from the server's `Server-Timing` header.

## Test conditions

- **Hardware:** NVIDIA GeForce GTX 1650, 4096 MiB; WSL2 with 3.7 GB RAM; 8 CPU cores.
- **Backend:** one uvicorn process; TinyLlama via Ollama on the GPU; multilingual-e5-base on the GPU; 44,072 products in PostgreSQL 15 + pgvector.
- **Settings:** rate limiting switched off for the load tests (otherwise most requests would get 429); everything else default (LLM timeout 8 s, circuit breaker 3 failures / 30 s).
- **Load:** the 80 eval queries (English, natural-language, vague and Hindi) in a fixed random order; 20 unmeasured warm-up requests; 200 measured requests per concurrency level; 3 repeats.
- Nothing else running on the machine apart from VS Code. Two single-request stalls (9.2 s and 12.4 s) appeared in individual runs, from system pauses rather than search; the medians of 3 runs absorb them.

---

## 1. Search quality

| System | NDCG@10 | MRR@10 | Precision@10 | Recall@10 | Recall@20 | Recall@50 |
|---|---|---|---|---|---|---|
| Vector | 0.923 | 0.925 | 0.841 | 0.421 | 0.713 | 0.719 |
| Keyword | 0.309 | 0.380 | 0.189 | 0.094 | 0.154 | 0.259 |
| Hybrid | 0.820 | 0.925 | 0.720 | 0.360 | 0.585 | 0.706 |
| **Hybrid + TinyLlama** (what the app runs) | 0.832 | 0.931 | 0.731 | 0.366 | 0.594 | 0.704 |

80 queries, answer key `ground_truth_v2_real.json` (20 relevant products per query). TinyLlama was used for 70 of 80 queries; the other 10 are Hindi queries, which skip the LLM by design.

- **Recall@10 can't exceed 0.5:** each query has 20 relevant products. Recall@20 is the first cutoff where 1.0 is possible.
- **The answer key favours vector search:** its relevant products are the embedding model's own top results. See [`EVAL_RESULTS.md`](EVAL_RESULTS.md) for this caveat and the per-query breakdown.
- **No reranker row:** the app has no reranker yet.
- **TinyLlama results vary slightly between runs:** this run gave hybrid NDCG@10 0.832, an earlier one 0.831. The LLM's output isn't perfectly repeatable on the GPU even at temperature 0.

## 2. Latency and throughput

### With TinyLlama (the normal configuration)

| Concurrent requests | p50 | p95 | p99 | max | Throughput | Error rate |
|---|---|---|---|---|---|---|
| 1 | 502 ms | 825 ms | 1104 ms | 1444 ms | 1.99 req/s | 0.0% |
| 4 | 1308 ms | 1827 ms | 3505 ms | 3704 ms | 3.06 req/s | 0.0% |
| 8 | 2846 ms | 3430 ms | 3672 ms | 4025 ms | 3.13 req/s | 0.0% |

### Without the LLM (`QUERY_UNDERSTANDING_ENABLED=false`)

| Concurrent requests | p50 | p95 | p99 | max | Throughput | Error rate |
|---|---|---|---|---|---|---|
| 1 | 115 ms | 262 ms | 604 ms | 925 ms | 7.25 req/s | 0.0% |
| 4 | 261 ms | 463 ms | 765 ms | 902 ms | 12.48 req/s | 0.0% |
| 8 | 749 ms | 1087 ms | 1158 ms | 1234 ms | 10.26 req/s | 0.0% |

The difference between the two tables is the cost of LLM query understanding.

### Where the time goes (server side, with TinyLlama)

One request at a time:

| Stage | p50 | p95 |
|---|---|---|
| LLM query understanding (TinyLlama) | 316 ms | 423 ms |
| Query embedding (e5) | 19 ms | 37 ms |
| Vector search query (pgvector, HNSW) | 55 ms | 229 ms |
| Keyword search queries (full-text) | 34 ms | 149 ms |
| Product-type detection (DB) | 2.3 ms | 3.8 ms |
| Filter values (cached) | 0.0 ms | 0.0 ms |
| Total server time | 497 ms | 819 ms |

8 concurrent requests:

| Stage | p50 | p95 |
|---|---|---|
| LLM query understanding (TinyLlama) | 2555 ms | 3008 ms |
| Query embedding (e5) | 36 ms | 117 ms |
| Vector search query (pgvector, HNSW) | 87 ms | 356 ms |
| Keyword search queries (full-text) | 45 ms | 245 ms |
| Product-type detection (DB) | 3.3 ms | 22 ms |
| Filter values (cached) | 0.0 ms | 0.0 ms |
| Total server time | 2835 ms | 3383 ms |

**The LLM is the bottleneck under load.** With 8 requests at once, the LLM stage takes about 8× its single-request time (2.6 s vs 0.32 s). Ollama processes one request at a time (`OLLAMA_NUM_PARALLEL=1`), so the extra requests queue for it.
- **With TinyLlama,** throughput levels off at about **3 searches/s** from 4 concurrent requests upwards.
- **Without the LLM,** the same machine handles about **12 searches/s**, and adds less latency per extra user.
- **Possible ways to raise it** (not done): let Ollama process requests in parallel, or cache the LLM's understanding of repeated queries (page and filter changes repeat the same query).

## 3. Reliability

| Check | Result |
|---|---|
| Errors under normal load (with TinyLlama, all levels) | 0 of 1800 requests |
| Errors under normal load (without LLM, all levels) | 0 of 1800 requests |
| LLM failures under normal load | 0 (the other 225 searches without the LLM were Hindi queries, which skip it by design) |
| **Degraded mode: Ollama hangs** (fake server that never answers, 4 concurrent requests, 200 requests) | error rate **0.0%**; p50 397 ms, p95 10443 ms, p99 22969 ms, max 24454 ms; LLM used for 0.0% of requests |

**Degraded mode setup:** Ollama was replaced by a fake server that accepts connections but never answers, and 4 clients searched at once.
- **What happened** (from the backend log): the first searches waited the 8 s LLM timeout. After 3 consecutive timeouts the circuit breaker opened, and searches skipped the LLM instantly. After the 30 s cooldown one search tested the LLM, waited the timeout again, and the breaker reopened.
- **Result:** no search failed, and the median stayed at normal speed. The tail (p95, p99) is the requests that waited for the LLM timeout.
- **Caveat:** the laptop went to sleep while this backend was starting, and the load test ran right after it woke. That likely inflated the tail beyond the 8 s timeout (p99 23 s). Treat the p95/p99 here as approximate until a clean rerun. The breaker's on/off behaviour itself was verified separately with exact timings: 3 searches of ~8 s, then 0.03 s each.

A separate run, with Ollama **not running at all** (connection refused instead of a hang), also had 0% errors. There the failures are instant, so there was no latency spike.

## 4. Catalogue pipeline

| Metric | Result |
|---|---|
| Embedding throughput | **144 products/s** on NVIDIA GeForce GTX 1650 (batch 64, median of 3 runs of 2,000 products) |
| Time to embed the full catalogue | ≈ 5.1 min for 44,072 products |
| GPU memory while embedding | 1111 MB peak |
| Successful ingestion rate | **100.0%**: 44,072 unchanged, 0 inserted, 0 updated, 0 invalid |
| Sync time, unchanged catalogue | 75 s (exit code 0); embedded 0, indexed 0, embedding errors 0 |

The catalogue already matched the feed, so the sync measures the "nothing changed" path: it reads and compares every record but recomputes nothing. The embedding benchmark measures what a large change costs.

## 5. Startup and memory

| Metric | With TinyLlama | Without LLM |
|---|---|---|
| Process start → `/health` responds | 1.8 s | 13.9 s |
| Process start → embedding model loaded | 27.8 s | 171.8 s |
| First search after that | 8448 ms | 18091 ms |
| Backend memory (RSS) after the first search | 1563 MB | 1470 MB |
| Backend peak memory during the load test | 1533 MB | – |
| GPU memory used (embedding model + TinyLlama) | 1943 MB of 4096 MB | 1939 MB |

**Treat the "Without LLM" column as unreliable.** That backend started just after VS Code and this session restarted, and the embedding model took about 3 minutes to load instead of about 30 seconds. The exact cause isn't confirmed. Likely candidates:
- **Memory:** WSL is limited to 3.7 GB here, and swap was in use.
- **Network:** loading the model contacts huggingface.co to check for updates. Setting `HF_HUB_OFFLINE=1` would skip that once the model is downloaded (not yet tested).

The clean "With TinyLlama" column is the representative startup.

**The first search after startup took 8.4 s even with the models loaded** (clean run). Its cause hasn't been pinned down yet. Likely contributors: the first TinyLlama call with a new JSON schema, and the first read of filter values and product types from the database.

## How to reproduce

```bash
# Quality
PYTHONPATH=. python3 scripts/run_eval.py --ground-truth evals/ground_truth/ground_truth_v2_real.json \
  --output-prefix evals/reports/health_quality_llm --use-query-understanding

# Load test: start the backend with rate limiting off, then
RATE_LIMIT_ENABLED=false PYTHONPATH=. python3 -m uvicorn app.main:app --port 8000 &
PYTHONPATH=. python3 scripts/load_test.py --label with_llm --concurrency 1 4 8 --requests 200 --repeats 3 \
  --output evals/reports/health_load_with_llm.json --backend-pid <uvicorn pid>

# Embedding throughput (read-only)
PYTHONPATH=. python3 scripts/benchmark_embeddings.py --products 2000 --repeats 3 --output evals/reports/health_embedding.json
```

## Caveats

- **These are single-machine numbers** on a 4 GB laptop GPU with 3.7 GB RAM. They show how the system behaves, not production capacity.
- **Latency depends on the query mix,** which here includes vague and Hindi queries. Hindi skips the LLM, so it's faster.
- **One backend process and one GPU:** throughput is limited by requests queuing for the GPU (LLM + embeddings); more workers or GPUs would change these numbers.
- **The degraded-mode test** simulates a hung LLM, not a database outage. Search depends on PostgreSQL and fails without it (`/health` reports 503).
