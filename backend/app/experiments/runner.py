"""批量实验编排（docs/06“批量”、docs/07 BatchResult）。

按 场景 × 策略 × 种子 的输入顺序逐项调用 A 注入的 run_once(RunSpec) -> RunOutcome。
单项失败记录 error、run_id=null 后继续；最后按 (场景, 策略) 汇总统计。
不访问数据库，也不自己创建引擎。
"""
from __future__ import annotations

import copy
from typing import Any, Mapping

from contracts.python_interfaces import DTO, OnProgress, RunOnce

from .stats import aggregate

ALGORITHMS = ("none", "greedy", "min_cost_flow")


class BatchRequestError(ValueError):
    """批量请求本身不合法（重复组合、触发时刻未对齐等），整批不执行。"""

    def __init__(self, message: str, details: dict | None = None):
        super().__init__(message)
        self.code = "INVALID_BATCH"
        self.details = details or {}


def _check_unique(name: str, values: list) -> None:
    if not values:
        raise BatchRequestError(f"{name} 不能为空", {"field": name})
    if len(set(values)) != len(values):
        raise BatchRequestError(f"{name} 含有重复值", {"field": name, "values": values})


def validate_request(request: Mapping[str, Any]) -> list[int]:
    """校验批量请求，返回排序后的调度触发时刻。"""
    _check_unique("scenario_ids", list(request["scenario_ids"]))
    _check_unique("algorithms", list(request["algorithms"]))
    _check_unique("seeds", list(request["seeds"]))
    unknown = [a for a in request["algorithms"] if a not in ALGORITHMS]
    if unknown:
        raise BatchRequestError(f"未知调度算法: {unknown}", {"field": "algorithms"})

    params = request["params"]
    step = int(params["step_sec"])
    duration = int(params["duration_min"]) * 60
    times = list(request["dispatch_times_sec"])
    if len(set(times)) != len(times):
        raise BatchRequestError("dispatch_times_sec 含有重复值", {"field": "dispatch_times_sec"})
    bad = [t for t in times if t < 0 or t >= duration or t % step != 0]
    if bad:
        raise BatchRequestError("调度时刻必须是 step 的整数倍且 0 <= t < 时长",
                                {"field": "dispatch_times_sec", "invalid": bad})
    return sorted(times)


def _error_of(exc: BaseException) -> DTO:
    code = getattr(exc, "code", None)
    details = getattr(exc, "details", None)
    return {
        "code": code if isinstance(code, str) and code else "RUN_FAILED",
        "message": str(exc) or type(exc).__name__,
        "details": details if isinstance(details, dict) else {"exception": type(exc).__name__},
    }


def _check_outcome(outcome: Any) -> None:
    if not isinstance(outcome, Mapping) or not isinstance(outcome.get("run_id"), str) \
            or not outcome["run_id"] or not isinstance(outcome.get("summary"), Mapping):
        raise ValueError("run_once 返回的 RunOutcome 缺少 run_id 或 summary")


def _final_status(items: list[DTO]) -> str:
    failed = sum(1 for item in items if item["status"] == "failed")
    if failed == 0:
        return "completed"
    if failed == len(items):
        return "failed"
    return "partial_failed"


class ExperimentRunner:
    def run_batch(self, request: DTO, run_once: RunOnce, on_progress: OnProgress) -> DTO:
        dispatch_times = validate_request(request)
        frozen_request = copy.deepcopy(request)

        combos = [(scenario_id, algorithm, seed)
                  for scenario_id in request["scenario_ids"]
                  for algorithm in request["algorithms"]
                  for seed in request["seeds"]]
        items = [{"scenario_id": s, "algorithm": a, "seed": seed, "status": "pending",
                  "run_id": None, "error": None} for s, a, seed in combos]
        result: DTO = {"id": request["request_id"], "status": "running", "total": len(items),
                       "finished": 0, "items": items, "aggregates": []}
        summaries: dict[tuple[str, str], list[Mapping[str, Any]]] = {}

        on_progress(copy.deepcopy(result))
        for item in items:
            item["status"] = "running"
            on_progress(copy.deepcopy(result))

            spec = {
                "batch_id": request["request_id"],
                "scenario_id": item["scenario_id"],
                "algorithm": item["algorithm"],
                "seed": item["seed"],
                "params": copy.deepcopy(request["params"]),
                "dispatch_times_sec": list(dispatch_times),
                "batch_request": copy.deepcopy(frozen_request),
            }
            try:
                outcome = run_once(spec)
                _check_outcome(outcome)
            except Exception as exc:  # 单项失败不影响后续组合
                item["status"] = "failed"
                item["run_id"] = None
                item["error"] = _error_of(exc)
            else:
                item["status"] = "completed"
                item["run_id"] = outcome["run_id"]
                key = (item["scenario_id"], item["algorithm"])
                summaries.setdefault(key, []).append(copy.deepcopy(outcome["summary"]))

            result["finished"] += 1
            if result["finished"] == result["total"]:
                result["status"] = _final_status(items)
                groups = [(s, a) for s in request["scenario_ids"] for a in request["algorithms"]]
                result["aggregates"] = aggregate(groups, summaries)
            on_progress(copy.deepcopy(result))

        return copy.deepcopy(result)
