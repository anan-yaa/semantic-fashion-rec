"""Typed load/save helpers for every eval pipeline JSON file.

Centralizing the schemas here (instead of parsing JSON ad hoc in each
script) means a field rename or schema change only needs to happen in one
place.
"""
import json
from dataclasses import asdict, dataclass, field


@dataclass
class QuerySetEntry:
    id: str
    query: str
    category_tag: str


def load_query_set(path: str) -> list[QuerySetEntry]:
    with open(path) as f:
        data = json.load(f)
    return [QuerySetEntry(**q) for q in data["queries"]]


@dataclass
class PoolCandidate:
    product_id: str
    external_product_id: str
    name: str
    category: str | None
    subcategory: str | None
    gender: str | None
    color: str | None
    season: str | None
    search_text: str | None
    found_by: list[str]
    pre_label: int | None = None
    pre_label_rationale: str | None = None


@dataclass
class PoolEntry:
    query_id: str
    query: str
    candidates: list[PoolCandidate]


def save_pool(path: str, pools: list[PoolEntry], source_query_set: str, k_per_method: int, built_at: str) -> None:
    data = {
        "version": 1,
        "source_query_set": source_query_set,
        "k_per_method": k_per_method,
        "built_at": built_at,
        "pools": [
            {
                "query_id": p.query_id,
                "query": p.query,
                "candidates": [asdict(c) for c in p.candidates],
            }
            for p in pools
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_pool(path: str) -> list[PoolEntry]:
    with open(path) as f:
        data = json.load(f)
    return [
        PoolEntry(
            query_id=p["query_id"],
            query=p["query"],
            candidates=[PoolCandidate(**c) for c in p["candidates"]],
        )
        for p in data["pools"]
    ]


@dataclass
class GroundTruthCandidate:
    product_id: str
    relevance: int
    pre_label: int | None
    human_flipped: bool


@dataclass
class GroundTruthEntry:
    query_id: str
    query: str
    relevant_product_ids: list[str]
    all_candidates: list[GroundTruthCandidate] = field(default_factory=list)


def save_ground_truth(path: str, judgments: list[GroundTruthEntry], source_pool: str, labeled_at: str) -> None:
    data = {
        "version": 1,
        "source_pool": source_pool,
        "labeled_at": labeled_at,
        "judgments": [
            {
                "query_id": j.query_id,
                "query": j.query,
                "relevant_product_ids": j.relevant_product_ids,
                "all_candidates": [asdict(c) for c in j.all_candidates],
            }
            for j in judgments
        ],
    }
    with open(path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def load_ground_truth(path: str) -> list[GroundTruthEntry]:
    with open(path) as f:
        data = json.load(f)
    return [
        GroundTruthEntry(
            query_id=j["query_id"],
            query=j["query"],
            relevant_product_ids=j["relevant_product_ids"],
            all_candidates=[GroundTruthCandidate(**c) for c in j.get("all_candidates", [])],
        )
        for j in data["judgments"]
    ]


@dataclass
class MethodScores:
    ndcg_at_10: float
    precision_at_10: float
    mrr: float
    mrr_at_10: float = 0.0
    recall_at_10: float = 0.0
    recall_at_20: float = 0.0
    recall_at_50: float = 0.0


@dataclass
class QueryUnderstandingRecord:
    """One query's LLM query-understanding outcome, recorded only when
    run_eval() was given an llm_provider. Lets a report be analyzed for
    Gemini reliability (successes/failures/fallbacks) and per-query effect
    without re-running anything.
    """

    query_id: str
    query: str
    used_llm: bool
    cleaned_query: str
    filters: dict
    error: str | None = None
    translated: bool = False


@dataclass
class EvalReport:
    generated_at: str
    ground_truth_source: str
    query_count: int
    excluded_query_count: int
    per_method: dict  # method name -> MethodScores
    per_query: dict  # query_id -> {method name -> MethodScores}
    query_understanding_enabled: bool = False
    query_understanding: list[QueryUnderstandingRecord] = field(default_factory=list)


def save_report(json_path: str, md_path: str, report: EvalReport) -> None:
    data = {
        "generated_at": report.generated_at,
        "ground_truth_source": report.ground_truth_source,
        "query_count": report.query_count,
        "excluded_query_count": report.excluded_query_count,
        "per_method": {m: asdict(s) for m, s in report.per_method.items()},
        "per_query": {
            qid: {m: asdict(s) for m, s in methods.items()}
            for qid, methods in report.per_query.items()
        },
        "query_understanding_enabled": report.query_understanding_enabled,
        "query_understanding": [asdict(r) for r in report.query_understanding],
    }
    with open(json_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    lines = [
        f"# Eval Report ({report.generated_at})",
        "",
        f"Ground truth: `{report.ground_truth_source}`  ",
        f"Queries scored: {report.query_count} (excluded for having zero relevant items: {report.excluded_query_count})",
        f"Query understanding enabled: {report.query_understanding_enabled}",
        "",
        "| Method  | NDCG@10 | Precision@10 | MRR   | MRR@10 | Recall@10 | Recall@20 | Recall@50 |",
        "|---------|---------|--------------|-------|--------|-----------|-----------|-----------|",
    ]
    for method in ("hybrid", "vector", "keyword"):
        if method in report.per_method:
            s = report.per_method[method]
            lines.append(
                f"| {method:<7} | {s.ndcg_at_10:.3f}   | {s.precision_at_10:.3f}        | {s.mrr:.3f} "
                f"| {s.mrr_at_10:.3f}  | {s.recall_at_10:.3f}     | {s.recall_at_20:.3f}     | {s.recall_at_50:.3f}     |"
            )
    with open(md_path, "w") as f:
        f.write("\n".join(lines) + "\n")
