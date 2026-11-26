"""批量实验统计（docs/06“批量”、docs/09 Metrics 口径）。

每个 (场景, 策略) 组对每个指标给出 {mean, stddev, n}：
- null 值排除，不当作 0；
- n 为有效样本数；n=0 时 mean 为 null；
- stddev 为样本标准差（除以 n-1），n<2 时为 null。
"""
from __future__ import annotations

import statistics
from typing import Any, Iterable, Mapping, Sequence

# 与 contracts/schema.json 中 Metrics 字段一致
METRIC_FIELDS = (
    "request_count", "borrow_success", "borrow_failed",
    "first_return_attempts", "first_return_success",
    "dispatch_quantity", "target_deviation",
    "unfinished_riding", "unfinished_waiting", "unfinished_transporting",
    "shortage_station_min", "full_station_min", "extra_ride_distance_m",
    "dispatch_cost_bike_m", "algorithm_compute_ms",
    "borrow_success_rate", "first_return_success_rate", "utilization",
)


def summarize(values: Iterable[Any]) -> dict[str, Any]:
    """对一组可能含 None 的数值求 {mean, stddev, n}。"""
    valid = [float(v) for v in values if v is not None]
    n = len(valid)
    mean = statistics.fmean(valid) if n >= 1 else None
    stddev = statistics.stdev(valid) if n >= 2 else None
    return {"mean": mean, "stddev": stddev, "n": n}


def aggregate(groups: Sequence[tuple[str, str]],
              summaries: Mapping[tuple[str, str], list[Mapping[str, Any]]]) -> list[dict[str, Any]]:
    """groups 给出输出顺序；summaries 为每组成功运行的 Metrics 列表（失败项不在其中）。

    即使某组全部失败也输出该组，所有指标 n=0。
    """
    result = []
    for scenario_id, algorithm in groups:
        rows = summaries.get((scenario_id, algorithm), [])
        result.append({
            "scenario_id": scenario_id,
            "algorithm": algorithm,
            "metrics": {field: summarize(row.get(field) for row in rows) for field in METRIC_FIELDS},
        })
    return result
