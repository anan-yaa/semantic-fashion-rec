"""Pure helpers for the system-health load test: parse results, compute percentiles."""
from collections import Counter
from dataclasses import dataclass, field
from statistics import median
from typing import Dict, List, Optional

import numpy as np

PERCENTILES = (50, 95, 99)


@dataclass
class RequestResult:
    status: Optional[int]  # None when the request itself failed (timeout, connection error)
    latency_ms: float
    stages: Dict[str, float] = field(default_factory=dict)
    used_llm: Optional[bool] = None
    fallback_reason: Optional[str] = None
    error: Optional[str] = None

    @property
    def ok(self) -> bool:
        return self.status is not None and 200 <= self.status < 300


def parse_server_timing(header: Optional[str]) -> Dict[str, float]:
    """'llm;dur=312.4, embed;dur=21.0' -> {'llm': 312.4, 'embed': 21.0}. Ignores malformed parts."""
    stages: Dict[str, float] = {}
    for part in (header or "").split(","):
        name, _, params = part.strip().partition(";")
        for param in params.split(";"):
            key, _, value = param.strip().partition("=")
            if name and key == "dur":
                try:
                    stages[name] = float(value)
                except ValueError:
                    pass
    return stages


def percentiles(values: List[float]) -> Dict[str, float]:
    if not values:
        return {}
    arr = np.asarray(values, dtype=float)
    out = {f"p{p}": float(np.percentile(arr, p)) for p in PERCENTILES}
    out["max"] = float(arr.max())
    out["mean"] = float(arr.mean())
    return out


def summarize(results: List[RequestResult], wall_seconds: float) -> dict:
    """Latency percentiles, throughput, error and LLM fallback rates for one load-test run."""
    total = len(results)
    ok = [r for r in results if r.ok]
    stage_names = sorted({name for r in ok for name in r.stages})
    llm_known = [r for r in ok if r.used_llm is not None]
    return {
        "requests": total,
        "succeeded": len(ok),
        "error_rate": (total - len(ok)) / total if total else 0.0,
        "errors": dict(Counter(r.error or f"HTTP {r.status}" for r in results if not r.ok)),
        "throughput_rps": len(ok) / wall_seconds if wall_seconds > 0 else 0.0,
        "latency_ms": percentiles([r.latency_ms for r in ok]),
        "stages_ms": {name: percentiles([r.stages[name] for r in ok if name in r.stages]) for name in stage_names},
        "llm_used_rate": (sum(1 for r in llm_known if r.used_llm) / len(llm_known)) if llm_known else None,
        "llm_fallbacks": dict(Counter(r.fallback_reason for r in llm_known if not r.used_llm)),
    }


def median_of_runs(runs: List[dict], paths: List[List[str]]) -> Dict[str, Optional[float]]:
    """Median across repeated runs of the numeric values at each key path, e.g. ['latency_ms', 'p95']."""
    out: Dict[str, Optional[float]] = {}
    for path in paths:
        values = []
        for run in runs:
            value = run
            for key in path:
                value = value.get(key) if isinstance(value, dict) else None
            if isinstance(value, (int, float)):
                values.append(float(value))
        out[".".join(path)] = median(values) if values else None
    return out
