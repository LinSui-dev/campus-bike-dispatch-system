"""AC-B04：批量组合、失败继续、统计口径。run_once 用测试替身，不创建真实 DB。"""
import copy
import json
import statistics

import pytest

from app.experiments import ExperimentRunner
from app.experiments.runner import BatchRequestError
from app.experiments.stats import METRIC_FIELDS, summarize

from .helpers import ROOT, schema_validator

BASE_REQUEST = json.loads((ROOT / "contracts/examples/batch_request.json").read_text(encoding="utf-8"))


def make_request(scenarios=("morning", "lunch"), algorithms=("none", "greedy", "min_cost_flow"),
                 seeds=(42, 43), times=(0, 900)):
    req = copy.deepcopy(BASE_REQUEST)
    req.update(request_id="batch-test", scenario_ids=list(scenarios), algorithms=list(algorithms),
               seeds=list(seeds), dispatch_times_sec=list(times))
    return req


def make_metrics(**overrides):
    m = {f: 0 for f in METRIC_FIELDS}
    m.update(borrow_success_rate=None, first_return_success_rate=None, utilization=None)
    m.update(overrides)
    return m


class FakeRunOnce:
    """记录每次收到的 RunSpec；fail 中的组合抛异常；metrics_fn 决定返回的指标。"""

    def __init__(self, fail=(), metrics_fn=None):
        self.calls = []
        self.fail = set(fail)
        self.metrics_fn = metrics_fn or (lambda spec: make_metrics(request_count=spec["seed"]))

    def __call__(self, spec):
        self.calls.append(copy.deepcopy(spec))
        key = (spec["scenario_id"], spec["algorithm"], spec["seed"])
        spec["params"]["step_sec"] = 999          # 故意篡改，检查下一项会重建
        spec["batch_request"]["seeds"].clear()
        if key in self.fail:
            raise RuntimeError(f"boom {key}")
        return {"run_id": "run-{}-{}-{}".format(*key), "summary": self.metrics_fn(spec)}


def run(request, run_once):
    events = []
    result = ExperimentRunner().run_batch(request, run_once, events.append)
    return result, events


def test_twelve_items_one_failure_continues():
    request = make_request()
    before = copy.deepcopy(request)
    fake = FakeRunOnce(fail={("lunch", "greedy", 42)})
    result, events = run(request, fake)

    expected_order = [(s, a, seed) for s in ["morning", "lunch"]
                      for a in ["none", "greedy", "min_cost_flow"] for seed in [42, 43]]
    # 每项恰好执行一次，顺序稳定
    assert [(c["scenario_id"], c["algorithm"], c["seed"]) for c in fake.calls] == expected_order
    assert [(i["scenario_id"], i["algorithm"], i["seed"]) for i in result["items"]] == expected_order

    assert result["total"] == 12 and result["finished"] == 12
    assert result["status"] == "partial_failed"
    failed = [i for i in result["items"] if i["status"] == "failed"]
    assert len(failed) == 1
    assert failed[0]["run_id"] is None
    assert failed[0]["error"]["code"] == "RUN_FAILED" and "boom" in failed[0]["error"]["message"]
    ok = [i for i in result["items"] if i["status"] == "completed"]
    assert all(i["run_id"] and i["error"] is None for i in ok)

    # 失败项不进统计：lunch+greedy 只剩 seed 43
    agg = {(a["scenario_id"], a["algorithm"]): a["metrics"] for a in result["aggregates"]}
    assert agg["lunch", "greedy"]["request_count"] == {"mean": 43.0, "stddev": None, "n": 1}
    assert agg["morning", "none"]["request_count"] == {
        "mean": 42.5, "stddev": pytest.approx(statistics.stdev([42, 43])), "n": 2}

    assert request == before  # 不修改输入
    schema_validator("BatchResult").validate(result)


def test_each_spec_is_rebuilt_and_schema_valid():
    request = make_request()
    fake = FakeRunOnce()
    run(request, fake)
    validator = schema_validator("RunSpec")
    for spec in fake.calls:
        validator.validate(spec)
        assert spec["batch_id"] == "batch-test"
        assert spec["params"] == BASE_REQUEST["params"]       # 上一项的篡改没有传过来
        assert spec["batch_request"]["seeds"] == [42, 43]
        assert spec["dispatch_times_sec"] == [0, 900]


def test_progress_events():
    result, events = run(make_request(), FakeRunOnce(fail={("morning", "none", 43)}))
    validator = schema_validator("BatchResult")
    for e in events:
        validator.validate(e)
    first = events[0]
    assert first["status"] == "running" and first["finished"] == 0
    assert all(i["status"] == "pending" for i in first["items"])
    assert events[1]["items"][0]["status"] == "running"
    finished = [e["finished"] for e in events]
    assert finished == sorted(finished)
    assert all(e["status"] == "running" for e in events[:-1])
    assert events[-1] == result
    assert len(events) == 1 + 2 * 12   # 开始一次 + 每项开始、结束各一次


def test_all_success_and_all_failed():
    req = make_request(scenarios=["morning"], algorithms=["none"], seeds=[1, 2])
    assert run(req, FakeRunOnce())[0]["status"] == "completed"
    failed, _ = run(req, FakeRunOnce(fail={("morning", "none", 1), ("morning", "none", 2)}))
    assert failed["status"] == "failed"
    metrics = failed["aggregates"][0]["metrics"]
    assert metrics["request_count"] == {"mean": None, "stddev": None, "n": 0}


def test_null_excluded_not_treated_as_zero():
    rates = {42: 0.8, 43: None, 44: 0.6}
    req = make_request(scenarios=["morning"], algorithms=["greedy"], seeds=[42, 43, 44])
    fake = FakeRunOnce(metrics_fn=lambda spec: make_metrics(borrow_success_rate=rates[spec["seed"]]))
    result, _ = run(req, fake)
    stat = result["aggregates"][0]["metrics"]["borrow_success_rate"]
    assert stat["n"] == 2
    assert stat["mean"] == pytest.approx(0.7)
    assert stat["stddev"] == pytest.approx(statistics.stdev([0.8, 0.6]))


@pytest.mark.parametrize("values,expected", [
    ([], {"mean": None, "stddev": None, "n": 0}),
    ([None, None], {"mean": None, "stddev": None, "n": 0}),
    ([5], {"mean": 5.0, "stddev": None, "n": 1}),
    ([2, 4, 4, 4, 5, 5, 7, 9], {"mean": 5.0, "stddev": pytest.approx(2.138089935), "n": 8}),  # 样本标准差
    ([0, None, 0], {"mean": 0.0, "stddev": 0.0, "n": 2}),
])
def test_summarize_hand_values(values, expected):
    assert summarize(values) == expected


def test_invalid_outcome_becomes_failed_item():
    req = make_request(scenarios=["morning"], algorithms=["none"], seeds=[1])
    result, _ = run(req, lambda spec: {"summary": make_metrics()})
    assert result["items"][0]["status"] == "failed"
    assert result["items"][0]["run_id"] is None


def test_error_code_from_exception_is_kept():
    class CodedError(Exception):
        code = "ENGINE_ERROR"
        details = {"step": 3}

    def run_once(spec):
        raise CodedError("engine crashed")

    req = make_request(scenarios=["morning"], algorithms=["none"], seeds=[1])
    item = run(req, run_once)[0]["items"][0]
    assert item["error"] == {"code": "ENGINE_ERROR", "message": "engine crashed", "details": {"step": 3}}


@pytest.mark.parametrize("change", [
    {"seeds": [42, 42]},
    {"scenario_ids": ["morning", "morning"]},
    {"algorithms": ["greedy", "greedy"]},
    {"algorithms": ["random"]},
    {"seeds": []},
    {"dispatch_times_sec": [30]},        # 未对齐 step=60
    {"dispatch_times_sec": [7200]},      # 等于时长
    {"dispatch_times_sec": [-60]},
    {"dispatch_times_sec": [0, 0]},
])
def test_invalid_request_rejected_without_running(change):
    req = make_request()
    req.update(change)
    fake = FakeRunOnce()
    events = []
    with pytest.raises(BatchRequestError):
        ExperimentRunner().run_batch(req, fake, events.append)
    assert fake.calls == [] and events == []


def test_dispatch_times_sorted_in_spec():
    req = make_request(scenarios=["morning"], algorithms=["none"], seeds=[1], times=[1800, 0, 900])
    fake = FakeRunOnce()
    run(req, fake)
    assert fake.calls[0]["dispatch_times_sec"] == [0, 900, 1800]


def test_default_sixty_combinations():
    fake = FakeRunOnce()
    result, _ = run(copy.deepcopy(BASE_REQUEST), fake)
    assert result["total"] == 60 and len(fake.calls) == 60
    assert len(result["aggregates"]) == 12
    assert result["status"] == "completed"
