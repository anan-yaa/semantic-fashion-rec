# Search evaluation results

Results of the search-quality evaluation for the fashion recommendation service: hybrid search with and without LLM query understanding, using a local LLM (TinyLlama via Ollama) and a hosted one (Gemini API).

All numbers below are read directly from the report files in [`evals/reports/`](reports/). The per-query details are in [Appendix A](#appendix-a-per-query-results).

## Summary

| Comparison | Hybrid NDCG@10 without LLM | with LLM | Change | Queries better / worse / unchanged |
|---|---|---|---|---|
| **TinyLlama (local, GPU)** | 0.820 | 0.831 | **+0.011** | 3 / 0 / 77 |
| **Gemini API** | 0.825 | 0.803 | **-0.022** | 3 / 7 / 70 |

Each LLM run is compared with a baseline (no LLM) run on the same code version: for TinyLlama the same commit; for Gemini a baseline run 20 minutes earlier with no commits in between. The search code changed between the two LLM runs, so the two "with LLM" numbers should not be compared with each other directly.

- **TinyLlama made hybrid search slightly better and no query worse.** The gain comes from 3 queries: “women's silver jewellery” (+0.408), “white sneakers” (+0.269), “sturdy bag for carrying a laptop” (+0.220).
- **Gemini made hybrid search slightly worse on this answer key** (7 queries worse, 3 better). Most losses are vague queries that Gemini cut down to one word ("something trendy" → "trendy", "something comfortable" → "comfortable", "nice accessory" → "accessory"). A one-word keyword search matches many loosely related products, which then get mixed into the hybrid results. The setups also differ in other ways (see [Differences between the two LLM setups](#differences-between-the-two-llm-setups)).
- **Vector search is identical in every run** (0.923), as expected: the LLM only affects the keyword side of hybrid search.
- **Read these as small effects.** With 80 queries, differences of about ±0.01 rest on a handful of queries, and the answer key favours vector search (see [Caveats](#caveats)).

## How the evaluation works

- **Queries:** 80 queries in [`queries/query_set_v1.json`](queries/query_set_v1.json): keyword-style ("navy blue shirt"), natural-language ("lightweight breathable top for hot days"), occasion, gender, vague, and 10 Hindi queries.
- **Answer key:** [`ground_truth/ground_truth_v2_real.json`](ground_truth/ground_truth_v2_real.json). For each query, the 20 products most similar to it under the multilingual-e5 embedding model are marked relevant.
- **Methods scored:** `hybrid` (what the app uses: vector + keyword fused with Reciprocal Rank Fusion), `vector` and `keyword`, each on its own.
- **Metrics** (per query, then averaged):
  - **NDCG@10:** ranking quality of the top 10, rewarding relevant products near the top.
  - **Precision@10:** share of the top 10 that is relevant.
  - **MRR:** 1 / position of the first relevant result.
- **With LLM:** each query first goes through query understanding, exactly as `POST /search` does. The LLM's keyword rewrite and inferred filters apply to the **keyword** side only; vector search always uses the original query.

Reproduce:

```bash
PYTHONPATH=. python3 scripts/run_eval.py \
  --ground-truth evals/ground_truth/ground_truth_v2_real.json \
  --output-prefix evals/reports/<name> [--use-query-understanding]
```

## Run 1: Baseline, no LLM (current code)

| | |
|---|---|
| Report | [`report_no_llm_current.md`](reports/report_no_llm_current.md) / [`.json`](reports/report_no_llm_current.json) / [`.log`](reports/report_no_llm_current.log) |
| Run at | 2026-10-05 15:55 UTC |
| Code | commit `20c0205` (filters, sorting, pagination, product-type ranking) |
| Duration | 2 min 20 s |

| Method | NDCG@10 | Precision@10 | MRR |
|---|---|---|---|
| hybrid | 0.820 | 0.720 | 0.925 |
| vector | 0.923 | 0.841 | 0.925 |
| keyword | 0.309 | 0.189 | 0.385 |

## Run 2: TinyLlama query understanding (local, GPU)

| | |
|---|---|
| Report | [`report_tinyllama_gpu.md`](reports/report_tinyllama_gpu.md) / [`.json`](reports/report_tinyllama_gpu.json) / [`.log`](reports/report_tinyllama_gpu.log) |
| Run at | 2026-10-05 15:52 UTC |
| Code | commit `20c0205`, same as Run 1 |
| LLM | `tinyllama` (1.1B, Q4) via Ollama on a GTX 1650 (100% GPU), timeout 15 s |
| LLM used | 70 of 80 queries; 10 Hindi queries skipped by design (handled by multilingual vector search); **0 failures or timeouts** |
| Grounding | 21 inferred filters dropped because the query didn't mention them (17 gender, 4 season) |
| Duration | 3 min 21 s (both models loaded inside the run) |

| Method | NDCG@10 | Precision@10 | MRR |
|---|---|---|---|
| hybrid | 0.831 | 0.731 | 0.931 |
| vector | 0.923 | 0.841 | 0.925 |
| keyword | 0.272 | 0.176 | 0.353 |

**Change from Run 1:**

| Run | Hybrid NDCG@10 | Hybrid P@10 | Hybrid MRR | Vector NDCG@10 | Keyword NDCG@10 |
|---|---|---|---|---|---|
| Baseline (Run 1) | 0.820 | 0.720 | 0.925 | 0.923 | 0.309 |
| TinyLlama (Run 2) | 0.831 | 0.731 | 0.931 | 0.923 | 0.272 |

- Hybrid: 3 queries better, 0 worse, 77 unchanged.
- Keyword on its own: 2 better, 6 worse. TinyLlama sometimes rewrites a query in a way that loses matches, e.g. “spring light jacket” (-1.000), “eye-catching statement jewellery” (-0.765), “white sneakers” (-0.501). Hybrid isn't affected by these because vector search compensates, and hybrid is what the app uses.

Log excerpt ([full log](reports/report_tinyllama_gpu.log)):

```text
15:49:48 Loaded 80 judged queries from evals/ground_truth/ground_truth_v2_real.json
15:50:03 Using OllamaProvider: tinyllama at http://localhost:11434, timeout=15.0s
15:50:03 Query understanding ENABLED for this eval run - making real LLM API calls
15:50:05 Dropping ungrounded gender='Men' for query 'black leather jacket'
15:51:14 Model loaded. Output dimension: 768          (multilingual-e5-base, cuda)
...
Query understanding: 80 calls, 70 real, 10 fell back to the original query
15:52:32 Reports written to evals/reports/report_tinyllama_gpu.json and .md
```

## Run 3: Gemini API query understanding

| | |
|---|---|
| Report | [`report_gemini_llm.md`](reports/report_gemini_llm.md) / [`.json`](reports/report_gemini_llm.json) (no `.log` file was saved for this run; its per-query LLM output is in the JSON and in Appendix A) |
| Run at | 2026-10-05 06:23 UTC |
| Code | uncommitted working tree between commits `a434582` and `fc96eaf` (keyword coverage threshold 0.75; no product-type ranking) |
| Baseline for this run | [`report_hybrid_coverage_075`](reports/report_hybrid_coverage_075.md), no commits in between, run at 2026-10-05 06:03 UTC |
| LLM | Gemini API, `gemini-3.5-flash-lite` (the configured default; the model name isn't recorded in the report) |
| LLM used | 80 of 80 queries, including the Hindi ones |

| Method | NDCG@10 | Precision@10 | MRR |
|---|---|---|---|
| hybrid | 0.803 | 0.714 | 0.925 |
| vector | 0.923 | 0.841 | 0.925 |
| keyword | 0.301 | 0.184 | 0.377 |

**Change from its baseline:**

| Run | Hybrid NDCG@10 | Hybrid P@10 | Hybrid MRR | Vector NDCG@10 | Keyword NDCG@10 |
|---|---|---|---|---|---|
| Baseline (no LLM) | 0.825 | 0.733 | 0.925 | 0.923 | 0.309 |
| Gemini (Run 3) | 0.803 | 0.714 | 0.925 | 0.923 | 0.301 |

- Hybrid: 3 queries better, 7 worse, 70 unchanged.
- Largest gains: “sturdy bag for carrying a laptop” (+0.220), “grey topwear” (+0.042), “white sneakers” (+0.010).
- Largest losses: “nice accessory” (-0.613), “गर्मियों के कपड़े” (-0.407), “something trendy” (-0.362).
- Keyword on its own: 10 better, 7 worse.

### Earlier Gemini run on the v1 answer key

On 2026-10-03 Gemini was also evaluated on the older, human-reviewed v1 answer key ([`report_gemini_api.md`](reports/report_gemini_api.md) / [`report_gemini_20261003T154356Z.json`](reports/report_gemini_20261003T154356Z.json)). Only 49 of its 73 queries actually used Gemini; **24 hit the free tier's rate limit (HTTP 429)** and fell back to the plain query, so it measures a partial Gemini setup.

| Run | Hybrid NDCG@10 | Hybrid P@10 | Hybrid MRR | Vector NDCG@10 | Keyword NDCG@10 |
|---|---|---|---|---|---|
| Baseline, v1 (2026-10-03 14:36) | 0.904 | 0.881 | 0.942 | 0.931 | 0.390 |
| Gemini, v1 (2026-10-03 15:48) | 0.864 | 0.844 | 0.921 | 0.918 | 0.396 |

The v1 answer key can no longer be used: its product IDs come from an earlier ingest of the catalogue, and none of them exist in the current database (later runs on v1 score 0.000).

## Differences between the two LLM setups

| | Gemini (Run 3) | TinyLlama (Run 2) |
|---|---|---|
| Where it runs | Hosted API (needs a key; free tier rate-limited) | Local, Ollama on the GPU |
| Filters it can infer | category, gender, color, season | gender, color, season (category dropped: the small model got it wrong too often, e.g. "saree" → Footwear) |
| Filter check | Value must exist in the catalogue | Value must exist in the catalogue **and** be mentioned in the query ("autumn" counts as Fall, "ladies" as Women) |
| Hindi queries | Sent to the LLM | Skipped; left to multilingual vector search |
| Output format | JSON schema enforced by the API | JSON schema enforced by Ollama |
| Search code | Before product-type ranking | With product-type ranking (also in its baseline) |

## Caveats

1. **The answer key favours vector search.** Its "relevant" products are the embedding model's own top 20 per query, so vector search scores near the ceiling by construction (0.923). Products that keyword or hybrid search find and that a shopper would accept (for example other black jackets) can be counted as wrong. This understates what keyword search and the LLM add. A fairer comparison would need pooled results from every method, judged by people.
2. **Small sample.** 80 queries, and each LLM changed hybrid results for fewer than 10 of them, so the differences are indicative, not statistically established.
3. **The two LLM runs used different search code** (see their baselines), so compare each LLM with its own baseline, not with each other.
4. **Recall@K is not measured yet.** Every query has 20 relevant products, so Recall@20 and Recall@50 would show how many good products search misses; this is a planned addition.

## All reports in `evals/reports/`

| Report | Answer key | LLM | Hybrid NDCG@10 | Notes |
|---|---|---|---|---|
| [`report_preliminary`](reports/report_preliminary.md) | v1, unreviewed | – | 0.904 | First run, labels not yet reviewed |
| [`report_20261003T143435Z`](reports/report_20261003T143435Z.md) | v1 | – | 0.904 | Baseline on the reviewed v1 key |
| [`report_gemini_api`](reports/report_gemini_api.md) | v1 | Gemini | 0.864 | 24 of 73 queries rate-limited |
| [`report_20261004_083004_prod_validated`](reports/report_20261004_083004_prod_validated.md) | v1 | Gemini | 0.000 | v1 IDs no longer in the database |
| [`report_final_baseline`](reports/report_final_baseline.md) | v2_auto | – | 0.000 | v2_auto IDs not in the database |
| [`report_final_baseline_real`](reports/report_final_baseline_real.md) | v2_real | – | 0.806 | First baseline on v2_real (keyword search required every word) |
| [`report_keyword_or_fix`](reports/report_keyword_or_fix.md) | v2_real | – | 0.694 | Keyword search matches any word: keyword up, hybrid down (noise) |
| [`report_hybrid_coverage_075`](reports/report_hybrid_coverage_075.md) | v2_real | – | 0.825 | Hybrid keeps keyword hits matching ≥ 75% of words |
| [`report_gemini_llm`](reports/report_gemini_llm.md) | v2_real | Gemini | 0.803 | Run 3 |
| [`report_no_llm_current`](reports/report_no_llm_current.md) | v2_real | – | 0.820 | Run 1 (current code) |
| [`report_tinyllama_gpu`](reports/report_tinyllama_gpu.md) | v2_real | TinyLlama | 0.831 | Run 2 |

## Appendix A: per-query results

Hybrid NDCG@10 for each query, and what each LLM extracted from it (keywords used for keyword search, then filters). ▲/▼ mark queries where the LLM changed the score.

| # | Query | Baseline → TinyLlama | TinyLlama understood | Baseline → Gemini | Gemini understood |
|---|---|---|---|---|---|
| q001 | black leather jacket | 0.539 → 0.539 | “black leather jacket” · color=Black | 1.000 → 1.000 | “black leather jacket” · category=Apparel, color=Black |
| q002 | navy blue running shoes | 0.647 → 0.647 | “navy blue running shoes” · color=Navy Blue | 0.647 → 0.647 | “navy blue running shoes” · category=Footwear, color=Navy Blue |
| q003 | women's silver jewellery | 0.592 → 1.000 ▲ | “silver jewelery” · gender=Women | 0.592 → 0.592 | “women silver jewellery” · category=Accessories, gender=Women, color=Silver |
| q004 | formal watch for men | 0.584 → 0.584 | “formal watch” · gender=Men | 0.690 → 0.690 | “formal watch men” · category=Accessories, gender=Men |
| q005 | brown leather wallet | 0.849 → 0.849 | “brown leather wallet” | 0.855 → 0.855 | “brown leather wallet” · category=Accessories, color=Brown |
| q006 | grey eyewear sunglasses | 1.000 → 1.000 | “grey eyewear sunglasses” | 0.367 → 0.367 | “grey eyewear sunglasses” · category=Accessories, color=Grey |
| q007 | pink innerwear | 0.841 → 0.841 | “pink innerwear” | 0.841 → 0.841 | “pink innerwear” · category=Apparel, color=Pink |
| q008 | purple handbag | 0.727 → 0.727 | “purple handbag” · color=Purple | 0.791 → 0.791 | “purple handbag” · category=Accessories, color=Purple |
| q009 | white flip flops | 0.782 → 0.782 | “white flip flops” | 0.770 → 0.770 | “white flip flops” · category=Footwear, color=White |
| q010 | yellow socks | 1.000 → 1.000 | “yellow socks” | 1.000 → 1.000 | “yellow socks” · category=Apparel, color=Yellow |
| q011 | maroon saree | 1.000 → 1.000 | “maroon saree” · color=Maroon | 1.000 → 1.000 | “maroon saree” · category=Apparel, gender=Women, color=Maroon |
| q012 | black belt for men | 0.533 → 0.533 | “black belt for men” · gender=Men | 0.772 → 0.772 | “black belt men” · category=Accessories, gender=Men, color=Black |
| q013 | lightweight breathable top for hot days | 1.000 → 1.000 | “lightweight breathable top for hot days” | 1.000 → 1.000 | “lightweight breathable top hot days” · category=Apparel, season=Summer |
| q014 | shoes for standing all day comfortably | 1.000 → 1.000 | “comfortable shoes for standing all day” | 1.000 → 1.000 | “shoes standing comfortable” · category=Footwear |
| q015 | elegant evening handbag | 1.000 → 1.000 | “elegant evening handbag” | 1.000 → 1.000 | “elegant evening handbag” · category=Accessories |
| q016 | rugged outdoor footwear | 1.000 → 1.000 | “rugged outdoor footwear” | 1.000 → 1.000 | “rugged outdoor footwear” · category=Footwear |
| q017 | eye-catching statement jewellery | 1.000 → 1.000 | “eye-catching statement jewelry” | 1.000 → 1.000 | “eye-catching statement jewellery” · category=Accessories |
| q018 | soft loungewear for relaxing at home | 1.000 → 1.000 | “soft loungewear for relaxing at home” | 1.000 → 1.000 | “soft loungewear relaxing home” · category=Apparel |
| q019 | a fragrance that lasts all day | 1.000 → 1.000 | “fragance that lasts all day” | 1.000 → 1.000 | “fragrance lasts all day” · category=Personal Care |
| q020 | sturdy bag for carrying a laptop | 0.780 → 1.000 ▲ | “sturdy laptop bag” | 0.780 → 1.000 ▲ | “sturdy bag laptop” · category=Accessories |
| q021 | sleek minimalist wristwatch | 1.000 → 1.000 | “sleek minimalist wristwaTCH” | 1.000 → 1.000 | “sleek minimalist wristwatch” · category=Accessories |
| q022 | warm layer to wear under a jacket | 1.000 → 1.000 | “warm layer to wear under a jacket” | 1.000 → 1.000 | “warm layer under jacket” · category=Apparel, season=Winter |
| q023 | breathable socks for long walks | 1.000 → 1.000 | “breathable socks for long walks” | 1.000 → 1.000 | “breathable socks long walks” · category=Apparel |
| q024 | durable sandals for everyday wear | 1.000 → 1.000 | “durable sandals for everyday wear” | 1.000 → 1.000 | “durable sandals everyday wear” · category=Footwear |
| q025 | outfit for a job interview | 1.000 → 1.000 | “job interview outfit” | 1.000 → 1.000 | “outfit job interview” · category=Apparel |
| q026 | something to wear to a summer wedding | 1.000 → 1.000 | “summer wedding dress” · season=Summer | 1.000 → 0.757 ▼ | “summer wedding” · category=Apparel, season=Summer |
| q027 | gym workout clothes | 0.000 → 0.000 | “gym workout clothes” | 0.000 → 0.000 | “gym workout clothes” · category=Apparel |
| q028 | beach vacation outfit | 1.000 → 1.000 | “beach vacation outfit” | 1.000 → 1.000 | “beach vacation outfit” · category=Apparel, season=Summer |
| q029 | office wear for men | 1.000 → 1.000 | “office wear for men” · gender=Men | 1.000 → 1.000 | “office wear men” · category=Apparel, gender=Men |
| q030 | festive traditional wear for women | 1.000 → 1.000 | “festive traditional wear for women” · gender=Women | 1.000 → 1.000 | “festive traditional wear women” · category=Apparel, gender=Women |
| q031 | clothes for a night out | 1.000 → 1.000 | “night out clothes” | 1.000 → 1.000 | “clothes night out” · category=Apparel |
| q032 | sportswear for running a marathon | 1.000 → 1.000 | “sportswear for running a marathon” | 1.000 → 1.000 | “sportswear running marathon” · category=Sporting Goods |
| q033 | travel-friendly comfortable shoes | 1.000 → 1.000 | “travel-friendly comfortable shoes” | 1.000 → 1.000 | “travel friendly comfortable shoes” · category=Footwear |
| q034 | party accessories for women | 0.905 → 0.905 | “party accessories for women” · gender=Women | 0.905 → 0.905 | “party accessories women” · category=Accessories, gender=Women |
| q035 | warm winter coat | 0.000 → 0.000 | “warm winter coat” · season=Winter | 0.000 → 0.000 | “warm winter coat” · category=Apparel, season=Winter |
| q036 | summer dress | 0.432 → 0.432 | “summer dress” · season=Summer | 0.522 → 0.522 | “summer dress” · category=Apparel, season=Summer |
| q037 | fall jacket for men | 0.478 → 0.478 | “fall jacket for men” · gender=Men | 0.473 → 0.473 | “fall jacket men” · category=Apparel, gender=Men, season=Fall |
| q038 | spring light jacket | 1.000 → 1.000 | “spring light jacket” · season=Spring | 1.000 → 1.000 | “spring light jacket” · category=Apparel, season=Spring |
| q039 | winter woolen socks | 1.000 → 1.000 | “winter woolen socks” | 1.000 → 1.000 | “winter woolen socks” · category=Apparel, season=Winter |
| q040 | summer sandals | 0.469 → 0.469 | “summer sandals” · season=Summer | 0.330 → 0.330 | “summer sandals” · category=Footwear, season=Summer |
| q041 | monsoon footwear | 1.000 → 1.000 | “monsoon footwear” | 1.000 → 1.000 | “monsoon footwear” · category=Footwear, season=Fall |
| q042 | winter sweater for women | 1.000 → 1.000 | “winter sweater for women” · gender=Women | 1.000 → 1.000 | “winter sweater women” · category=Apparel, gender=Women, season=Winter |
| q043 | summer topwear for men | 0.842 → 0.842 | “summer topwear for men” · gender=Men | 0.842 → 0.842 | “summer topwear men” · category=Apparel, gender=Men, season=Summer |
| q044 | fall accessories | 0.785 → 0.785 | “fall accessories” | 0.785 → 0.785 | “fall accessories” · category=Accessories, season=Fall |
| q045 | maroon saree for women | 1.000 → 1.000 | “maroon saree” · gender=Women, color=Maroon | 1.000 → 1.000 | “maroon saree” · category=Apparel, gender=Women, color=Maroon |
| q046 | beige sandals | 0.990 → 0.990 | “beige sandals” | 1.000 → 0.936 ▼ | “beige sandals” · category=Footwear, color=Beige |
| q047 | olive green bag | 0.927 → 0.927 | “olive green bag” · color=Olive | 0.927 → 0.927 | “olive green bag” · category=Accessories, color=Olive |
| q048 | white sneakers | 0.731 → 1.000 ▲ | “white snaker” · color=White | 0.731 → 0.741 ▲ | “white sneakers” · category=Footwear, color=White |
| q049 | red dress | 1.000 → 1.000 | “red dress” · color=Red | 1.000 → 1.000 | “red dress” · category=Apparel, color=Red |
| q050 | navy blue shirt | 0.771 → 0.771 | “navy blue shirt” · color=Navy Blue | 0.791 → 0.791 | “navy blue shirt” · category=Apparel, color=Navy Blue |
| q051 | gold watch | 0.858 → 0.858 | “gold watch” | 0.785 → 0.785 | “gold watch” · category=Accessories, color=Gold |
| q052 | black formal shoes | 1.000 → 1.000 | “black formal shoes” | 1.000 → 1.000 | “black formal shoes” · category=Footwear, color=Black |
| q053 | grey topwear | 0.542 → 0.542 | “grey topwear” | 0.542 → 0.584 ▲ | “grey topwear” · category=Apparel, color=Grey |
| q054 | orange accessories | 0.756 → 0.756 | “orange accessories” | 0.756 → 0.754 ▼ | “orange accessories” · category=Accessories, color=Orange |
| q055 | boys topwear | 0.703 → 0.703 | “boys topwear” · gender=Boys | 0.703 → 0.703 | “boys topwear” · category=Apparel, gender=Boys |
| q056 | girls dress | 1.000 → 1.000 | “girls dress” · gender=Girls | 1.000 → 1.000 | “girls dress” · category=Apparel, gender=Girls |
| q057 | unisex sunglasses | 0.797 → 0.797 | “unisex sunglasses” | 0.860 → 0.860 | “unisex sunglasses” · category=Accessories, gender=Unisex |
| q058 | men's innerwear | 0.706 → 0.706 | “men's innerwear” · gender=Men | 0.706 → 0.706 | “mens innerwear” · category=Apparel, gender=Men |
| q059 | women's handbags | 0.477 → 0.477 | “women's handbag” · gender=Women | 0.570 → 0.570 | “women handbags” · category=Accessories, gender=Women |
| q060 | boys footwear | 0.555 → 0.555 | “boys footwear” · gender=Boys | 0.555 → 0.555 | “boys footwear” · category=Footwear, gender=Boys |
| q061 | girls accessories | 0.469 → 0.469 | “girls accessories” · gender=Girls | 0.469 → 0.469 | “girls accessories” · category=Accessories, gender=Girls |
| q062 | unisex watches | 0.785 → 0.785 | “unisex watches” | 0.849 → 0.849 | “unisex watches” · category=Accessories, gender=Unisex |
| q063 | cozy winter outfit | 1.000 → 1.000 | “winter cozy outfit” · season=Winter | 1.000 → 1.000 | “cozy winter outfit” · category=Apparel, season=Winter |
| q064 | something comfortable | 1.000 → 1.000 | “comfortable something” | 1.000 → 0.679 ▼ | “comfortable” |
| q065 | nice accessory | 1.000 → 1.000 | “nice accessory” | 1.000 → 0.387 ▼ | “accessory” · category=Accessories |
| q066 | stylish footwear | 0.766 → 0.766 | “stylish footwear” | 0.766 → 0.766 | “stylish footwear” · category=Footwear |
| q067 | good gift idea | 0.000 → 0.000 | “good gift idea” | 0.000 → 0.000 | “gift idea” |
| q068 | something trendy | 1.000 → 1.000 | “trench coat” | 1.000 → 0.638 ▼ | “trendy” |
| q069 | everyday essentials | 0.000 → 0.000 | “everyday essential” | 0.000 → 0.000 | “everyday essentials” |
| q070 | something for casual outings | 0.000 → 0.000 | “casual outings” | 0.000 → 0.000 | “casual outings” |
| q071 | नीली शर्ट | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “नीली शर्ट” · category=Apparel, color=Blue |
| q072 | सर्दियों का ऊनी कोट | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “सर्दियों ऊनी कोट” · category=Apparel, season=Winter |
| q073 | काली जूती | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “काली जूती” · category=Footwear, color=Black |
| q074 | महिलाओं के लिए गहने | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “gahne” · category=Accessories, gender=Women |
| q075 | पुरुषों के लिए घड़ी | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “पुरुषों घड़ी watch mens” · category=Accessories, gender=Men |
| q076 | लाल साड़ी | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “लाल साड़ी red saree” · category=Apparel, gender=Women, color=Red |
| q077 | बच्चों के कपड़े | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “बच्चों के कपड़े” · category=Apparel, gender=Boys |
| q078 | सफेद जूते | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “सफेद जूते” · category=Footwear, color=White |
| q079 | चमड़े का बैग | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 1.000 | “चमड़े बैग leather bag” · category=Accessories |
| q080 | गर्मियों के कपड़े | 1.000 → 1.000 | skipped (non-Latin script) | 1.000 → 0.593 ▼ | “summer clothes” · category=Apparel, season=Summer |
