"""Search evaluation: pooled labeling + NDCG@10/Precision@10/MRR scoring."""
from app.services.eval.pooling import build_pool, build_and_save_pool, PoolBuildStats
from app.services.eval.runner import run_eval, run_and_save_eval
from app.services.eval.io import (
    QuerySetEntry,
    PoolCandidate,
    PoolEntry,
    GroundTruthCandidate,
    GroundTruthEntry,
    MethodScores,
    EvalReport,
    load_query_set,
    save_pool,
    load_pool,
    save_ground_truth,
    load_ground_truth,
    save_report,
)

__all__ = [
    "build_pool",
    "build_and_save_pool",
    "PoolBuildStats",
    "run_eval",
    "run_and_save_eval",
    "QuerySetEntry",
    "PoolCandidate",
    "PoolEntry",
    "GroundTruthCandidate",
    "GroundTruthEntry",
    "MethodScores",
    "EvalReport",
    "load_query_set",
    "save_pool",
    "load_pool",
    "save_ground_truth",
    "load_ground_truth",
    "save_report",
]
