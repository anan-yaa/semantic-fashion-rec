# Additional exploration

The experiments behind the design decisions: what was tried, what was measured, what was chosen, and what is still open. Every number comes from a file in [`reports/`](reports/); the longer write-ups are linked from each section.

| # | Question | Outcome |
|---|---|---|
| 1 | Which small local LLM should understand queries? | Gemma 3 1B ([details](#1-which-local-llm)) |
| 2 | Local LLM or a hosted one (Gemini)? | Local; Gemini was slightly worse on the answer key and rate-limited ([details](#2-local-or-hosted-llm)) |
| 3 | How should non-English queries be handled? | Detect the language with a library, translate with the LLM, search in English ([details](#3-multilingual-queries)) |
| 4 | Should the LLM rewrite English queries? | No: it only adds filters ([details](#4-should-the-llm-rewrite-english-queries)) |
| 5 | How strict should keyword matching be? | Hybrid keeps keyword hits that match at least 75% of the words ([details](#5-keyword-matching-strictness)) |
| 6 | Can the answer key be trusted? | Only partly: it favours vector search ([details](#6-how-trustworthy-is-the-evaluation)) |
| 7 | How far can LLM filters be trusted? | Only after validation against the catalogue ([details](#7-grounding-llm-filters)) |
| 8 | Can the system return a whole outfit, not a ranked list? | Yes: fixed slots, one hybrid search each ([README](../README.md#outfit-builder)) |

Everything ran on one GTX 1650 (4 GB) with 3.7 GB of RAM under WSL, which is why only one LLM fits next to the embedding model.

## 1. Which local LLM?

TinyLlama 1.1B, Qwen 2.5 1.5B and Gemma 3 1B were each tested alone on the GPU, on the 22-query multilingual test and on the 80-query main eval. Full tables and the per-query translations are in [`LLM_COMPARISON.md`](LLM_COMPARISON.md).

| | TinyLlama | Qwen 2.5 1.5B | **Gemma 3 1B (chosen)** |
|---|---|---|---|
| Multilingual relevant@10 (22 queries) | 0.69 | 0.71 | **0.85** |
| English queries, NDCG@10 (70) | 0.808 | 0.736 | 0.794 |
| Hindi translations right | skipped | mostly wrong | 8 of 10 |
| LLM time per query | ~316 ms | ~547 ms | ~908 ms |

- TinyLlama is essentially English-only: it can't translate, so Spanish words get matched by spelling ("chaqueta" → "Red Chief" shoes).
- Qwen invents translations (red saree → "lilac", leather bag → "camera").
- Gemma translates well but is about 3× slower than TinyLlama. That was accepted for the multilingual gain.

## 2. Local or hosted LLM?

Each LLM was compared with a no-LLM baseline on the same code ([`EVAL_RESULTS.md`](EVAL_RESULTS.md)).

| | Hybrid NDCG@10 without LLM | with LLM | Queries better / worse |
|---|---|---|---|
| TinyLlama (local) | 0.820 | 0.831 | 3 / 0 |
| Gemini API | 0.825 | 0.803 | 3 / 7 |

- Gemini's losses were mostly vague queries it cut to one word ("something trendy" → "trendy"). A one-word keyword search matches many loosely related products.
- On the free tier, 24 of 73 queries in the earlier Gemini run hit the rate limit (HTTP 429) and fell back to plain search.
- The two runs used different search code, so each LLM should be compared only with its own baseline.
- Result: the local LLM is the default; Gemini stays available with `LLM_PROVIDER=gemini`.

## 3. Multilingual queries

The 22 Hindi, Spanish and French queries were scored with hand-written relevance rules (product type, plus colour and gender when stated), not the main answer key, which can't judge translation (see [section 6](#6-how-trustworthy-is-the-evaluation)). Script: [`scripts/multilingual_experiment.py`](../scripts/multilingual_experiment.py); data: [`reports/multilingual_experiment.json`](reports/multilingual_experiment.json).

**Step 1: would a dedicated translator help?** The opus-mt translation model, then search:

| Relevant@10 | Hindi | Spanish | French | All |
|---|---|---|---|---|
| Search the original text | 0.79 | 0.54 | 0.73 | 0.69 |
| Translate with opus-mt first | 0.24 | 0.99 | 0.50 | 0.56 |

It was a clear win for Spanish and a clear loss for Hindi: it turned "सर्दियों का ऊनी कोट" (winter woollen coat) into "The Unicorn's Unicorn". A translator is only as good as its worst language.

**Step 2: use the app's own LLM as the translator.** Gemma's translations as the search query scored 0.84 overall, but the app was only using them for keyword search. Making Gemma work took three runs:

| Run | All 22 | Hindi | Spanish | French |
|---|---|---|---|---|
| 1. Gemma keywords → keyword search only | 0.74 | 0.85 | 0.60 | 0.72 |
| 2. Translate first; Gemma also detects the language | 0.65 | 0.76 | 0.47 | 0.72 |
| **3. A library detects the language** | **0.85** | 0.76 | 0.89 | 1.00 |

Run 2 failed because, asked whether a query was English, Gemma labelled every Spanish and French query as English and repeated it untranslated. Run 3 uses [lingua](https://github.com/pemistahl/lingua-py) (about 40 MB of RAM, 0.03 ms per query), limited to English, Spanish, French and Hindi. It labelled all 77 English eval queries English and all 22 others correctly.

**Remaining weak spots:** "काली जूती" (black jutti) → "black kurta", "बच्चों के कपड़े" (children's clothes), and "atuendo playero" → "playero outfit".

## 4. Should the LLM rewrite English queries?

The first Gemma run shortened English queries ("durable sandals for everyday wear" → "durable sandals"), which dropped useful words. Searching English queries with the user's own words, and using the LLM only for filters, raised English NDCG@10 from 0.770 to 0.794. For comparison, search with no LLM at all scored 0.795, so for English the LLM now does no harm and adds the filters.

## 5. Keyword matching strictness

Keyword search is the weak half of hybrid, so its matching rule was tuned against hybrid NDCG@10 (all with the same answer key):

| Rule | Hybrid NDCG@10 | Reports |
|---|---|---|
| Every query word must match | 0.806 | [`report_final_baseline_real`](reports/report_final_baseline_real.md) |
| Any word may match | 0.694 | [`report_keyword_or_fix`](reports/report_keyword_or_fix.md) |
| **At least 75% of words (in use)** | **0.825** | [`report_hybrid_coverage_075`](reports/report_hybrid_coverage_075.md) |

"Any word" lifted keyword search on its own but flooded hybrid with noise from long queries. In the app the rule relaxes to 50% inside a detected product type when nothing matches.

## 6. How trustworthy is the evaluation?

- **The first answer key was human-reviewed**, using the pooling method: the top results of every search method were pooled and then judged without showing which method found them ([pipeline](README.md)). It stopped working after a re-ingest changed product IDs, and runs against it now score 0.000.
- **Its replacement is derived from the embedding model's own top 20** per query. Vector search therefore scores near the ceiling by construction (NDCG@10 0.923), and keyword or hybrid hits a shopper would accept can be marked wrong.
- **For Hindi it is worse than biased:** the key is the model's top 20 for the Hindi text, so searching that text unchanged scores a perfect 1.000 and any translation scores lower, even a correct one. This is why the multilingual test in section 3 exists.
- **Small sample:** 80 queries, and each LLM changed hybrid results for fewer than 10 of them, so differences of about ±0.01 are indicative, not significant.

Because of this, the decisions in sections 1 to 4 lean on the written-rules multilingual test and per-query reading, and use the main eval mainly to check that English quality didn't drop.

## 7. Grounding LLM filters

- The LLM's output is forced into a JSON schema whose allowed values are the live catalogue's own, and any value not in the catalogue is dropped afterwards.
- TinyLlama's category guesses were dropped entirely (it labelled "saree" as Footwear). Its gender and season filters must also be mentioned in the query: 21 inferred filters were discarded this way in the eval (17 gender, 4 season).
- LLM-inferred filters apply to keyword search only, so a wrong guess can't hide good semantic matches. User-chosen filters always win.

## Not explored yet

- **Whether the vector index loses matches.** Vector Recall@20 is 0.71 against an answer key made of the embedding model's own top 20, which suggests approximate HNSW search (`ef_search = 40`) misses some. The cause is unconfirmed; the experiment is to raise `ef_search` and re-measure.
- **A larger LLM.** Gemma 3 4B (3.3 GB) doesn't fit next to the embedding model on this GPU.
- **A reranker** over the fused results.
- **A human-judged, pooled answer key** to replace the embedding-derived one (see section 6).
- **Using the feedback votes** the UI collects to evaluate or adjust ranking.
