# System health and search quality

Measured 2026-10-06 with **Gemma 3 1B** (the LLM the app now uses) on commit `dd5233b` plus uncommitted changes that don't affect results (the load test's new `--endpoint` option, Docker files). It replaces the earlier TinyLlama report, which is kept in [`reports/`](reports/) as the `health_*` files without a `gemma3` suffix. Raw results for this report are the `health_*gemma3*` files.

## Summary

| Metric | Result |
|---|---|
| Search quality, hybrid + Gemma, 80 queries (NDCG@10 / Recall@50) | 0.727 / 0.622 |
| ↳ 70 English queries | 0.793 / 0.689 |
| ↳ 10 Hindi queries (not a fair measure, see section 1) | 0.258 / 0.155 |
| LLM used | 80 of 80 queries in the quality eval; 100% of searches in every load run |
| Search latency p50 / p95 / p99, one user at a time | 793 ms / 989 ms / 1502 ms |
| Search latency p50 / p95, 8 concurrent requests | 5584 ms / 5939 ms |
| Throughput, 1 / 4 / 8 concurrent requests | 1.20 / 1.38 / 1.43 searches/s |
| Throughput with the LLM result cache on (best case, 80 repeated queries) | 5.1 / 11.3 / 9.5 searches/s |
| Outfit builder (`POST /outfit`) latency p50 / p95, one user | 1168 ms / 1610 ms |
| LLM latency p50 / p95, one user | 662 ms / 807 ms |
| Query embedding latency p50 / p95 | 11 ms / 19 ms |
| DB latency p50 (vector + keyword + type detection, sum of each stage's median) | 78 ms |
| Error rate under load | 0.0% (0 of 1200 searches, 0 of 160 outfits) |
| Error rate while the LLM hangs | 0.0% (every search fell back to plain search) |
| Embedding throughput | 144 products/s (NVIDIA GeForce GTX 1650); full catalogue ≈ 5.1 min *(measured earlier, unchanged)* |
| Successful ingestion rate | 100.0% (44,072 of 44,072 feed records) *(measured earlier, unchanged)* |
| Catalogue sync, no changes | 75 s *(measured earlier, unchanged)* |

Each load figure is the median of 2 runs (with 2 runs, the average of the two). Latencies are client-side wall time except the per-stage figures, which come from the server's `Server-Timing` header.

## What changed since the TinyLlama report

| | TinyLlama (old report) | Gemma 3 1B (this report) |
|---|---|---|
| LLM time per search, one user | 316 ms | 662 ms |
| Search p50, one user | 502 ms | 793 ms |
| Search p50, 8 concurrent | 2846 ms | 5584 ms |
| Throughput, 8 concurrent | 3.1 searches/s | 1.43 searches/s |
| Queries using the LLM | 70 of 80 (Hindi skipped) | 80 of 80 |
| GPU memory (embedding model + LLM) | 1943 MiB | 2122 MiB |

Gemma costs about twice the LLM time per search and roughly halves throughput, in exchange for multilingual translation (see [`LLM_COMPARISON.md`](LLM_COMPARISON.md)). Two things are new since the last report: a cache of LLM results per query, and the `/outfit` endpoint.

## Test conditions

- **Hardware:** NVIDIA GeForce GTX 1650, 4096 MiB; WSL2 with 3.7 GB RAM; 8 CPU cores.
- **Backend:** one uvicorn process; Gemma 3 1B via Ollama, confirmed at 100% GPU (`ollama ps`); multilingual-e5-base on the GPU; 44,072 products in PostgreSQL 15.19 + pgvector 0.8.6 (the local development database these measurements ran against; Docker Compose and CI use PostgreSQL 16).
- **Settings:** rate limiting off (otherwise most requests get 429); LLM result cache **off** except in the run marked "cache on"; LLM timeout 8 s, circuit breaker 3 failures / 30 s.
- **Load:** the 80 eval queries in a fixed random order; 20 unmeasured warm-up requests; 200 measured requests per concurrency level, 2 repeats (outfit: 40 requests, 2 repeats). Ollama was already loaded.
- **Checked on every run:** the share of searches that actually used the LLM and the fallback count are recorded in each report (`llm_used_rate`, `llm_fallbacks`), so a silent fallback can't pass as a healthy run.

---

## 1. Search quality

Hybrid search with Gemma, 80 queries, answer key `ground_truth_v2_real.json` ([`reports/health_quality_gemma3.md`](reports/health_quality_gemma3.md)). The LLM was used for **80 of 80 queries** (10 of them translated to English), with 0 fallbacks.

| Queries | Method | NDCG@10 | Precision@10 | MRR@10 | Recall@20 | Recall@50 |
|---|---|---|---|---|---|---|
| All 80 | Hybrid + Gemma (what the app runs) | 0.727 | 0.622 | 0.842 | 0.501 | 0.622 |
| All 80 | Vector (with Gemma's translation) | 0.827 | 0.741 | 0.838 | 0.626 | 0.633 |
| All 80 | Keyword | 0.316 | 0.189 | 0.389 | 0.158 | 0.264 |
| 70 English | Hybrid + Gemma | 0.793 | 0.687 | 0.914 | 0.554 | 0.689 |
| 70 English | Vector | 0.912 | 0.827 | 0.914 | 0.699 | 0.704 |
| 10 Hindi | Hybrid + Gemma | 0.258 | 0.170 | 0.333 | 0.125 | 0.155 |
| 10 Hindi | Vector (searched in English) | 0.225 | 0.140 | 0.300 | 0.115 | 0.135 |

- **English quality matches the earlier Gemma comparison** (hybrid NDCG@10 0.793 here, 0.794 in [`LLM_COMPARISON.md`](LLM_COMPARISON.md)).
- **The Hindi rows are not a quality measure.** The answer key is the embedding model's own top 20 for the Hindi *text*, so searching the Hindi text scores perfectly and any translation scores lower, even a correct one. Hindi quality is judged by the multilingual test in [`EXPLORATION.md`](EXPLORATION.md#3-multilingual-queries). For the same reason the all-80 vector figure (0.827) is below the old 0.923: vector search now uses the English translation for non-English queries.
- **The answer key favours vector search** (see [`EVAL_RESULTS.md`](EVAL_RESULTS.md)), which is why vector beats hybrid here.
- Recall@10 can't exceed 0.5, since each query has 20 relevant products.

## 2. Latency and throughput

### With Gemma (the normal configuration, LLM cache off)

| Concurrent requests | p50 | p95 | p99 | max | Throughput | Error rate | LLM used |
|---|---|---|---|---|---|---|---|
| 1 | 793 ms | 989 ms | 1502 ms | 3871 ms | 1.20 req/s | 0.0% | 100% |
| 4 | 2784 ms | 3038 ms | 8721 ms | 9173 ms | 1.38 req/s | 0.0% | 100% |
| 8 | 5584 ms | 5939 ms | 6057 ms | 6123 ms | 1.43 req/s | 0.0% | 100% |

At 4 concurrent requests, one of the two runs contained a single stall of about 15 s (that run's p99 was 14248 ms, the other's 3193 ms). It produced no error or fallback and its cause is unknown, so the p99 and max above are inflated by it. With only 2 runs, the median can't separate it out. The TinyLlama report saw similar one-off stalls (9 s and 12 s) and attributed them to system pauses.

### Where the time goes (server side)

One request at a time:

| Stage | p50 | p95 |
|---|---|---|
| LLM query understanding (Gemma) | 662 ms | 807 ms |
| Query embedding (e5) | 11 ms | 19 ms |
| Vector search query (pgvector, HNSW) | 54 ms | 147 ms |
| Keyword search queries (full-text) | 22 ms | 69 ms |
| Product-type detection (DB) | 1.7 ms | 2.1 ms |
| Filter values (cached) | 0.0 ms | 0.0 ms |
| Total server time | 789 ms | 985 ms |

8 concurrent requests:

| Stage | p50 | p95 |
|---|---|---|
| LLM query understanding (Gemma) | 5454 ms | 5772 ms |
| Query embedding (e5) | 22 ms | 28 ms |
| Vector search query (pgvector, HNSW) | 28 ms | 128 ms |
| Keyword search queries (full-text) | 23 ms | 81 ms |
| Product-type detection (DB) | 1.9 ms | 2.6 ms |
| Total server time | 5575 ms | 5917 ms |

**The LLM is still the bottleneck under load, and more so with Gemma.** With 8 requests at once the LLM stage takes about 8× its single-request time (5.5 s vs 0.66 s) and is 98% of the request. Ollama processes one request at a time, so extra requests queue for it, and throughput stops rising at about 1.4 searches/s from 4 concurrent requests upwards. The database and embedding stages barely change.

### With the LLM result cache on

Repeated queries (paging, sorting, filter changes) skip the LLM. Same load, cache on ([`reports/health_load_gemma3_cache_on.json`](reports/health_load_gemma3_cache_on.json)):

| Concurrent requests | p50 | p95 | Throughput | LLM used |
|---|---|---|---|---|
| 1 | 124 ms | 607 ms | 5.06 req/s | 100% |
| 4 | 295 ms | 485 ms | 11.25 req/s | 100% |
| 8 | 797 ms | 1235 ms | 9.50 req/s | 100% |

**This is a best case, not a typical result.** The test sends only 80 distinct queries many times each, so after the first pass nearly every request is a cache hit (the median LLM stage time is 0 ms). The first run at one concurrent request shows the cache filling: 2.8 req/s, then 7.3 req/s in the second run. Real traffic has many more distinct queries, and a new query still pays the full LLM cost. The cache hit rate wasn't measured directly.

### Without the LLM (`QUERY_UNDERSTANDING_ENABLED=false`) *(measured earlier, search path unchanged)*

| Concurrent requests | p50 | p95 | p99 | max | Throughput | Error rate |
|---|---|---|---|---|---|---|
| 1 | 115 ms | 262 ms | 604 ms | 925 ms | 7.25 req/s | 0.0% |
| 4 | 261 ms | 463 ms | 765 ms | 902 ms | 12.48 req/s | 0.0% |
| 8 | 749 ms | 1087 ms | 1158 ms | 1234 ms | 10.26 req/s | 0.0% |

The difference from the Gemma table is the cost of LLM query understanding.

### Outfit builder (`POST /outfit`, Gemma, cache off)

One outfit runs one hybrid search per slot (four slots, plus one extra to choose the gender when none is given) after a single LLM call. 40 requests per run, so the percentiles are approximate ([`reports/health_load_gemma3_outfit.json`](reports/health_load_gemma3_outfit.json)).

| Concurrent requests | p50 | p95 | max | Throughput | Error rate | LLM used |
|---|---|---|---|---|---|---|
| 1 | 1168 ms | 1610 ms | 2855 ms | 0.79 req/s | 0.0% | 100% |
| 4 | 2965 ms | 3657 ms | 3883 ms | 1.31 req/s | 0.0% | 100% |

An outfit costs only about 0.4 s more than a plain search, because the LLM call (673 ms) dominates and the slot searches are cheap. The same LLM bottleneck applies under concurrency.

## 3. Reliability

| Check | Result |
|---|---|
| Errors under normal load (searches, all levels) | 0 of 1200 requests; 0 of 1200 with the cache on |
| Errors under normal load (outfits) | 0 of 160 requests |
| LLM fallbacks under normal load | 0 (every search used the LLM) |
| **Degraded mode: Ollama hangs** (fake server that accepts connections and never answers, 4 concurrent requests, 2 × 200 requests) | error rate **0.0%**; LLM used for 0%, all 400 searches fell back to plain search |

**Degraded mode** ([`reports/health_load_gemma3_degraded.json`](reports/health_load_gemma3_degraded.json)):

| Run | p50 | p95 | p99 | max | Throughput |
|---|---|---|---|---|---|
| 1 (cold start, no warm-up) | 294 ms | 677 ms | 19167 ms | 19451 ms | 5.34 req/s |
| 2 (steady state) | 241 ms | 496 ms | 673 ms | 8283 ms | 10.79 req/s |

- **What happened** (from the backend log): the first four searches waited out the 8 s LLM timeout, the circuit breaker opened after 3 consecutive timeouts, and every later search skipped the LLM instantly. No search failed and the median stayed at normal speed.
- **Run 1's 19 s tail is a cold-start effect, not the breaker.** The stage timings show the very first requests spent about 9 s reading the filter values from the database for the first time (`facets` stage max 9.1 s), then 8 s waiting for the LLM. The steady-state run 2 has a p99 of 673 ms. The one-off 8.3 s max in run 2 is the breaker's recovery probe waiting out the timeout.
- This replaces the earlier degraded run, whose tail was inflated by a laptop sleep.

**Cold Ollama (observed in an evaluation run).** When the quality eval first ran, Ollama had unloaded Gemma, and the eval script (unlike the backend) doesn't warm it. The first three LLM calls hit the 15 s eval timeout while the model loaded, the breaker opened for 30 s, and 47 of 80 queries fell back to plain search. The breaker closed on its own once the model answered. That run was discarded and repeated with Gemma loaded; the numbers in section 1 come from the repeat (80 of 80 used the LLM).

The degraded-mode test simulates a hung LLM, not a database outage. Search depends on PostgreSQL: it returns 503 when the database is down (tested), and `/health` reports 503.

## 4. Catalogue pipeline *(measured earlier, unchanged)*

| Metric | Result |
|---|---|
| Embedding throughput | **144 products/s** on NVIDIA GeForce GTX 1650 (batch 64, median of 3 runs of 2,000 products) |
| Time to embed the full catalogue | ≈ 5.1 min for 44,072 products |
| GPU memory while embedding | 1111 MB peak |
| Successful ingestion rate | **100.0%**: 44,072 unchanged, 0 inserted, 0 updated, 0 invalid |
| Sync time, unchanged catalogue | 75 s (exit code 0); embedded 0, indexed 0, embedding errors 0 |

These come from the earlier report. The embedding model and the sync code haven't changed since. The catalogue already matched the feed, so the sync measures the "nothing changed" path; the embedding benchmark measures what a large change costs. On CPU inside Docker, embedding ran at about 20 products/s ([`reports/compose_verification.md`](reports/compose_verification.md)).

## 5. Startup and memory

| Metric | Gemma, cache off | Gemma, cache on | LLM hung |
|---|---|---|---|
| Process start → `/health` responds | 4.5 s | 20.0 s | 10.5 s |
| Process start → embedding model loaded | 50.6 s | 84.0 s | 45.2 s |
| First search after that | 7.4 s (LLM used) | not measured | not measured |
| Backend memory (RSS) after start | 1389 MB | 1412 MB | 1435 MB |
| GPU memory used (embedding model + Gemma) | 2122 MB of 4096 MB | 2122 MB | 2122 MB |

- **Startup time varies between starts** (45 to 84 s to load the embedding model). The cause of the spread isn't confirmed.
- **Ollama was already loaded in these starts**, so this isn't a cold Ollama start. A cold model load takes noticeably longer (see the cold Ollama observation in section 3).
- **The first search after startup (7.4 s) is slow even with the models loaded.** The degraded run suggests why: the first reads of the filter values and product types from the database are slow. In that run the filter-values lookup took about 9 s on the first requests. Loading them during startup warm-up would likely remove most of this; that hasn't been done.
- **Backend memory** peaked at 1.3 GB during the load tests.

## How to reproduce

```bash
# Quality (Ollama must be loaded first, or the first LLM calls time out and the breaker opens;
# check the "Query understanding: N calls, N real" line says 80 real)
LLM_CACHE_TTL_SECONDS=0 PYTHONPATH=. python3 scripts/run_eval.py \
  --ground-truth evals/ground_truth/ground_truth_v2_real.json \
  --output-prefix evals/reports/health_quality_gemma3 --use-query-understanding

# Load test: start the backend with rate limiting and the LLM cache off, then
RATE_LIMIT_ENABLED=false LLM_CACHE_TTL_SECONDS=0 PYTHONPATH=. python3 -m uvicorn app.main:app --port 8000 &
PYTHONPATH=. python3 scripts/load_test.py --label gemma3_cache_off --concurrency 1 4 8 --requests 200 --repeats 2 \
  --output evals/reports/health_load_gemma3_cache_off.json --backend-pid <uvicorn pid>
# Outfit builder:  add  --endpoint outfit --concurrency 1 4 --requests 40 --warmup 5
# Cache on:        start the backend without LLM_CACHE_TTL_SECONDS=0
# Degraded mode:   start the backend with OLLAMA_BASE_URL pointing at a server that accepts connections
#                  and never replies, with  --concurrency 4 --requests 200 --warmup 0

# Embedding throughput (read-only)
PYTHONPATH=. python3 scripts/benchmark_embeddings.py --products 2000 --repeats 3 --output evals/reports/health_embedding.json
```

## Caveats

- **These are single-machine numbers** on a 4 GB laptop GPU with 3.7 GB RAM. They show how the system behaves, not production capacity.
- **Two repeats per load level** keep the run time down, but a single outlier shows up in the median (see the 4-concurrent stall in section 2).
- **Latency depends on the query mix,** which includes vague queries and 10 Hindi queries; with Gemma those now use the LLM too.
- **One backend process, one GPU, and an LLM that handles one request at a time:** throughput is limited by requests queuing for it. More workers, a bigger GPU or a hosted LLM would change these numbers.
- **The cache-on numbers are a best case** (80 distinct queries, repeated).
- **The sections marked "measured earlier"** weren't re-run because the code behind them hasn't changed; the no-LLM table is from before the Gemma and cache changes.
- **Quality is measured against an answer key that favours vector search and penalises translation**; see [`EVAL_RESULTS.md`](EVAL_RESULTS.md).
