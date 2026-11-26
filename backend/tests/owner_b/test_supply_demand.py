"""AC-B02：供需公式的手算基准与边界。"""
import copy

import pytest

from app.dispatch.supply_demand import (build_supply_demand, compute_target,
                                        station_supply_demand)

from .helpers import make_station, schema_validator


@pytest.mark.parametrize("b,r,s,cap,expected", [
    (2.5, 0, 0, 20, 3),     # 恰好 .5 向上取整
    (1.5, 0, 0, 20, 2),
    (2.49, 0, 0, 20, 2),
    (0.5, 0, 0, 20, 1),
    (10, 0, 5, 20, 15),     # 讲解例子：宿舍
    (0, 5, 5, 20, 0),       # 讲解例子：教学楼
    (0, 10, 5, 20, 0),      # B-R+S 为负 → 0
    (30, 0, 5, 20, 20),     # 超过容量 → 截到 capacity
    (3.2, 1.1, 0, 20, 2),   # 2.1 → 2
])
def test_target_hand_table(b, r, s, cap, expected):
    assert compute_target(b, r, s, cap) == expected


@pytest.mark.parametrize("stock,reserved,cap,b,r,s,T,E,supply,demand", [
    (3, 0, 20, 10, 0, 5, 15, 3, 0, 12),    # 缺车
    (15, 0, 20, 0, 5, 5, 0, 15, 15, 0),    # 车多
    (5, 3, 20, 5, 0, 5, 10, 8, 0, 2),      # 已有在途预留，只需补 2
    (2, 10, 20, 0, 0, 0, 0, 12, 2, 0),     # 供给不超过现有库存（预留的车还没到）
    (10, 0, 20, 0, 0, 10, 10, 10, 0, 0),   # 刚好平衡
    (0, 0, 20, 0, 0, 0, 0, 0, 0, 0),       # 空站且无需求
    (18, 2, 20, 30, 0, 5, 20, 20, 0, 0),   # 满容量，无空位可调入
])
def test_supply_demand_hand_table(stock, reserved, cap, b, r, s, T, E, supply, demand):
    row = station_supply_demand(make_station("x", stock, cap, reserved), b, min(b, stock), r, s)
    assert (row["target"], row["effective_stock"], row["supply"], row["demand"]) == (T, E, supply, demand)
    assert 0 <= row["supply"] <= stock
    assert 0 <= row["demand"] <= cap - stock - reserved
    assert not (row["supply"] > 0 and row["demand"] > 0)


def test_served_cannot_exceed_potential():
    with pytest.raises(ValueError):
        station_supply_demand(make_station("x", 5), 2.0, 3.0, 0.0, 5)


def test_negative_inputs_rejected():
    with pytest.raises(ValueError):
        station_supply_demand(make_station("x", 5), -1.0, 0.0, 0.0, 5)


def test_build_is_schema_valid_sorted_and_skips_inactive():
    stations = [make_station("s2", 15), make_station("s1", 3),
                make_station("s9", 4, active=False)]
    before = copy.deepcopy(stations)
    forecast = {"s1": (10.0, 3.0, 0.0), "s2": (0.0, 0.0, 5.0)}
    sd = build_supply_demand(stations, forecast, safety_stock=5, now_sec=0, horizon_sec=1800)

    schema_validator("SupplyDemand").validate(sd)
    assert [row["station_id"] for row in sd["stations"]] == ["s1", "s2"]
    assert sd["stations"][0]["demand"] == 12
    assert sd["stations"][1]["supply"] == 15
    assert stations == before  # 不修改输入


def test_missing_forecast_defaults_to_zero():
    sd = build_supply_demand([make_station("s1", 0)], {}, safety_stock=5, now_sec=60, horizon_sec=1800)
    row = sd["stations"][0]
    assert row["expected_borrow"] == 0 and row["target"] == 5 and row["demand"] == 5
