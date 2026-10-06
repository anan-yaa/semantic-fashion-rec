# Eval Report (2026-10-06T04:08:41.733263+00:00)

Ground truth: `evals/ground_truth/ground_truth_v2_real.json`  
Queries scored: 80 (excluded for having zero relevant items: 0)
Query understanding enabled: True

| Method  | NDCG@10 | Precision@10 | MRR   | MRR@10 | Recall@10 | Recall@20 | Recall@50 |
|---------|---------|--------------|-------|--------|-----------|-----------|-----------|
| hybrid  | 0.832   | 0.731        | 0.931 | 0.931  | 0.366     | 0.594     | 0.704     |
| vector  | 0.923   | 0.841        | 0.925 | 0.925  | 0.421     | 0.713     | 0.719     |
| keyword | 0.267   | 0.171        | 0.344 | 0.337  | 0.086     | 0.144     | 0.241     |
