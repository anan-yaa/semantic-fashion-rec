# Eval Report (2026-10-06T04:10:10.395323+00:00)

Ground truth: `evals/ground_truth/ground_truth_v2_real.json`  
Queries scored: 80 (excluded for having zero relevant items: 0)
Query understanding enabled: False

| Method  | NDCG@10 | Precision@10 | MRR   | MRR@10 | Recall@10 | Recall@20 | Recall@50 |
|---------|---------|--------------|-------|--------|-----------|-----------|-----------|
| hybrid  | 0.820   | 0.720        | 0.925 | 0.925  | 0.360     | 0.585     | 0.706     |
| vector  | 0.923   | 0.841        | 0.925 | 0.925  | 0.421     | 0.713     | 0.719     |
| keyword | 0.309   | 0.189        | 0.385 | 0.380  | 0.094     | 0.154     | 0.259     |
