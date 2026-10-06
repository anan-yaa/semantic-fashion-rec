# Eval Report (2026-10-06T12:18:42.121589+00:00)

Ground truth: `evals/ground_truth/ground_truth_v2_real.json`  
Queries scored: 80 (excluded for having zero relevant items: 0)
Query understanding enabled: True

| Method  | NDCG@10 | Precision@10 | MRR   | MRR@10 | Recall@10 | Recall@20 | Recall@50 |
|---------|---------|--------------|-------|--------|-----------|-----------|-----------|
| hybrid  | 0.727   | 0.622        | 0.842 | 0.842  | 0.311     | 0.501     | 0.622     |
| vector  | 0.827   | 0.741        | 0.838 | 0.838  | 0.371     | 0.626     | 0.633     |
| keyword | 0.316   | 0.189        | 0.394 | 0.389  | 0.094     | 0.158     | 0.264     |
