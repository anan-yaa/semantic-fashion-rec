# Search evaluation pipeline

Measures hybrid vs. vector vs. keyword search quality (NDCG@10, Precision@10, MRR)
against a human-reviewed ground-truth query set, built via the pooling method.

## Pipeline

```
evals/queries/query_set_v1.json
  -> python -m scripts.build_eval_pool --query-set evals/queries/query_set_v1.json \
         --output evals/pools/pool_v1.json --k-per-method 20
evals/pools/pool_v1.json          (pre_label: null for every candidate)
  -> pre-labeling pass: every candidate's pre_label/pre_label_rationale filled in
     by reading product attributes (name/category/subcategory/color/gender/season/
     search_text) against the query text. Deliberately NEVER reads `found_by`
     (which method(s) retrieved the candidate) when judging relevance - a method
     must not get credit just because it retrieved something. `found_by` exists
     only for post-hoc audit after labels are final.
evals/pools/pool_v1.json          (pre_label filled in)
  -> python -m scripts.label_eval_pool --pool evals/pools/pool_v1.json \
         --output evals/ground_truth/ground_truth_v1.json
     Interactive: review/accept/flip every pre-label. Also never shown `found_by`,
     for the same reason. Resumable (Ctrl-C / [q]uit saves progress to
     <output>.partial; re-run with --resume to continue).
evals/ground_truth/ground_truth_v1.json
  -> python -m scripts.run_eval --ground-truth evals/ground_truth/ground_truth_v1.json \
         --output-prefix evals/reports/report_$(date +%Y%m%d_%H%M%S) --k 10
evals/reports/report_<timestamp>.json + .md
```

## Relevance scale

Binary: 1 = relevant, 0 = not relevant. A product never pooled for a given query
is implicitly 0 (standard pooling-method assumption - it's infeasible to judge
all 44k products per query, so only the union of what the 3 methods actually
retrieved gets judged).

## Metrics

- **NDCG@10**: ranking quality, position-aware. 0.0 for a query with no relevant
  items in the pool at all (rather than NaN) - such queries are excluded from the
  aggregate mean, since NDCG is undefined there, not just low.
- **Precision@10**: fraction of the top 10 results that are relevant. A method
  returning fewer than 10 results is NOT given a smaller denominator - the
  missing slots count as non-relevant, so returning less never scores higher.
- **MRR**: 1 / rank of the first relevant result, averaged across queries.

All three computed per query per method, then averaged (mean) per method across
the query set for side-by-side comparison. Implementation: `app/services/eval/metrics.py`
(pure numpy, no scikit-learn dependency).

## Versioning

Files are suffixed `_v1` because the query set and ground truth will be revised
over time (new queries, corrected labels) without being confused with stale
files. `run_eval.py` always takes an explicit `--ground-truth` path - there is
no "latest" symlink/default, so which dataset a report came from is always
explicit in the command that produced it.

## Query set composition

`evals/queries/query_set_v1.json` has 80 queries across 8 categories (10 each,
except keyword_heavy/semantic at 12 and gender/vague at 8), grounded in the
catalogue's real facet distributions (44,072 products): category (7 values),
gender (5), season (4), color (46), subcategory (45). `brand` and `material`
are empty for every product in this dataset and are not used as query facets.
Multilingual queries are Hindi, short noun phrases (matching the pattern already
proven to work well for the E5 model in `scripts/verify_e5_model.py` and
`tests/model/test_e5_real.py`, rather than untested longer sentences).

## Smoke-testing before a full run

Before running the full 80-query pipeline (which means ~1500-3000 individual
pre-label judgments and the same number of human review decisions), verify the
tooling itself on a handful of hand-picked queries first: copy 3-5 entries into
a throwaway `evals/queries/smoke_test.json`, run the pipeline above against it,
confirm `label_eval_pool.py`'s accept/flip/skip/quit/--resume all work as
expected and `run_eval.py` prints a sane 3-row table. Delete the smoke-test
scratch files afterward - they are not part of the versioned dataset.
