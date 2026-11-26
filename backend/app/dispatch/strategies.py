"""三种调度策略（docs/06“优化”一节）。

输入 SupplyDemand，输出 DispatchPlanItem 列表：
    {source_id, destination_id, quantity, distance_m, route}
只生成计划，不扣库存；执行和原子校验由 A 负责。
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Mapping

import networkx as nx

from contracts.python_interfaces import NetworkError, NetworkPort

DTO = dict[str, Any]
ALGORITHMS = ("none", "greedy", "min_cost_flow")


@dataclass(frozen=True)
class Candidate:
    """一对可达的“供给站 -> 需求站”。"""
    source_id: str
    destination_id: str
    distance_m: float          # 原始米数，用于报告成本
    route: list                # 道路折线

    @property
    def cost(self) -> int:
        """优化用的整数米：floor(distance_m + 0.5)。"""
        return math.floor(self.distance_m + 0.5)


def read_supply_demand(supply_demand: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, int]]:
    """从 SupplyDemand 取出 supply>0 与 demand>0 的站点（新字典，不改输入）。"""
    supply: dict[str, int] = {}
    demand: dict[str, int] = {}
    for row in supply_demand["stations"]:
        if row["supply"] > 0:
            supply[row["station_id"]] = int(row["supply"])
        if row["demand"] > 0:
            demand[row["station_id"]] = int(row["demand"])
    return supply, demand


def collect_candidates(supply: Mapping[str, int], demand: Mapping[str, int],
                       network: NetworkPort) -> list[Candidate]:
    """查询所有供给站到需求站的道路；不可达的组合跳过。按 (源, 目的) 排序。"""
    candidates = []
    for source in sorted(supply):
        for destination in sorted(demand):
            if source == destination:
                continue
            try:
                route = network.route(source, destination)
            except NetworkError as exc:
                if exc.code == "UNREACHABLE":
                    continue
                raise
            candidates.append(Candidate(source, destination,
                                        float(route["distance_m"]), route["polyline"]))
    return candidates


def greedy_allocate(supply: Mapping[str, int], demand: Mapping[str, int],
                    candidates: list[Candidate], budget: int) -> dict[tuple[str, str], int]:
    """贪心：按 (距离, 源id, 目的id) 从近到远，每对分配 min(剩余供给, 剩余需求, 剩余预算)。

    不保证调度量最大，也不保证总成本最小。
    """
    left_supply = dict(supply)
    left_demand = dict(demand)
    allocation: dict[tuple[str, str], int] = {}
    for cand in sorted(candidates, key=lambda c: (c.distance_m, c.source_id, c.destination_id)):
        if budget <= 0:
            break
        quantity = min(left_supply[cand.source_id], left_demand[cand.destination_id], budget)
        if quantity <= 0:
            continue
        allocation[cand.source_id, cand.destination_id] = quantity
        left_supply[cand.source_id] -= quantity
        left_demand[cand.destination_id] -= quantity
        budget -= quantity
    return allocation


SUPER, SRC, SINK = "__super__", "__source__", "__sink__"


def min_cost_flow_allocate(supply: Mapping[str, int], demand: Mapping[str, int],
                           candidates: list[Candidate], budget: int) -> dict[tuple[str, str], int]:
    """最小费用流：先求最大调度量 F，再在流量为 F 时求整数米费用最小。

    图结构：SUPER -(容量=预算)-> SRC -(容量=供给)-> 供给站
            -(费用=整数米)-> 需求站 -(容量=需求)-> SINK
    """
    graph = nx.DiGraph()
    # 按固定顺序插入节点和边，保证并列最优时结果可复现
    graph.add_node(SUPER)
    graph.add_node(SRC)
    for source in sorted(supply):
        graph.add_node(("s", source))
    for destination in sorted(demand):
        graph.add_node(("d", destination))
    graph.add_node(SINK)

    graph.add_edge(SUPER, SRC, capacity=budget, weight=0)
    for source in sorted(supply):
        graph.add_edge(SRC, ("s", source), capacity=supply[source], weight=0)
    for cand in sorted(candidates, key=lambda c: (c.source_id, c.destination_id)):
        # 不设 capacity 表示容量不限
        graph.add_edge(("s", cand.source_id), ("d", cand.destination_id), weight=cand.cost)
    for destination in sorted(demand):
        graph.add_edge(("d", destination), SINK, capacity=demand[destination], weight=0)

    max_flow = nx.maximum_flow_value(graph, SUPER, SINK)
    if max_flow == 0:
        return {}

    graph.nodes[SUPER]["demand"] = -max_flow
    graph.nodes[SINK]["demand"] = max_flow
    _, flow = nx.network_simplex(graph)

    allocation: dict[tuple[str, str], int] = {}
    for cand in candidates:
        quantity = flow[("s", cand.source_id)][("d", cand.destination_id)]
        if quantity > 0:
            allocation[cand.source_id, cand.destination_id] = int(quantity)
    return allocation


def to_plan_items(allocation: Mapping[tuple[str, str], int],
                  candidates: list[Candidate]) -> list[DTO]:
    """把分配结果转成 DispatchPlanItem，按 (source_id, destination_id) 排序。"""
    by_pair = {(c.source_id, c.destination_id): c for c in candidates}
    items = []
    for (source, destination), quantity in sorted(allocation.items()):
        cand = by_pair[source, destination]
        items.append({
            "source_id": source,
            "destination_id": destination,
            "quantity": int(quantity),
            "distance_m": cand.distance_m,
            "route": [list(point) for point in cand.route],
        })
    return items


def plan(algorithm: str, supply_demand: Mapping[str, Any], network: NetworkPort,
         max_dispatch: int) -> list[DTO]:
    """按指定策略生成调度计划。"""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"未知调度算法: {algorithm}")
    if max_dispatch < 0:
        raise ValueError("max_dispatch 不能为负")
    if algorithm == "none":
        return []

    supply, demand = read_supply_demand(supply_demand)
    if not supply or not demand or max_dispatch == 0:
        return []
    candidates = collect_candidates(supply, demand, network)
    if algorithm == "greedy":
        allocation = greedy_allocate(supply, demand, candidates, max_dispatch)
    else:
        allocation = min_cost_flow_allocate(supply, demand, candidates, max_dispatch)
    return to_plan_items(allocation, candidates)
