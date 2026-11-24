"""Permanent contract and fixture checks, not a P0 business acceptance suite."""
from pathlib import Path

from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator
import pytest

from app.main import app
from scripts.check_baseline import load, validate_fixture

ROOT = Path(__file__).resolve().parents[2]
SCHEMA = load("contracts/schema.json")


def validator(name):
    return Draft202012Validator({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})


@pytest.mark.parametrize("name,path", [
    ("State", "contracts/examples/state.json"),
    ("RunRequest", "contracts/examples/run_request.json"),
    ("BatchRequest", "contracts/examples/batch_request.json"),
    ("SupplyDemand", "contracts/examples/supply_demand.json"),
    ("RoadNetwork", "data/fixtures/road_network.json"),
    ("Config", "data/fixtures/default_config.json"),
    ("StationCreate", "contracts/examples/station_create.json"),
    ("StationPatch", "contracts/examples/station_patch.json"),
])
def test_examples_conform(name, path):
    validator(name).validate(load(path))


def test_all_schema_definitions_valid():
    Draft202012Validator.check_schema(SCHEMA)
    for name in SCHEMA["$defs"]:
        Draft202012Validator.check_schema({"$defs": SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})


def test_fixture_collections():
    for station in load("data/fixtures/default_stations.json"):
        validator("Station").validate(station)
    for scenario in load("data/fixtures/scenarios.json"):
        validator("Scenario").validate(scenario)


def test_reset_requires_explicit_save_choice():
    assert not validator("Control").is_valid({"action": "reset"})
    assert validator("Control").is_valid({"action": "reset", "save": False})
    assert not validator("Control").is_valid({"action": "pause", "save": True})


def test_duplicate_batch_inputs_rejected():
    request = load("contracts/examples/batch_request.json")
    request["seeds"].append(42)
    assert not validator("BatchRequest").is_valid(request)


@pytest.mark.parametrize("corruption", ["stock", "reference", "period"])
def test_fixture_gate_detects_cross_field_corruption(corruption):
    network = load("data/fixtures/road_network.json")
    stations = load("data/fixtures/default_stations.json")
    scenarios = load("data/fixtures/scenarios.json")
    if corruption == "stock":
        stations[0]["initial_stock"] = 999
    elif corruption == "reference":
        scenarios[0]["od_demands"][0]["destination_id"] = "missing"
    else:
        scenarios[0]["od_demands"][0]["periods"] *= 2
    with pytest.raises(ValueError):
        validate_fixture(network, stations, scenarios)


def test_api_health_and_fixture_asset_are_connected(monkeypatch):
    monkeypatch.setenv("DATA_PROFILE", "fixture")
    with TestClient(app) as client:
        health = client.get("/api/v1/health").json()
        assert health["status"] == "ok"
        assert health["stage"] in {"scaffold", "implemented"}
        assert client.get("/api/v1/runtime").json()["mode"] == "idle"
        metadata = client.get("/api/v1/map").json()
        assert metadata["synthetic"] is True
        assert client.get(metadata["image_url"]).status_code == 200
        validator("RoadNetwork").validate(client.get("/api/v1/roads").json())


def test_station_create_does_not_accept_derived_road_fields():
    request = load("contracts/examples/station_create.json")
    request["road_offset"] = 0.5
    assert not validator("StationCreate").is_valid(request)


@pytest.mark.parametrize("patch", [{}, {"x": 100}, {"y": 200}, {"id": "s2"}, {"road_edge_id": "e1"}])
def test_station_patch_rejects_ambiguous_or_derived_updates(patch):
    assert not validator("StationPatch").is_valid(patch)


def test_runtime_context_is_required_for_recovery():
    state = load("contracts/examples/state.json")
    del state["context"]
    assert not validator("State").is_valid(state)


def test_current_speed_can_differ_from_frozen_initial_speed():
    state = load("contracts/examples/state.json")
    state["context"]["current_speed"] = 120
    validator("State").validate(state)
    assert state["context"]["params"]["speed"] == 60
