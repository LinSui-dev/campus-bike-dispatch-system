"""AC-B02：供需公式（fluid-v2）的手算基准与边界。

T = clip(floor(E + S_i - min_level + 0.5), 0, capacity)
S_i = max(safety_stock, Q95(Poisson(B)) - B)
"""
import copy

import pytest

from app.dispatch.forecast import StationForecast
from app.dispatch.supply_demand import (build_supply_demand, compute_target, poisson_quantile,
                                        safety_buffer, station_supply_demand)

from .helpers import make_station, schema_validator


@pytest.mark.parametrize("mean,expected", [
    (0, 0), (0.5, 2), (1, 3), (2, 5), (2.5, 5), (9, 14), (10, 15), (20, 28), (50, 62),
])
def test_poisson_quantile_table(mean, expected):
    """查表值：最小 k 使 P(X<=k) >= 0.95。"""
    assert poisson_quantile(mean) == expected


def test_poisson_quantile_large_mean_does_not_overflow():
    assert 220 <= poisson_quantile(200) <= 225


@pytest.mark.parametrize("b,floor,expected", [
    (0, 5, 5.0),      # 无需求：用下限
    (9, 5, 5.0),      # 14-9=5
    (20, 5, 8.0),     # 28-20=8 > 下限
    (2.5, 0, 2.5),    # 下限 0：纯泊松余量
    (0, 0, 0.0),
])
def test_safety_buffer(b, floor, expected):
    assert safety_buffer(b, floor) == pytest.approx(expected)


def test_negative_floor_rejected():
    with pytest.raises(ValueError):
        safety_buffer(1, -1)


@pytest.mark.parametrize("E,min_level,S,cap,expected", [
    (3, -6, 5, 20, 14),     # 讲解例子：宿舍
    (15, 15, 5, 20, 5),     # 只进不出：保留 S
    (10, -10, 8, 30, 28),   # 先借后还
    (10, -30, 5, 20, 20),   # 超过容量 → 截到 capacity
    (10, 20, 0, 20, 0),     # 最低点高于现有库存 + S → 0
    (4, 2, 2.5, 20, 5),     # 4.5 → 半数向上取整为 5
    (4, 2, 2.4, 20, 4),     # 4.4 → 4
])
def test_target_hand_table(E, min_level, S, cap, expected):
    assert compute_target(E, min_level, S, cap) == expected


def fc(b=0.0, served=None, r=0.0, min_level=0.0):
    return StationForecast(b, b if served is None else served, r, min_level)


@pytest.mark.parametrize("stock,reserved,cap,forecast,floor,T,E,supply,demand", [
    (3, 0, 20, fc(9, 3, 0, -6), 5, 14, 3, 0, 11),          # 缺车
    (15, 0, 20, fc(0, 0, 5, 15), 5, 5, 15, 10, 0),          # 车多，但保留 S
    (5, 3, 20, fc(5, 5, 0, 3), 5, 10, 8, 0, 2),             # 已有在途预留，只需补 2
    (2, 10, 20, fc(0, 0, 0, 12), 0, 0, 12, 2, 0),           # 供给不超过现有库存（预留车未到）
    (18, 2, 20, fc(30, 18, 0, -10), 5, 20, 20, 0, 0),       # 满容量，无空位可调入
    (0, 0, 20, fc(0, 0, 0, 0), 0, 0, 0, 0, 0),              # 空站且无需求
])
def test_supply_demand_hand_table(stock, reserved, cap, forecast, floor, T, E, supply, demand):
    row = station_supply_demand(make_station("x", stock, cap, reserved), forecast, floor)
    assert (row["target"], row["effective_stock"], row["supply"], row["demand"]) == (T, E, supply, demand)
    assert 0 <= row["supply"] <= stock
    assert 0 <= row["demand"] <= cap - stock - reserved
    assert not (row["supply"] > 0 and row["demand"] > 0)


def test_served_cannot_exceed_potential():
    with pytest.raises(ValueError):
        station_supply_demand(make_station("x", 5), fc(2.0, 3.0), 5)


def test_negative_inputs_rejected():
    with pytest.raises(ValueError):
        station_supply_demand(make_station("x", 5), fc(-1.0, 0.0), 5)


def test_build_is_schema_valid_sorted_and_skips_inactive():
    stations = [make_station("s2", 15), make_station("s1", 3),
                make_station("s9", 4, active=False)]
    before = copy.deepcopy(stations)
    forecast = {"s1": fc(9, 3, 0, -6), "s2": fc(0, 0, 5, 15)}
    sd = build_supply_demand(stations, forecast, safety_stock=5, now_sec=0, horizon_sec=1800)

    schema_validator("SupplyDemand").validate(sd)
    assert sd["estimator_version"] == "fluid-v2"
    assert [row["station_id"] for row in sd["stations"]] == ["s1", "s2"]
    assert sd["stations"][0]["demand"] == 11
    assert sd["stations"][1]["supply"] == 10
    assert stations == before  # 不修改输入


def test_missing_forecast_defaults_to_current_level():
    sd = build_supply_demand([make_station("s1", 0)], {}, safety_stock=5, now_sec=60, horizon_sec=1800)
    row = sd["stations"][0]
    assert row["expected_borrow"] == 0 and row["target"] == 5 and row["demand"] == 5
