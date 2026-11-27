"""AC-B03：三策略。最小费用流与独立实现的暴力穷举对比。"""
import copy
import itertools
import math
import random

import pytest

from app.dispatch import DispatchService
from contracts.python_interfaces import NetworkError

from .helpers import make_network, make_supply_demand, schema_validator

service = DispatchService()


def total_quantity(plan):
    return sum(item["quantity"] for item in plan)


def total_cost(plan):
    """报告口径：数量 × 原始米数。"""
    return sum(item["quantity"] * item["distance_m"] for item in plan)


def int_cost(plan):
    """优化口径：数量 × floor(米 + 0.5)。"""
    return sum(item["quantity"] * math.floor(item["distance_m"] + 0.5) for item in plan)


# ---------- 暴力穷举（与被测算法分开实现） ----------

def brute_force(supply, demand, distances, budget):
    """枚举所有可行整数分配，返回 (最大调度量, 该调度量下的最小整数费用)。"""
    pairs = [(s, d) for s in supply for d in demand if s != d and (s, d) in distances]
    best = (0, 0)
    ranges = [range(min(supply[s], demand[d], budget) + 1) for s, d in pairs]
    for amounts in itertools.product(*ranges):
        used_s = {s: 0 for s in supply}
        used_d = {d: 0 for d in demand}
        for (s, d), q in zip(pairs, amounts):
            used_s[s] += q
            used_d[d] += q
        if any(used_s[s] > supply[s] for s in supply) or any(used_d[d] > demand[d] for d in demand):
            continue
        flow = sum(amounts)
        if flow > budget:
            continue
        cost = sum(q * math.floor(distances[p] + 0.5) for p, q in zip(pairs, amounts))
        if flow > best[0] or (flow == best[0] and cost < best[1]):
            best = (flow, cost)
    return best


def check_feasible(plan, supply, demand, budget):
    out, inn = {}, {}
    for item in plan:
        assert item["quantity"] >= 1
        out[item["source_id"]] = out.get(item["source_id"], 0) + item["quantity"]
        inn[item["destination_id"]] = inn.get(item["destination_id"], 0) + item["quantity"]
    assert all(out[s] <= supply.get(s, 0) for s in out)
    assert all(inn[d] <= demand.get(d, 0) for d in inn)
    assert total_quantity(plan) <= budget


# ---------- 讲解中的两个反例 ----------

def test_greedy_is_not_globally_optimal():
    """图书馆/体育馆各多 1 辆，宿舍/教学楼各缺 1 辆。"""
    supply = {"lib": 1, "gym": 1}
    demand = {"dorm": 1, "teach": 1}
    net = make_network({("lib", "dorm"): 100, ("lib", "teach"): 200,
                        ("gym", "dorm"): 200, ("gym", "teach"): 1000})
    sd = make_supply_demand(supply, demand)

    greedy = service.plan("greedy", sd, net, 50)
    mcf = service.plan("min_cost_flow", sd, net, 50)

    assert [(i["source_id"], i["destination_id"]) for i in greedy] == [("gym", "teach"), ("lib", "dorm")]
    assert total_cost(greedy) == 1100
    assert [(i["source_id"], i["destination_id"]) for i in mcf] == [("gym", "dorm"), ("lib", "teach")]
    assert total_cost(mcf) == 400


def test_greedy_can_move_fewer_bikes():
    """体育馆→教学楼不可达时，贪心只搬 1 辆，最小费用流搬 2 辆。"""
    supply = {"lib": 1, "gym": 1}
    demand = {"dorm": 1, "teach": 1}
    net = make_network({("lib", "dorm"): 100, ("lib", "teach"): 200, ("gym", "dorm"): 300})
    sd = make_supply_demand(supply, demand)

    assert total_quantity(service.plan("greedy", sd, net, 50)) == 1
    assert total_quantity(service.plan("min_cost_flow", sd, net, 50)) == 2


# ---------- 与穷举对比 ----------

def random_instance(rng):
    sources = [f"a{i}" for i in range(rng.randint(1, 3))]
    sinks = [f"b{i}" for i in range(rng.randint(1, 3))]
    supply = {s: rng.randint(1, 3) for s in sources}
    demand = {d: rng.randint(1, 3) for d in sinks}
    distances = {}
    for s in sources:
        for d in sinks:
            if rng.random() < 0.8:  # 约 20% 不可达
                # 非整数米，并刻意制造并列
                distances[s, d] = rng.choice([50, 100, 100, 150.4, 150.6, 200, 99.5])
    budget = rng.choice([0, 1, 2, 3, 5, 50])
    return supply, demand, distances, budget


@pytest.mark.parametrize("seed", range(200))
def test_min_cost_flow_matches_brute_force(seed):
    supply, demand, distances, budget = random_instance(random.Random(seed))
    plan = service.plan("min_cost_flow", make_supply_demand(supply, demand),
                        make_network(distances), budget)
    check_feasible(plan, supply, demand, budget)
    assert (total_quantity(plan), int_cost(plan)) == brute_force(supply, demand, distances, budget)


@pytest.mark.parametrize("seed", range(200))
def test_greedy_feasible_and_never_beats_optimum(seed):
    supply, demand, distances, budget = random_instance(random.Random(seed))
    plan = service.plan("greedy", make_supply_demand(supply, demand),
                        make_network(distances), budget)
    check_feasible(plan, supply, demand, budget)
    best_flow, best_cost = brute_force(supply, demand, distances, budget)
    assert total_quantity(plan) <= best_flow
    if total_quantity(plan) == best_flow:
        assert int_cost(plan) >= best_cost


# ---------- 边界 ----------

@pytest.mark.parametrize("algorithm", ["none", "greedy", "min_cost_flow"])
def test_budget_zero_and_empty_inputs(algorithm):
    net = make_network({("a", "b"): 100})
    assert service.plan(algorithm, make_supply_demand({"a": 3}, {"b": 3}), net, 0) == []
    assert service.plan(algorithm, make_supply_demand({}, {"b": 3}), net, 50) == []
    assert service.plan(algorithm, make_supply_demand({"a": 3}, {}), net, 50) == []


def test_none_always_empty():
    net = make_network({("a", "b"): 100})
    assert service.plan("none", make_supply_demand({"a": 3}, {"b": 3}), net, 50) == []


@pytest.mark.parametrize("algorithm", ["greedy", "min_cost_flow"])
def test_budget_limits_total(algorithm):
    net = make_network({("a", "c"): 100, ("b", "c"): 50})
    plan = service.plan(algorithm, make_supply_demand({"a": 5, "b": 5}, {"c": 10}), net, 3)
    assert total_quantity(plan) == 3
    assert plan == [{"source_id": "b", "destination_id": "c", "quantity": 3,
                     "distance_m": 50.0, "route": [[0, 0], [1, 1]]}]


@pytest.mark.parametrize("algorithm", ["greedy", "min_cost_flow"])
def test_all_unreachable(algorithm):
    assert service.plan(algorithm, make_supply_demand({"a": 3}, {"b": 3}), make_network({}), 50) == []


def test_reports_raw_meters_and_schema_valid():
    net = make_network({("a", "b"): 120.4, ("a", "c"): 80.6})
    sd = make_supply_demand({"a": 4}, {"b": 2, "c": 2})
    validator = schema_validator("DispatchPlanItem")
    for algorithm in ["greedy", "min_cost_flow"]:
        plan = service.plan(algorithm, sd, net, 50)
        for item in plan:
            validator.validate(item)
        assert {i["destination_id"]: i["distance_m"] for i in plan} == {"b": 120.4, "c": 80.6}
        assert total_cost(plan) == pytest.approx(2 * 120.4 + 2 * 80.6)


@pytest.mark.parametrize("algorithm", ["greedy", "min_cost_flow"])
def test_tie_is_reproducible_and_sorted(algorithm):
    """两个供给站距离相同（并列最优），多次运行结果一致且按 (源, 目的) 排序。"""
    net = make_network({("a", "c"): 100, ("b", "c"): 100})
    sd = make_supply_demand({"a": 2, "b": 2}, {"c": 2})
    plans = [service.plan(algorithm, sd, net, 50) for _ in range(5)]
    assert all(p == plans[0] for p in plans)
    assert plans[0] == sorted(plans[0], key=lambda i: (i["source_id"], i["destination_id"]))
    assert total_quantity(plans[0]) == 2


@pytest.mark.parametrize("algorithm", ["greedy", "min_cost_flow"])
def test_does_not_mutate_input(algorithm):
    sd = make_supply_demand({"a": 3}, {"b": 2})
    before = copy.deepcopy(sd)
    service.plan(algorithm, sd, make_network({("a", "b"): 100}), 50)
    assert sd == before


def test_unknown_algorithm_and_negative_budget():
    sd = make_supply_demand({"a": 1}, {"b": 1})
    net = make_network({("a", "b"): 100})
    with pytest.raises(ValueError):
        service.plan("random", sd, net, 50)
    with pytest.raises(ValueError):
        service.plan("greedy", sd, net, -1)


def test_other_network_errors_propagate():
    class BrokenNetwork:
        def route(self, source_id, destination_id):
            raise NetworkError("INVALID_STATION", "bad")

    with pytest.raises(NetworkError):
        service.plan("greedy", make_supply_demand({"a": 1}, {"b": 1}), BrokenNetwork(), 50)
