"""库存约束的流体期望预测（docs/06“库存约束期望预测”一节）。

从当前快照出发，按引擎的 step 逐步向后推演 horizon 窗口：
    每个边界 t 的处理顺序与引擎一致（docs/05）：
    运输到达 -> 骑行到达 -> 此前等待重试 -> 本步借车

对每个站累计三个量：
    B      expected_borrow         OD 率积分得到的潜在借车量，不管有没有车
    served expected_served_borrow  受库存限制的预计实际借出量，只有它产生新骑行
    R      expected_return         窗口内实际归还到该站的骑行/等待车辆

这是确定性的期望近似：车辆数是小数，不做随机抽样，不读未来真实请求，
不预测之后会发生的调度。
"""
from __future__ import annotations

import copy
import math
from collections import defaultdict
from typing import Any, Mapping

from contracts.python_interfaces import NetworkError, NetworkPort

EPS = 1e-9


def multiplier_integral(periods: list[Mapping[str, Any]], start_sec: float, end_sec: float) -> float:
    """倍率对时间的积分（单位：秒）。时段为相对场景起点的分钟半开区间，未覆盖处倍率为 1。"""
    if end_sec <= start_sec:
        return 0.0
    total = end_sec - start_sec
    for period in periods:
        lo = max(start_sec, period["start_min"] * 60)
        hi = min(end_sec, period["end_min"] * 60)
        if hi > lo:
            total += (hi - lo) * (period["multiplier"] - 1)
    return total


def travel_steps_sec(distance_m: float, speed_kmh: float, step_sec: int) -> int:
    """引擎的到达规则：max(step, ceil(距离/速度/step) * step)，零距离也至少一步。"""
    seconds = distance_m / (speed_kmh / 3.6)
    steps = math.ceil(round(seconds / step_sec, 9))  # round 消除浮点误差，如 4.9999999999 -> 5
    return max(step_sec, steps * step_sec)


class FluidForecaster:
    def __init__(self, snapshot: Mapping[str, Any], scenario: Mapping[str, Any],
                 params: Mapping[str, Any], network: NetworkPort):
        self.network = network
        self.step = int(params["step_sec"])
        self.speed_kmh = float(params["ride_speed_kmh"])
        self.now = int(snapshot["sim_time_sec"])
        self.window_end = min(self.now + int(params["horizon_min"]) * 60, int(snapshot["duration_sec"]))

        stations = [s for s in snapshot["stations"] if s.get("active", True)]
        self.ids = sorted(s["id"] for s in stations)
        self.capacity = {s["id"]: int(s["capacity"]) for s in stations}
        self.stock = {s["id"]: float(s["stock"]) for s in stations}
        self.reserved = {s["id"]: float(s["reserved_inbound"]) for s in stations}

        self.borrow = dict.fromkeys(self.ids, 0.0)     # B
        self.served = dict.fromkeys(self.ids, 0.0)     # served
        self.returned = dict.fromkeys(self.ids, 0.0)   # R

        # 到达队列：时刻 -> [(目的站, 数量)]
        self.ride_arrivals: dict[int, list[tuple[str, float]]] = defaultdict(list)
        self.transport_arrivals: dict[int, list[tuple[str, float]]] = defaultdict(list)
        self.waiting: dict[str, float] = defaultdict(float)
        self._routes: dict[tuple[str, str], float | None] = {}

        # 已知在途骑行：各入队一次
        for ride in snapshot["rides"]:
            self._schedule(self.ride_arrivals, int(ride["arrival_sec"]), ride["destination_id"], 1.0)
        # 已在运输中的调度：到达后入库并释放预留（不计入 R）
        for task in snapshot["tasks"]:
            if task["status"] == "transporting":
                self._schedule(self.transport_arrivals, int(task["arrival_sec"]),
                               task["destination_id"], float(task["quantity"]))
        # 已在等待的车辆：下一步起重试
        for item in snapshot["waiting"]:
            if item["station_id"] in self.capacity:
                self.waiting[item["station_id"]] += 1.0

        # 只保留起终点都有效的 OD，按 (起点, 终点) 排序
        self.ods = sorted(
            (od for od in scenario["od_demands"]
             if od["origin_id"] in self.capacity and od["destination_id"] in self.capacity
             and od["origin_id"] != od["destination_id"]),
            key=lambda od: (od["origin_id"], od["destination_id"]))

    # ---------- 工具 ----------

    def _schedule(self, queue, time_sec: int, station_id: str, amount: float) -> None:
        """登记到达；窗口结束后才到的不计入，已过去的时刻按下一边界处理。"""
        if amount <= EPS or station_id not in self.capacity:
            return
        time_sec = max(time_sec, self.now + self.step)
        if time_sec <= self.window_end:
            queue[time_sec].append((station_id, amount))

    def _distance(self, source: str, destination: str) -> float | None:
        """道路距离，带缓存；不可达返回 None。"""
        key = (source, destination)
        if key not in self._routes:
            try:
                self._routes[key] = float(self.network.route(source, destination)["distance_m"])
            except NetworkError as exc:
                if exc.code != "UNREACHABLE":
                    raise
                self._routes[key] = None
        return self._routes[key]

    def _free(self, station_id: str) -> float:
        return self.capacity[station_id] - self.stock[station_id] - self.reserved[station_id]

    # ---------- 每步四个阶段 ----------

    def _arrive_transports(self, t: int) -> None:
        for station_id, amount in self.transport_arrivals.pop(t, []):
            self.stock[station_id] += amount
            self.reserved[station_id] = max(0.0, self.reserved[station_id] - amount)

    def _try_return(self, station_id: str, amount: float, t: int, redirected: dict[str, float]) -> None:
        """在 station_id 归还 amount 辆：有空位就还；满了按 (距离, id) 改道到有空位的站；
        都没有空位则在原站等待。"""
        accepted = min(amount, max(0.0, self._free(station_id)))
        if accepted > EPS:
            self.stock[station_id] += accepted
            self.returned[station_id] += accepted
        rest = amount - accepted
        if rest <= EPS:
            return

        candidates = []
        for other in self.ids:
            if other == station_id:
                continue
            distance = self._distance(station_id, other)
            if distance is not None:
                candidates.append((distance, other))
        for distance, other in sorted(candidates):
            # 改道不预留车位；本步已改道去该站的量先扣掉，避免同一空位被重复使用
            space = self._free(other) - redirected[other]
            if space <= EPS:
                continue
            moved = min(rest, space)
            redirected[other] += moved
            self._schedule(self.ride_arrivals, t + travel_steps_sec(distance, self.speed_kmh, self.step),
                           other, moved)
            rest -= moved
            if rest <= EPS:
                return
        self.waiting[station_id] += rest

    def _arrive_rides_and_waiting(self, t: int) -> None:
        redirected: dict[str, float] = defaultdict(float)
        previous_waiting = self.waiting
        self.waiting = defaultdict(float)  # 本步新产生的等待不在本步重试
        for station_id, amount in sorted(self.ride_arrivals.pop(t, [])):
            self._try_return(station_id, amount, t, redirected)
        for station_id in sorted(previous_waiting):
            self._try_return(station_id, previous_waiting[station_id], t, redirected)

    def _borrow(self, t: int) -> None:
        """借车桶 [t, t+step) 与窗口的交集；同一起点多条 OD 按潜在需求比例分配库存。"""
        bucket_end = min(t + self.step, self.window_end)
        potentials: dict[str, list[tuple[Mapping[str, Any], float]]] = defaultdict(list)
        for od in self.ods:
            amount = od["rate_per_min"] * multiplier_integral(od["periods"], t, bucket_end) / 60.0
            if amount > EPS:
                potentials[od["origin_id"]].append((od, amount))

        for origin in sorted(potentials):
            wanted = sum(amount for _, amount in potentials[origin])
            self.borrow[origin] += wanted
            available = max(0.0, self.stock[origin])
            served_total = min(available, wanted)
            if served_total <= EPS:
                continue
            self.stock[origin] -= served_total
            self.served[origin] += served_total
            for od, amount in potentials[origin]:
                share = served_total * amount / wanted
                distance = self._distance(origin, od["destination_id"])
                if distance is None:
                    raise NetworkError("UNREACHABLE",
                                       f"OD {origin}->{od['destination_id']} 不可达")
                arrival = t + travel_steps_sec(distance, self.speed_kmh, self.step)
                self._schedule(self.ride_arrivals, arrival, od["destination_id"], share)

    # ---------- 主循环 ----------

    def run(self) -> dict[str, tuple[float, float, float]]:
        """返回 station_id -> (B, served, R)。"""
        t = self.now + self.step
        while t <= self.window_end:
            self._arrive_transports(t)
            self._arrive_rides_and_waiting(t)
            if t < self.window_end:
                self._borrow(t)
            t += self.step
        return {sid: (self.borrow[sid], min(self.served[sid], self.borrow[sid]), self.returned[sid])
                for sid in self.ids}

    @property
    def horizon_sec(self) -> int:
        return max(0, self.window_end - self.now)


def forecast(snapshot: Mapping[str, Any], scenario: Mapping[str, Any],
             params: Mapping[str, Any], network: NetworkPort) -> tuple[dict[str, tuple[float, float, float]], int]:
    """对输入做深拷贝后推演，返回 (每站 (B, served, R), 实际窗口秒数)。"""
    forecaster = FluidForecaster(copy.deepcopy(snapshot), copy.deepcopy(scenario),
                                 copy.deepcopy(params), network)
    return forecaster.run(), forecaster.horizon_sec
