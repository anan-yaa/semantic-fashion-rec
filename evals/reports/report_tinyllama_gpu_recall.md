# Eval Report (2026-10-05T16:18:30.912072+00:00)

Ground truth: `evals/ground_truth/ground_truth_v2_real.json`  
Queries scored: 80 (excluded for having zero relevant items: 0)
Query understanding enabled: True

| Method  | NDCG@10 | Precision@10 | MRR   | Recall@20 | Recall@50 |
|---------|---------|--------------|-------|-----------|-----------|
| hybrid  | 0.831   | 0.731        | 0.931 | 0.594     | 0.705     |
| vector  | 0.923   | 0.841        | 0.925 | 0.713     | 0.719     |
| keyword | 0.272   | 0.176        | 0.353 | 0.148     | 0.252     |
