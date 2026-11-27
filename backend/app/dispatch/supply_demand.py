"""供需计算（fluid-v2）。

与 docs/06 的 v1 公式相比有两处改动（详见 docs/handoffs/B/dispatch-experiments.md）：

1. 目标库存按“需求水位曲线最低点”计算，而不是窗口总量 B-R：
       T = clip(floor(E + S_i - min_level + 0.5), 0, capacity)
   含义：要让窗口内库存最低的时刻仍留有 S_i 辆，现在需要多少车。
   v1 的 T = B-R+S 只看总量，“先借后还”的站会被误判为不缺车。

2. 每站安全库存 S_i 按泊松分布计算，而不是统一的常数：
       S_i = max(safety_stock, Q95(Poisson(B)) - B)
   Q95 为 95% 分位数；需求越大波动越大，留的余量越多。
   参数 safety_stock 作为下限保留；设为 0 即为纯泊松余量。

E、supply、demand 的定义不变：
    E = stock + reserved_inbound
    supply = min(stock, max(0, E - T))
    demand = min(capacity - stock - reserved_inbound, max(0, T - E))
纯函数，不修改输入。
"""
from __future__ import annotations

import math
from typing import Any, Iterable, Mapping

from .forecast import StationForecast

DTO = dict[str, Any]

ESTIMATOR_VERSION = "fluid-v2"
SERVICE_LEVEL = 0.95


def poisson_quantile(mean: float, level: float = SERVICE_LEVEL) -> int:
    """泊松分布的分位数：最小的 k，使 P(X <= k) >= level。"""
    if mean <= 0:
        return 0
    # 递推概率质量，避免大数阶乘；log 形式防止 exp(-mean) 下溢
    log_pmf = -mean
    cdf = math.exp(log_pmf)
    k = 0
    while cdf < level:
        k += 1
        log_pmf += math.log(mean) - math.log(k)
        cdf += math.exp(log_pmf)
    return k


def safety_buffer(expected_borrow: float, floor: int) -> float:
    """S_i = max(floor, Q95(Poisson(B)) - B)。"""
    if floor < 0:
        raise ValueError("safety_stock 不能为负")
    poisson_extra = poisson_quantile(expected_borrow) - expected_borrow
    return max(float(floor), poisson_extra)


def compute_target(effective_stock: float, min_level: float, buffer: float, capacity: int) -> int:
    """T = clip(floor(E + S_i - min_level + 0.5), 0, capacity)，半数向上取整。"""
    target = math.floor(effective_stock + buffer - min_level + 0.5)
    return max(0, min(target, capacity))


def station_supply_demand(station: Mapping[str, Any], fc: StationForecast, safety_stock: int) -> DTO:
    """计算单站的 SupplyDemand 条目。

    station 需要 id、capacity、stock、reserved_inbound（State.stations 中的元素）。
    """
    if fc.borrow < 0 or fc.returned < 0 or fc.served < 0:
        raise ValueError(f"{station['id']}: B/R/served 不能为负")
    if fc.served > fc.borrow + 1e-9:
        raise ValueError(f"{station['id']}: expected_served_borrow 不能大于 expected_borrow")

    capacity = int(station["capacity"])
    stock = int(station["stock"])
    reserved = int(station["reserved_inbound"])
    effective = stock + reserved

    buffer = safety_buffer(fc.borrow, safety_stock)
    target = compute_target(effective, fc.min_level, buffer, capacity)
    supply = min(stock, max(0, effective - target))
    free_capacity = max(0, capacity - stock - reserved)
    demand = min(free_capacity, max(0, target - effective))

    return {
        "station_id": station["id"],
        "expected_borrow": float(fc.borrow),
        "expected_served_borrow": float(min(fc.served, fc.borrow)),
        "expected_return": float(fc.returned),
        "target": target,
        "effective_stock": effective,
        "supply": supply,
        "demand": demand,
    }


def build_supply_demand(stations: Iterable[Mapping[str, Any]],
                        forecast: Mapping[str, StationForecast],
                        safety_stock: int, now_sec: int, horizon_sec: int) -> DTO:
    """组装完整 SupplyDemand。

    缺少预测的站视为无需求、无到达（最低点即当前有效库存）。
    只包含 active 站点，按 id 排序以保证输出稳定。
    """
    rows = []
    for station in sorted((s for s in stations if s.get("active", True)), key=lambda s: s["id"]):
        fc = forecast.get(station["id"])
        if fc is None:
            fc = StationForecast(0.0, 0.0, 0.0, float(station["stock"] + station["reserved_inbound"]))
        rows.append(station_supply_demand(station, fc, safety_stock))
    return {
        "estimator_version": ESTIMATOR_VERSION,
        "now_sec": int(now_sec),
        "horizon_sec": int(horizon_sec),
        "stations": rows,
    }
