"""Search evaluation: pooled labeling + NDCG@10/Precision@10/MRR scoring."""
from app.services.eval.io import (
    EvalReport,
    GroundTruthCandidate,
    GroundTruthEntry,
    MethodScores,
    PoolCandidate,
    PoolEntry,
    QuerySetEntry,
    QueryUnderstandingRecord,
    load_ground_truth,
    load_pool,
    load_query_set,
    save_ground_truth,
    save_pool,
    save_report,
)
from app.services.eval.pooling import PoolBuildStats, build_and_save_pool, build_pool
from app.services.eval.runner import run_and_save_eval, run_eval

__all__ = [
    "EvalReport",
    "GroundTruthCandidate",
    "GroundTruthEntry",
    "MethodScores",
    "PoolBuildStats",
    "PoolCandidate",
    "PoolEntry",
    "QuerySetEntry",
    "QueryUnderstandingRecord",
    "build_and_save_pool",
    "build_pool",
    "load_ground_truth",
    "load_pool",
    "load_query_set",
    "run_and_save_eval",
    "run_eval",
    "save_ground_truth",
    "save_pool",
    "save_report",
]
