"""供需计算（docs/06“供需”一节）。

把预测得到的 B（潜在借车）、R（预计归还）换算成每站的目标库存 T、
可调出量 supply 和需调入量 demand。纯函数，不修改输入。
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

DTO = dict[str, Any]

ESTIMATOR_VERSION = "fluid-v1"


def compute_target(expected_borrow: float, expected_return: float,
                   safety_stock: int, capacity: int) -> int:
    """T = clip(floor(max(0, B - R + S) + 0.5), 0, capacity)，半数向上取整。"""
    raw = max(0.0, expected_borrow - expected_return + safety_stock)
    target = math.floor(raw + 0.5)
    return max(0, min(target, capacity))


def station_supply_demand(station: Mapping[str, Any], expected_borrow: float,
                          expected_served_borrow: float, expected_return: float,
                          safety_stock: int) -> DTO:
    """计算单站的 SupplyDemand 条目。

    station 需要 id、capacity、stock、reserved_inbound（State.stations 中的元素）。
    E 用快照里的当前库存加在途预留，不是窗口末的预测库存。
    """
    if expected_borrow < 0 or expected_return < 0 or expected_served_borrow < 0:
        raise ValueError(f"{station['id']}: B/R/served 不能为负")
    if expected_served_borrow > expected_borrow + 1e-9:
        raise ValueError(f"{station['id']}: expected_served_borrow 不能大于 expected_borrow")
    if safety_stock < 0:
        raise ValueError("safety_stock 不能为负")

    capacity = int(station["capacity"])
    stock = int(station["stock"])
    reserved = int(station["reserved_inbound"])

    target = compute_target(expected_borrow, expected_return, safety_stock, capacity)
    effective = stock + reserved
    supply = min(stock, max(0, effective - target))
    free_capacity = max(0, capacity - stock - reserved)
    demand = min(free_capacity, max(0, target - effective))

    return {
        "station_id": station["id"],
        "expected_borrow": float(expected_borrow),
        "expected_served_borrow": float(min(expected_served_borrow, expected_borrow)),
        "expected_return": float(expected_return),
        "target": target,
        "effective_stock": effective,
        "supply": supply,
        "demand": demand,
    }


def build_supply_demand(stations: Iterable[Mapping[str, Any]],
                        forecast: Mapping[str, tuple[float, float, float]],
                        safety_stock: int, now_sec: int, horizon_sec: int) -> DTO:
    """组装完整 SupplyDemand。

    forecast: station_id -> (B, served, R)；缺省视为 (0, 0, 0)。
    只包含 active 站点，按 id 排序以保证输出稳定。
    """
    rows = []
    for station in sorted((s for s in stations if s.get("active", True)), key=lambda s: s["id"]):
        b, served, r = forecast.get(station["id"], (0.0, 0.0, 0.0))
        rows.append(station_supply_demand(station, b, served, r, safety_stock))
    return {
        "estimator_version": ESTIMATOR_VERSION,
        "now_sec": int(now_sec),
        "horizon_sec": int(horizon_sec),
        "stations": rows,
    }
