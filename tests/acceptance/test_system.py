"""E real-system acceptance on the formal campus profile.

Each test exercises the production wiring (A backend/engine + B dispatch/experiments +
D network/campus data). Tests assert observable behaviour, not implementation detail.
"""
from __future__ import annotations

import pytest

from app.network import NetworkService

from .conftest import (advance_until, assert_conserved, read_campus, run_request, P)

pytestmark = pytest.mark.acceptance

EXPECTED_SCENARIOS = {
    "morning", "morning-dismissal", "lunch", "afternoon-class",
    "afternoon-dismissal", "dinner", "evening-class", "evening",
}


def test_health_map_and_formal_campus_profile(client):
    """AC-D03 / AC-E02: implemented health and the 14-station, 8-scenario campus profile."""
    health = client.get(f"{P}/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok", "stage": "implemented"}

    info = client.get(f"{P}/map").json()
    assert info["profile"] == "campus"
    assert info["synthetic"] is False
    assert (info["width"], info["height"]) == (4500, 3163)

    stations = client.get(f"{P}/stations").json()["items"]
    assert len(stations) == 14
    assert sum(1 for s in stations if s["campus"] == "main") == 11
    assert sum(1 for s in stations if s["campus"] == "east") == 3
    assert sum(s["capacity"] for s in stations) == 565
    assert sum(s["initial_stock"] for s in stations) == 290

    scenarios = client.get(f"{P}/scenarios").json()["items"]
    assert {s["id"] for s in scenarios} == EXPECTED_SCENARIOS
    assert all(s["is_preset"] for s in scenarios)

    image = client.get(info["image_url"])
    assert image.status_code == 200
    assert image.headers["content-type"].startswith("image/")


def test_station_create_uses_real_projection(client):
    """AC-A01 / AC-D02: StationCreate without road fields is projected by D's real service."""
    stations = client.get(f"{P}/stations").json()["items"]
    anchor = next(s for s in stations if s["id"] == "M10")
    candidate = {
        "id": "ACC-T01", "name": "验收临时站点", "campus": "main", "zone": "验收",
        "x": anchor["x"], "y": anchor["y"], "capacity": 6, "initial_stock": 2, "active": True,
    }
    created = client.post(f"{P}/stations", json=candidate)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["road_edge_id"] and 0 <= body["road_offset"] <= 1
    assert body["capacity"] == 6 and body["initial_stock"] == 2

    moved = client.patch(f"{P}/stations/ACC-T01", json={"x": anchor["x"], "y": anchor["y"]})
    assert moved.status_code == 200
    assert moved.json()["id"] == "ACC-T01"

    illegal = dict(candidate, id="ACC-T02", x=-5000, y=-5000)
    rejected = client.post(f"{P}/stations", json=illegal)
    assert rejected.status_code in (400, 422)
    assert "ACC-T02" not in {s["id"] for s in client.get(f"{P}/stations").json()["items"]}

    assert client.delete(f"{P}/stations/ACC-T01").status_code == 204


def test_interactive_run_conserves_vehicles_and_saves_history(client, app):
    """AC-A02 / AC-A05 / AC-A06 / AC-A08: deterministic run, conservation and persisted history."""
    started = client.post(f"{P}/runs", json=run_request("acc-run-lifecycle"))
    assert started.status_code == 201, started.text
    state = started.json()
    run_id = state["run_id"]
    assert state["status"] == "running"
    assert state["contract_version"] == "1.1.0"
    assert state["vehicles"]["total"] == 290
    assert state["duration_sec"] == 1800

    final = advance_until(client, app, run_id)
    assert final["status"] == "completed"
    assert final["sim_time_sec"] == 1800
    assert_conserved(final)
    assert final["metrics"]["request_count"] > 0
    assert final["vehicles"]["total"] == 290

    metrics = client.get(f"{P}/runs/{run_id}/metrics")
    assert metrics.status_code == 200
    history = client.get(f"{P}/runs").json()["items"]
    assert any(item["id"] == run_id for item in history)
    assert client.get(f"{P}/runtime").json()["mode"] == "idle"


def test_real_dispatch_creates_tasks_and_is_idempotent(client, app):
    """AC-A04 / AC-B03: B's plan executed atomically by A, repeated request_id is safe."""
    started = client.post(f"{P}/runs", json=run_request("acc-dispatch-run", algorithm="greedy"))
    assert started.status_code == 201, started.text
    run_id = started.json()["run_id"]

    first = client.post(f"{P}/runs/{run_id}/dispatch", json={"request_id": "acc-dispatch-1"})
    assert first.status_code == 200, first.text
    receipt = first.json()
    assert isinstance(receipt.get("items", receipt.get("tasks", [])), list)

    tasks_before = client.get(f"{P}/runs/{run_id}/tasks").json()["items"]
    repeated = client.post(f"{P}/runs/{run_id}/dispatch", json={"request_id": "acc-dispatch-1"})
    assert repeated.status_code == 200
    tasks_after = client.get(f"{P}/runs/{run_id}/tasks").json()["items"]
    assert len(tasks_after) == len(tasks_before)

    final = advance_until(client, app, run_id)
    assert final["status"] == "completed"
    assert_conserved(final)
    assert final["metrics"]["dispatch_quantity"] > 0
    assert final["metrics"]["dispatch_cost_bike_m"] > 0


def test_batch_runs_three_strategies_with_real_engine(client, app):
    """AC-B04 / AC-E02: a real 1x3x2 batch finishes with correct aggregates and valid n."""
    request = {
        "request_id": "acc-batch-1",
        "scenario_ids": ["morning"],
        "algorithms": ["none", "greedy", "min_cost_flow"],
        "seeds": [42, 43],
        "params": run_request("x")["params"],
        "dispatch_times_sec": [0, 900],
    }
    accepted = client.post(f"{P}/batches", json=request)
    assert accepted.status_code == 202, accepted.text

    manager = app.state.manager
    manager.batch_thread.join(120)

    result = client.get(f"{P}/batches/acc-batch-1").json()
    assert result["status"] == "completed"
    assert result["finished"] == result["total"] == 6
    assert all(item["status"] == "completed" and item["run_id"] for item in result["items"])
    assert len({item["run_id"] for item in result["items"]}) == 6

    groups = {(g["scenario_id"], g["algorithm"]): g["metrics"] for g in result["aggregates"]}
    assert set(groups) == {("morning", a) for a in ("none", "greedy", "min_cost_flow")}
    for metrics in groups.values():
        assert metrics["borrow_success_rate"]["n"] == 2
        assert metrics["borrow_success_rate"]["stddev"] is not None
    assert groups[("morning", "none")]["dispatch_quantity"]["mean"] == 0
    assert groups[("morning", "greedy")]["dispatch_quantity"]["mean"] > 0


def test_single_run_slot_rejects_second_start(client):
    """AC-A07: one interactive run occupies the single slot until stopped."""
    first = client.post(f"{P}/runs", json=run_request("acc-slot-1", duration_min=60))
    assert first.status_code == 201
    run_id = first.json()["run_id"]
    assert client.get(f"{P}/runtime").json()["mode"] == "interactive"

    second = client.post(f"{P}/runs", json=run_request("acc-slot-2", duration_min=60))
    assert second.status_code == 409
    assert second.json()["code"] == "BUSY"

    stopped = client.post(f"{P}/runs/{run_id}/control", json={"action": "stop"})
    assert stopped.status_code == 200
    assert client.get(f"{P}/runtime").json()["mode"] == "idle"
    assert client.post(f"{P}/runs", json=run_request("acc-slot-3", duration_min=60)).status_code == 201


def test_campus_network_routes_and_scenario_references():
    """AC-D01 / AC-D03: formal network distances and every scenario OD are routable."""
    network = read_campus("road_network.json")
    stations = read_campus("default_stations.json")
    scenarios = read_campus("scenarios.json")
    service = NetworkService(network, stations)

    by_id = {s["id"]: s for s in stations}
    assert service.route("M10", "M13")["distance_m"] == pytest.approx(266.43, abs=0.05)
    assert service.route("E01", "E04")["distance_m"] == pytest.approx(297.14, abs=0.05)
    assert service.route("M08", "E01")["distance_m"] == pytest.approx(829.47, abs=0.05)

    ids = [s["id"] for s in stations if s["active"]]
    for origin in ids:
        for destination in ids:
            if origin != destination:
                route = service.route(origin, destination)
                assert route["distance_m"] > 0
                assert len(route["polyline"]) >= 2
    for scenario in scenarios:
        for od in scenario["od_demands"]:
            assert by_id[od["origin_id"]]["active"] and by_id[od["destination_id"]]["active"]
            service.route(od["origin_id"], od["destination_id"])
