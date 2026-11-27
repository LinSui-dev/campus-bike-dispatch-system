"""Synchronous deterministic engine: no HTTP, ORM or wall-clock scheduling."""
from collections import Counter
from copy import deepcopy
from decimal import Decimal, ROUND_CEILING
from math import isclose, isfinite
from time import perf_counter

from contracts.python_interfaces import NetworkError
from .errors import DomainError
from .generator import generate_requests


class Engine:
    def __init__(self, run_id, snapshot, network, dispatcher):
        self.run_id = run_id
        self.config = deepcopy(snapshot)
        self.network, self.dispatcher = network, dispatcher
        self.params = self.config["params"]
        self.duration = self.params["duration_min"] * 60
        self.step_sec = self.params["step_sec"]
        self.now = self.cursor = self.seq = 0
        self.status = "running"
        self.current_speed = self.params["speed"]
        self.stations = {s["id"]: deepcopy(s) | {"stock": s["initial_stock"], "reserved_inbound": 0}
                         for s in sorted(snapshot["stations"], key=lambda s: s["id"])}
        self.total = sum(s["stock"] for s in self.stations.values())
        self.rides, self.waiting, self.tasks = {}, {}, {}
        self.requests = generate_requests(self.config["scenario"], self.params, self.config["seed"])
        self.request_cursor = self.ride_counter = self.task_counter = 0
        self.commands = deepcopy(snapshot["commands"])
        self.samples, self.dispatch_receipts = [], {}
        self.riding_seconds = 0
        self.metrics = dict.fromkeys([
            "request_count", "borrow_success", "borrow_failed", "first_return_attempts",
            "first_return_success", "dispatch_quantity", "target_deviation", "unfinished_riding",
            "unfinished_waiting", "unfinished_transporting", "shortage_station_min", "full_station_min",
            "extra_ride_distance_m", "dispatch_cost_bike_m", "algorithm_compute_ms"], 0)
        self.metrics.update(borrow_success_rate=None, first_return_success_rate=None, utilization=None)
        self.assert_invariants()

    def snapshot(self):
        m = deepcopy(self.metrics)
        m.update(unfinished_riding=len(self.rides), unfinished_waiting=len(self.waiting),
                 unfinished_transporting=sum(t["quantity"] for t in self.tasks.values()
                                             if t["status"] == "transporting"))
        m["borrow_success_rate"] = m["borrow_success"] / m["request_count"] if m["request_count"] else None
        m["first_return_success_rate"] = (m["first_return_success"] / m["first_return_attempts"]
                                           if m["first_return_attempts"] else None)
        m["utilization"] = self.riding_seconds / (self.total * self.now) if self.total and self.now else None
        scenario = self.config["scenario"]
        return deepcopy({"contract_version": self.config["versions"]["contract"], "run_id": self.run_id,
            "seq": self.seq, "sim_time_sec": self.now, "duration_sec": self.duration,
            "status": self.status, "algorithm": self.config["algorithm"],
            "stations": list(self.stations.values()), "rides": list(self.rides.values()),
            "waiting": list(self.waiting.values()), "tasks": list(self.tasks.values()), "metrics": m,
            "vehicles": {"parked": sum(s["stock"] for s in self.stations.values()),
                         "riding": len(self.rides), "waiting": len(self.waiting),
                         "transporting": m["unfinished_transporting"], "total": self.total},
            "context": {"scenario_id": scenario["id"], "scenario_name": scenario["name"],
                        "start_minute": scenario["start_minute"], "seed": self.config["seed"],
                        "params": self.params, "current_speed": self.current_speed,
                        "network_version": self.config["versions"]["network"]}})

    def assert_invariants(self):
        def require(condition):
            if not condition:
                raise RuntimeError('Engine vehicle/capacity invariant violated')
        inbound = Counter()
        for task in self.tasks.values():
            if task["status"] == "transporting":
                inbound[task["destination_id"]] += task["quantity"]
        for s in self.stations.values():
            require(type(s["stock"]) is int and type(s["reserved_inbound"]) is int)
            require(0 <= s["stock"] <= s["capacity"] - s["reserved_inbound"])
            require(s["reserved_inbound"] == inbound[s["id"]])
        parked = sum(s["stock"] for s in self.stations.values())
        require(parked + len(self.rides) + len(self.waiting) + sum(inbound.values()) == self.total)
        require(not self.rides.keys() & self.waiting.keys())
        require(self.metrics["request_count"] == self.metrics["borrow_success"] + self.metrics["borrow_failed"])

    def arrival_sec(self, distance, speed):
        # Decimal inputs preserve exact decimal speed/distance boundaries (200m / 12km/h = 60s).
        steps = (Decimal(str(distance)) * Decimal('3.6') /
                 (Decimal(str(speed)) * self.step_sec)).to_integral_value(rounding=ROUND_CEILING)
        return self.now + max(1, int(steps)) * self.step_sec

    def available(self, station_id):
        s = self.stations[station_id]
        return s["capacity"] - s["stock"] - s["reserved_inbound"]

    def _return(self, ride, station_id):
        """Return policy; vehicle must already be removed from its old collection."""
        if self.available(station_id) > 0:
            self.stations[station_id]["stock"] += 1
            return
        choices = []
        for other in self.stations:
            if other == station_id or self.available(other) <= 0:
                continue
            try:
                route = self.network.route(station_id, other)
            except NetworkError as exc:
                if exc.code != "UNREACHABLE":
                    raise
                continue
            choices.append((route["distance_m"], other))
        if choices:
            distance, destination = min(choices)
            self.metrics["extra_ride_distance_m"] += distance
            self.rides[ride["id"]] = {"id": ride["id"], "origin_id": station_id,
                "destination_id": destination, "depart_sec": self.now,
                "arrival_sec": self.arrival_sec(distance, self.params["ride_speed_kmh"]),
                "first_attempted": True, "reroute_count": ride["reroute_count"] + 1,
                "extra_distance_m": ride["extra_distance_m"] + distance}
        else:
            self.waiting[ride["id"]] = {"id": ride["id"], "station_id": station_id,
                "since_sec": ride.get("since_sec", self.now), "first_attempted": True,
                "reroute_count": ride["reroute_count"], "extra_distance_m": ride["extra_distance_m"]}

    def step(self):
        if self.status != "running":
            return self.snapshot()
        elapsed = self.cursor - self.now
        self.riding_seconds += len(self.rides) * elapsed
        self.metrics["shortage_station_min"] += sum(s["stock"] == 0 for s in self.stations.values()) * elapsed / 60
        self.metrics["full_station_min"] += sum(self.available(s) == 0 for s in self.stations) * elapsed / 60
        self.now = self.cursor
        old_waiting = sorted(self.waiting)
        for task in sorted(self.tasks.values(), key=lambda t: t["id"]):
            if task["status"] == "transporting" and task["arrival_sec"] <= self.now:
                s = self.stations[task["destination_id"]]
                s["reserved_inbound"] -= task["quantity"]
                s["stock"] += task["quantity"]
                task["status"] = "completed"
                self.assert_invariants()
        for ride in sorted(list(self.rides.values()), key=lambda r: r["id"]):
            if ride["arrival_sec"] > self.now:
                continue
            del self.rides[ride["id"]]
            if not ride["first_attempted"]:
                self.metrics["first_return_attempts"] += 1
                self.metrics["first_return_success"] += int(self.available(ride["destination_id"]) > 0)
                ride["first_attempted"] = True
            self._return(ride, ride["destination_id"])
            self.assert_invariants()
        for ride_id in old_waiting:
            ride = self.waiting.pop(ride_id)
            self._return(ride, ride["station_id"])
            self.assert_invariants()
        if self.now < self.duration:
            while self.request_cursor < len(self.requests):
                req = self.requests[self.request_cursor]
                if req["executed_sec"] > self.now:
                    break
                self.request_cursor += 1
                source = self.stations[req["origin_id"]]
                self.metrics["request_count"] += 1
                if source["stock"] == 0:
                    self.metrics["borrow_failed"] += 1
                else:
                    route = self.network.route(req["origin_id"], req["destination_id"])
                    source["stock"] -= 1
                    self.metrics["borrow_success"] += 1
                    self.ride_counter += 1
                    ride_id = f"ride-{self.ride_counter:012d}"
                    self.rides[ride_id] = {"id": ride_id, "origin_id": source["id"],
                        "destination_id": req["destination_id"], "depart_sec": self.now,
                        "arrival_sec": self.arrival_sec(route["distance_m"], self.params["ride_speed_kmh"]),
                        "first_attempted": False, "reroute_count": 0, "extra_distance_m": 0}
                self.assert_invariants()
            if self.now in self.config["dispatch_times_sec"] and self.config["algorithm"] != "none":
                self.dispatch(f"scheduled-{self.now}")
            self.cursor += self.step_sec
        else:
            self.status = "completed"
        self.seq += 1
        self.sample()
        self.assert_invariants()
        return self.snapshot()

    def supply_demand(self):
        # Only public current state crosses the port; never expose self.requests.
        return self.dispatcher.estimate(self.snapshot(), deepcopy(self.config["scenario"]),
                                        deepcopy(self.params), self.network)

    def sample(self):
        supply = self.supply_demand()
        self.metrics["target_deviation"] = sum(abs(self.stations[s["station_id"]]["stock"] +
            self.stations[s["station_id"]]["reserved_inbound"] - s["target"]) for s in supply["stations"])
        state = self.snapshot()
        sample = {"sim_time_sec": self.now, "metrics": state["metrics"], "stations": state["stations"]}
        if self.samples and self.samples[-1]["sim_time_sec"] == self.now:
            self.samples[-1] = sample
        else:
            self.samples.append(sample)

    def record_command(self, action, payload, result):
        self.seq += 1
        self.commands.append({"command_seq": len(self.commands) + 1, "sim_time_sec": self.now,
                              "action": action, "payload": deepcopy(payload), "result": deepcopy(result)})

    def dispatch(self, request_id):
        if request_id in self.dispatch_receipts:
            receipt = self.dispatch_receipts[request_id]
            if isinstance(receipt, DomainError):
                raise receipt
            return deepcopy(receipt)
        try:
            if self.status not in ("running", "paused"):
                raise DomainError("INVALID_STATE", "运行已结束，不能发车", status=409)
            start = perf_counter()
            supply = self.supply_demand()
            plans = ([] if self.config["algorithm"] == "none" else self.dispatcher.plan(
                self.config["algorithm"], deepcopy(supply), self.network, self.params["max_dispatch"]))
            compute_ms = (perf_counter() - start) * 1000 if self.config["algorithm"] != "none" else 0
            self._validate_plan(plans)
            tasks = []
            for plan in plans:
                self.task_counter += 1
                task = deepcopy(plan) | {"id": f"task-{self.task_counter:012d}", "depart_sec": self.now,
                    "arrival_sec": self.arrival_sec(plan["distance_m"], self.params["dispatch_speed_kmh"]),
                    "status": "transporting"}
                self.stations[plan["source_id"]]["stock"] -= plan["quantity"]
                self.stations[plan["destination_id"]]["reserved_inbound"] += plan["quantity"]
                self.tasks[task["id"]] = task
                tasks.append(task)
            self.metrics["dispatch_quantity"] += sum(t["quantity"] for t in tasks)
            self.metrics["dispatch_cost_bike_m"] += sum(t["quantity"] * t["distance_m"] for t in tasks)
            self.metrics["algorithm_compute_ms"] += compute_ms
            result = {"request_id": request_id, "tasks": deepcopy(tasks), "supply_demand": supply}
            self.record_command("dispatch", {"request_id": request_id}, result)
            self.assert_invariants()
            self.dispatch_receipts[request_id] = deepcopy(result)
            return result
        except DomainError as exc:
            self.dispatch_receipts[request_id] = exc
            raise

    def _validate_plan(self, plans):
        outgoing, incoming = Counter(), Counter()
        for p in plans:
            if (set(p) != {"source_id", "destination_id", "quantity", "distance_m", "route"}
                or p["source_id"] not in self.stations or p["destination_id"] not in self.stations
                or p["source_id"] == p["destination_id"] or type(p["quantity"]) is not int or p["quantity"] <= 0):
                raise DomainError("INVALID_PLAN", "调度任务格式或站点非法")
            route = self.network.route(p["source_id"], p["destination_id"])
            if (type(p["distance_m"]) not in (int, float) or not isfinite(p["distance_m"]) or p["distance_m"] < 0
                or not isclose(p["distance_m"], route["distance_m"], abs_tol=1e-8)
                or p["route"] != route["polyline"]):
                raise DomainError("INVALID_PLAN", "调度路径与道路网络不符")
            outgoing[p["source_id"]] += p["quantity"]
            incoming[p["destination_id"]] += p["quantity"]
        if sum(outgoing.values()) > self.params["max_dispatch"]:
            raise DomainError("INVALID_PLAN", "超过单批调度上限")
        if any(n > self.stations[s]["stock"] for s, n in outgoing.items()) or any(
                n > self.available(s) for s, n in incoming.items()):
            raise DomainError("STALE_PLAN", "库存或容量不足，整批调度未执行", status=409)
