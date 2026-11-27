"""E system-acceptance fixtures: real A engine/runtime, real B dispatch, real D network.

No test doubles and no frontend Mock are used here. Every app instance gets its own
temporary SQLite database and the formal campus profile, so runs never touch the
development database.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app

ROOT = Path(__file__).resolve().parents[2]
CAMPUS = ROOT / "data" / "campus"
P = "/api/v1"


def read_campus(name: str):
    return json.loads((CAMPUS / name).read_text(encoding="utf-8"))


def run_request(request_id: str, scenario_id: str = "morning", algorithm: str = "none",
                seed: int = 42, duration_min: int = 30, speed: float = 60.0) -> dict:
    return {
        "request_id": request_id,
        "scenario_id": scenario_id,
        "params": {
            "duration_min": duration_min,
            "step_sec": 60,
            "ride_speed_kmh": 12,
            "dispatch_speed_kmh": 10,
            "speed": speed,
            "horizon_min": 30,
            "safety_stock": 5,
            "max_dispatch": 50,
        },
        "seed": seed,
        "algorithm": algorithm,
    }


@pytest.fixture
def app(tmp_path):
    application = create_app(
        database_url="sqlite:///" + (tmp_path / "acceptance.db").as_posix(),
        data_profile="campus",
        auto_advance=False,
    )
    return application


@pytest.fixture
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def advance_until(client: TestClient, app, run_id: str, limit_sec: int = 7200) -> dict:
    """Step the real engine deterministically until the run stops or the limit is reached."""
    state = client.get(f"{P}/runs/{run_id}/state").json()
    steps = 0
    while state["status"] == "running" and steps <= limit_sec // 60 + 5:
        app.state.manager.advance()
        state = client.get(f"{P}/runs/{run_id}/state").json()
        steps += 1
    return state


def assert_conserved(state: dict) -> None:
    vehicles = state["vehicles"]
    assert vehicles["total"] == (vehicles["parked"] + vehicles["riding"]
                                 + vehicles["waiting"] + vehicles["transporting"])
    for station in state["stations"]:
        assert 0 <= station["stock"] <= station["capacity"] - station["reserved_inbound"]
