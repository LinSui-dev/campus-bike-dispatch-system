"""AC-B01：库存约束期望预测。所有期望值都是按 docs/05、06 规则手算的。

约定：step=60 秒，骑行 12km/h。990 米 = 297 秒 → 向上取整到 5 步（300 秒）；
10 米 → 至少 1 步（60 秒）。
"""
import copy
import json

import pytest

from app.dispatch import DispatchService
from app.dispatch.forecast import forecast, multiplier_integral, travel_steps_sec
from contracts.python_interfaces import NetworkError

from .helpers import ROOT, make_network, schema_validator

service = DispatchService()


def station(sid, stock, capacity=20, reserved=0, active=True):
    return {"id": sid, "capacity": capacity, "stock": stock, "reserved_inbound": reserved, "active": active}


def snapshot(stations, now=0, duration=7200, rides=(), waiting=(), tasks=()):
    return {"sim_time_sec": now, "duration_sec": duration, "stations": list(stations),
            "rides": list(rides), "waiting": list(waiting), "tasks": list(tasks)}


def ride(dest, arrival):
    return {"id": f"ride-{dest}-{arrival}", "origin_id": "x", "destination_id": dest, "depart_sec": 0,
            "arrival_sec": arrival, "first_attempted": False, "reroute_count": 0, "extra_distance_m": 0}


def waiting_at(sid):
    return {"id": f"ride-w-{sid}", "station_id": sid, "since_sec": 0, "first_attempted": True,
            "reroute_count": 0, "extra_distance_m": 0}


def task(dest, qty, arrival, status="transporting"):
    return {"id": f"task-{dest}", "source_id": "x", "destination_id": dest, "quantity": qty,
            "distance_m": 100, "route": [[0, 0], [1, 1]], "depart_sec": 0,
            "arrival_sec": arrival, "status": status}


def od(origin, dest, rate, periods=()):
    return {"origin_id": origin, "destination_id": dest, "rate_per_min": rate, "periods": list(periods)}


def scenario(*ods):
    return {"id": "t", "name": "t", "start_minute": 420, "duration_min": 120, "description": "",
            "is_preset": False, "od_demands": list(ods)}


def params(horizon_min=10, safety_stock=5):
    return {"duration_min": 120, "step_sec": 60, "ride_speed_kmh": 12, "dispatch_speed_kmh": 10,
            "speed": 60, "horizon_min": horizon_min, "safety_stock": safety_stock, "max_dispatch": 50}


def rows_by_id(sd):
    return {row["station_id"]: row for row in sd["stations"]}


# ---------- 基础工具 ----------

def test_travel_time_rule():
    assert travel_steps_sec(990, 12, 60) == 300     # 297 秒 → 5 步
    assert travel_steps_sec(1000, 12, 60) == 300    # 恰好 300 秒，浮点误差不能变成 6 步
    assert travel_steps_sec(1001, 12, 60) == 360
    assert travel_steps_sec(10, 12, 60) == 60
    assert travel_steps_sec(0, 12, 60) == 60        # 零距离也至少一步


def test_multiplier_integral():
    assert multiplier_integral([], 0, 600) == 600
    assert multiplier_integral([{"start_min": 2.5, "end_min": 5, "multiplier": 3}], 0, 600) == 600 + 150 * 2
    assert multiplier_integral([{"start_min": 0, "end_min": 30, "multiplier": 0}], 60, 120) == 0


# ---------- 讲解例子 ----------

def test_tutorial_example():
    """宿舍 3 辆、教学楼 15 辆；宿舍→教学楼每分钟 1 人，骑 5 分钟；2 辆在途第 2 分钟到教学楼。
    借车桶 t=60..540 共 9 个 → B=9；宿舍只借出 3 辆（t=60,120,180），
    在 360/420/480 到达；教学楼 R = 3 + 2 = 5。"""
    snap = snapshot([station("dorm", 3), station("teach", 15)],
                    rides=[ride("teach", 120), ride("teach", 120)])
    net = make_network({("dorm", "teach"): 990})
    sd = service.estimate(snap, scenario(od("dorm", "teach", 1)), params(), net)
    rows = rows_by_id(sd)

    assert sd["now_sec"] == 0 and sd["horizon_sec"] == 600
    assert rows["dorm"]["expected_borrow"] == pytest.approx(9)
    assert rows["dorm"]["expected_served_borrow"] == pytest.approx(3)
    assert rows["dorm"]["expected_return"] == 0
    assert rows["teach"]["expected_return"] == pytest.approx(5)
    # 宿舍水位 3 → 最低 3-9=-6；S=max(5, Q95(Poisson(9))-9=14-9=5)=5；T=3+5-(-6)=14 → 缺 11
    assert (rows["dorm"]["target"], rows["dorm"]["demand"]) == (14, 11)
    # 教学楼只进不出，最低点就是当前 15；B=0 → S=5；T=15+5-15=5 → 可调出 10（v1 会给出 15）
    assert (rows["teach"]["target"], rows["teach"]["supply"]) == (5, 10)
    schema_validator("SupplyDemand").validate(sd)
    assert sd["estimator_version"] == "fluid-v2"


def test_borrow_first_return_later_is_short():
    """v1 公式的反例：宿舍 10 辆，前 10 分钟 20 人借车，第 25 分钟 20 辆还回来。
    v1：T = B-R+S = 20-20+5 = 5 < 10，判为可调出 5 辆，但第 5 分钟就空站了。
    v2：水位 10 → 第 10 分钟最低 -10 → 第 25 分钟回到 10；
        S = max(5, Q95(Poisson(20))-20 = 28-20 = 8) = 8；T = 10+8-(-10) = 28 → 缺 18。"""
    snap = snapshot([station("dorm", 10, capacity=30), station("teach", 0, capacity=60)],
                    rides=[ride("dorm", 1500) for _ in range(20)])
    sc = scenario(od("dorm", "teach", 2, [{"start_min": 11, "end_min": 120, "multiplier": 0}]))
    sd = service.estimate(snap, sc, params(horizon_min=30), make_network({("dorm", "teach"): 990}))
    dorm = rows_by_id(sd)["dorm"]
    assert dorm["expected_borrow"] == pytest.approx(20)
    assert dorm["expected_return"] == pytest.approx(20)
    assert (dorm["target"], dorm["supply"], dorm["demand"]) == (28, 0, 18)


def test_min_level_tracks_lowest_point():
    snap = snapshot([station("dorm", 10, capacity=30), station("teach", 0, capacity=60)],
                    rides=[ride("dorm", 1500) for _ in range(20)])
    sc = scenario(od("dorm", "teach", 2, [{"start_min": 11, "end_min": 120, "multiplier": 0}]))
    result, _ = forecast(snap, sc, params(horizon_min=30), make_network({("dorm", "teach"): 990}))
    assert result["dorm"].min_level == pytest.approx(-10)
    assert result["teach"].min_level == 0           # 只有到达，没有借车，最低点是起点


def test_redirected_arrivals_do_not_raise_level():
    """改道转来的车不计入目的站水位（它们原本不是来这个站的）。"""
    snap = snapshot([station("teach", 20), station("lib", 0)], rides=[ride("teach", 60)])
    result, _ = forecast(snap, scenario(od("lib", "teach", 1)), params(horizon_min=5),
                         make_network({("teach", "lib"): 10, ("lib", "teach"): 10}))
    # t=120 改道车到 lib；t=120 从 lib 借出的车 t=180 到满站 teach，又改道回 lib（t=240）
    assert result["lib"].returned == pytest.approx(2)
    assert result["lib"].min_level == pytest.approx(-4)   # 0 - 4 个借车桶，改道车不抵消


# ---------- AC-B01 核心检查点 ----------

def test_empty_station_keeps_potential_demand():
    snap = snapshot([station("dorm", 0), station("teach", 15)])
    sd = service.estimate(snap, scenario(od("dorm", "teach", 1)), params(),
                          make_network({("dorm", "teach"): 990}))
    rows = rows_by_id(sd)
    assert rows["dorm"]["expected_borrow"] == pytest.approx(9)       # 潜在需求 > 0
    assert rows["dorm"]["expected_served_borrow"] == 0               # 但借不出车
    assert rows["teach"]["expected_return"] == 0                     # 也就没有新骑行还车
    assert rows["dorm"]["demand"] == 14


def test_known_rides_counted_once_and_window_cutoff():
    snap = snapshot([station("a", 5), station("b", 5)],
                    rides=[ride("b", 120), ride("b", 600), ride("b", 660)])  # 窗口末 600
    result, _ = forecast(snap, scenario(), params(), make_network({}))
    assert result["b"].returned == pytest.approx(2)    # 120 与 600 计入，660 不计入


def test_new_ride_after_window_not_counted():
    """t=540 借出，5 分钟后 840 才到，超过窗口 600。"""
    snap = snapshot([station("a", 100), station("b", 0)])
    result, _ = forecast(snap, scenario(od("a", "b", 1)), params(), make_network({("a", "b"): 990}))
    # 借车桶 60..540 共 9 辆，到达 360..840，窗口内 360/420/480/540/600 共 5 辆
    assert result["a"].served == pytest.approx(9)
    assert result["b"].returned == pytest.approx(5)


def test_transport_adds_stock_but_not_return():
    """宿舍空站，5 辆运输在 120 到达；到货前借不出，到货后可借，运输本身不计 R。"""
    snap = snapshot([station("dorm", 0, reserved=5), station("teach", 0)],
                    tasks=[task("dorm", 5, 120), task("teach", 3, 60, status="completed")])
    result, _ = forecast(snap, scenario(od("dorm", "teach", 1)), params(), make_network({("dorm", "teach"): 990}))
    b, served, r = result["dorm"].borrow, result["dorm"].served, result["dorm"].returned
    assert b == pytest.approx(9)
    assert served == pytest.approx(5)      # t=60 借不到；t=120..540 共 8 桶，但只有 5 辆
    assert r == 0
    # 已完成的运输任务被忽略；5 辆在 120..360 借出，420..660 到达，窗口 600 内只有 4 辆
    assert result["teach"].returned == pytest.approx(4)


def test_multiplier_period():
    """前 5 分钟倍率 2：桶 t=60..240 每个 2，t=300..540 每个 1 → 8 + 5 = 13。"""
    snap = snapshot([station("a", 100, capacity=200), station("b", 0)])
    sc = scenario(od("a", "b", 1, [{"start_min": 0, "end_min": 5, "multiplier": 2}]))
    result, _ = forecast(snap, sc, params(), make_network({("a", "b"): 990}))
    assert result["a"].borrow == pytest.approx(13)


def test_same_origin_split_proportionally():
    """a 只有 1 辆，a→b 每分钟 2 人、a→c 每分钟 1 人：借出 1 辆按 2:1 分。窗口 2 分钟，只有 t=60 一个桶。"""
    snap = snapshot([station("a", 1), station("b", 0), station("c", 0)])
    sc = scenario(od("a", "b", 2), od("a", "c", 1))
    net = make_network({("a", "b"): 10, ("a", "c"): 10})
    result, _ = forecast(snap, sc, params(horizon_min=2), net)
    assert (result["a"].borrow, result["a"].served) == (pytest.approx(3), pytest.approx(1))
    assert result["b"].returned == pytest.approx(2 / 3)
    assert result["c"].returned == pytest.approx(1 / 3)


# ---------- 满站改道与等待 ----------

def test_full_station_redirects_to_nearest():
    snap = snapshot([station("teach", 20), station("lib", 0), station("gym", 0)],
                    rides=[ride("teach", 60)])
    net = make_network({("teach", "lib"): 10, ("teach", "gym"): 500})
    result, _ = forecast(snap, scenario(), params(horizon_min=5), net)
    assert result["teach"].returned == 0
    assert result["lib"].returned == pytest.approx(1)    # 改道到最近的 lib，下一步到达
    assert result["gym"].returned == 0


def test_redirect_splits_by_free_space():
    """2 辆到满站；最近的 lib 只剩 1 个空位，另 1 辆去 gym。"""
    snap = snapshot([station("teach", 20), station("lib", 19), station("gym", 0)],
                    rides=[ride("teach", 60), ride("teach", 60)])
    net = make_network({("teach", "lib"): 10, ("teach", "gym"): 500})
    result, _ = forecast(snap, scenario(), params(horizon_min=10), net)
    assert result["lib"].returned == pytest.approx(1)
    assert result["gym"].returned == pytest.approx(1)


def test_waiting_retries_when_space_frees():
    """teach 满且有 1 辆等待；dorm 也满。t=60 有人从 teach 借走 1 辆，
    等待车在 t=120 才重试成功（本步新等待不在本步重试）。"""
    snap = snapshot([station("teach", 2, capacity=2), station("dorm", 100, capacity=100)],
                    waiting=[waiting_at("teach")])
    net = make_network({("teach", "dorm"): 10})   # dorm→teach 不可达，dorm 满站车只能等待
    result, _ = forecast(snap, scenario(od("teach", "dorm", 1)), params(horizon_min=3), net)
    b, served, r = result["teach"].borrow, result["teach"].served, result["teach"].returned
    assert (b, served) == (pytest.approx(2), pytest.approx(2))
    assert r == pytest.approx(1)
    assert result["dorm"].returned == 0


# ---------- 窗口、输入与输出 ----------

def test_window_truncated_at_duration():
    snap = snapshot([station("a", 10), station("b", 0)], now=7080, duration=7200)
    sd = service.estimate(snap, scenario(od("a", "b", 1)), params(horizon_min=30),
                          make_network({("a", "b"): 990}))
    assert sd["horizon_sec"] == 120
    assert rows_by_id(sd)["a"]["expected_borrow"] == pytest.approx(1)   # 只有 t=7140 一个桶


def test_finished_run_has_empty_window():
    snap = snapshot([station("a", 10), station("b", 0)], now=7200, duration=7200)
    sd = service.estimate(snap, scenario(od("a", "b", 1)), params(), make_network({("a", "b"): 990}))
    assert sd["horizon_sec"] == 0
    assert all(row["expected_borrow"] == 0 for row in sd["stations"])


def test_inactive_station_excluded():
    snap = snapshot([station("a", 10), station("b", 0), station("z", 5, active=False)])
    sd = service.estimate(snap, scenario(od("a", "b", 1), od("z", "b", 1)), params(),
                          make_network({("a", "b"): 990, ("z", "b"): 990}))
    assert [row["station_id"] for row in sd["stations"]] == ["a", "b"]


def test_unreachable_od_raises():
    snap = snapshot([station("a", 10), station("b", 0)])
    with pytest.raises(NetworkError):
        service.estimate(snap, scenario(od("a", "b", 1)), params(), make_network({}))


def test_deterministic_and_does_not_mutate_inputs():
    snap = snapshot([station("dorm", 3), station("teach", 20), station("lib", 0)],
                    rides=[ride("teach", 120)], waiting=[waiting_at("teach")], tasks=[task("dorm", 2, 180)])
    snap["stations"][0]["reserved_inbound"] = 2
    sc = scenario(od("dorm", "teach", 1.3), od("lib", "dorm", 0.4))
    pr = params(horizon_min=30)
    net = make_network({("dorm", "teach"): 990, ("lib", "dorm"): 400, ("teach", "lib"): 10,
                        ("teach", "dorm"): 990})
    before = copy.deepcopy((snap, sc, pr))
    first = service.estimate(snap, sc, pr, net)
    second = service.estimate(snap, sc, pr, net)
    assert first == second
    assert (snap, sc, pr) == before
    for row in first["stations"]:
        assert 0 <= row["expected_served_borrow"] <= row["expected_borrow"] + 1e-9


def test_contract_example_state_with_fixture_scenarios():
    """用契约示例 State 和虚拟夹具的四个场景跑一遍，输出必须符合 Schema。"""
    state = json.loads((ROOT / "contracts/examples/state.json").read_text(encoding="utf-8"))
    scenarios = json.loads((ROOT / "data/fixtures/scenarios.json").read_text(encoding="utf-8"))
    config = json.loads((ROOT / "data/fixtures/default_config.json").read_text(encoding="utf-8"))
    ids = [s["id"] for s in state["stations"]]
    net = make_network({(a, b): 250 for a in ids for b in ids if a != b})
    validator = schema_validator("SupplyDemand")
    for sc in scenarios:
        sd = service.estimate(state, sc, config["params"], net)
        validator.validate(sd)
        assert sd["horizon_sec"] == 1800
        assert any(row["expected_borrow"] > 0 for row in sd["stations"])
