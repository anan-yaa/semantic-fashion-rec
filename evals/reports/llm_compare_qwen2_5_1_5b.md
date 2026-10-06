# Eval Report (2026-10-06T07:24:43.818833+00:00)

Ground truth: `evals/ground_truth/ground_truth_v2_real.json`  
Queries scored: 80 (excluded for having zero relevant items: 0)
Query understanding enabled: True

| Method  | NDCG@10 | Precision@10 | MRR   | MRR@10 | Recall@10 | Recall@20 | Recall@50 |
|---------|---------|--------------|-------|--------|-----------|-----------|-----------|
| hybrid  | 0.748   | 0.662        | 0.891 | 0.891  | 0.331     | 0.559     | 0.709     |
| vector  | 0.923   | 0.841        | 0.925 | 0.925  | 0.421     | 0.713     | 0.719     |
| keyword | 0.283   | 0.164        | 0.347 | 0.341  | 0.082     | 0.133     | 0.224     |
