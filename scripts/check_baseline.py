"""Dependency-free semantic gate for shared fixtures and document links."""
from __future__ import annotations

import ast
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]


def load(path: str):
    return json.loads((ROOT / path).read_text(encoding="utf-8"))


def validate_fixture(network, stations, scenarios):
    """Cross-file checks beyond JSON Schema; raises ValueError on corruption."""
    def require(condition, message):
        if not condition:
            raise ValueError(message)

    def unique(items, name):
        ids = [item["id"] for item in items]
        require(len(set(ids)) == len(ids), f"duplicate {name} id")

    unique(network["nodes"], "node")
    unique(network["edges"], "edge")
    unique(stations, "station")
    unique(scenarios, "scenario")
    nodes = {n["id"]: n for n in network["nodes"]}
    edges = {e["id"]: e for e in network["edges"]}
    adjacency = {n: set() for n in nodes}
    for edge in edges.values():
        a, b = edge["from"], edge["to"]
        require(a in nodes and b in nodes and a != b, "bad edge endpoints")
        require(edge["length_m"] > 0, "non-positive edge length")
        require(edge["polyline"][0] == [nodes[a]["x"], nodes[a]["y"]], "polyline start mismatch")
        require(edge["polyline"][-1] == [nodes[b]["x"], nodes[b]["y"]], "polyline end mismatch")
        adjacency[a].add(b)
        adjacency[b].add(a)
    require(bool(nodes), "empty network")
    visited, pending = set(), [next(iter(nodes))]
    while pending:
        n = pending.pop()
        if n not in visited:
            visited.add(n)
            pending.extend(adjacency[n] - visited)
    require(visited == set(nodes), "fixture network disconnected")
    ids = {s["id"] for s in stations}
    for station in stations:
        require(0 <= station["initial_stock"] <= station["capacity"], "invalid station stock")
        require(station["capacity"] > 0, "invalid capacity")
        require(0 <= station["x"] <= network["width"] and 0 <= station["y"] <= network["height"], "station out of bounds")
        require(station["road_edge_id"] in edges, "missing station edge")
        require(0 <= station["road_offset"] <= 1, "invalid offset")
    for scenario in scenarios:
        pairs = set()
        for od in scenario["od_demands"]:
            a, b = od["origin_id"], od["destination_id"]
            require(a in ids and b in ids and a != b, "invalid OD reference")
            require((a, b) not in pairs, "duplicate OD")
            pairs.add((a, b))
            require(od["rate_per_min"] >= 0, "negative rate")
            previous = 0
            for period in sorted(od["periods"], key=lambda p: p["start_min"]):
                require(previous <= period["start_min"] < period["end_min"] <= scenario["duration_min"], "overlap or invalid period")
                require(period["multiplier"] >= 0, "negative multiplier")
                previous = period["end_min"]


def main():
    network = load("data/fixtures/road_network.json")
    stations = load("data/fixtures/default_stations.json")
    scenarios = load("data/fixtures/scenarios.json")
    validate_fixture(network, stations, scenarios)
    meta = load("data/fixtures/metadata.json")
    assert meta["synthetic"] and network["synthetic"], "fixture must be synthetic"
    assert meta["network_version"] == network["version"]
    assert (meta["width"], meta["height"]) == (network["width"], network["height"])
    assert (ROOT / "data/fixtures" / meta["image_file"]).is_file()
    state = load("contracts/examples/state.json")
    version = load("contracts/version.json")["contract_version"]
    schema = load("contracts/schema.json")
    assert state["contract_version"] == version == schema["$defs"]["State"]["properties"]["contract_version"]["const"]
    assert state["vehicles"]["total"] == sum(s["initial_stock"] for s in stations)
    assert state["vehicles"]["total"] == sum(state["vehicles"][k] for k in ["parked", "riding", "waiting", "transporting"])
    batch = load("contracts/examples/batch_request.json")
    assert len(batch["scenario_ids"]) * len(batch["algorithms"]) * len(batch["seeds"]) == 60
    assert all(0 <= t < batch["params"]["duration_min"] * 60 and t % batch["params"]["step_sec"] == 0 for t in batch["dispatch_times_sec"])
    config = load("data/fixtures/default_config.json")
    assert config["scenario_id"] in {s["id"] for s in scenarios}
    assert state["context"]["scenario_id"] == config["scenario_id"]
    assert state["context"]["params"] == config["params"]
    for directory in ["contracts", "data"]:
        for file in (ROOT / directory).rglob("*.json"):
            json.loads(file.read_text(encoding="utf-8"))
    for directory in ["backend", "contracts", "scripts", "tests"]:
        for file in (ROOT / directory).rglob("*.py"):
            ast.parse(file.read_text(encoding="utf-8"), filename=str(file))
    for file in [ROOT / "README.md", *(ROOT / "docs").rglob("*.md")]:
        for target in re.findall(r"\]\(([^)]+)\)", file.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("#"):
                assert (file.parent / target.split("#")[0]).exists(), f"broken link: {file}: {target}"
    print("Baseline OK: fixture references/connectivity/periods, conservation example, 60 combinations, Python syntax, local links")


if __name__ == "__main__":
    try:
        main()
    except (AssertionError, ValueError, KeyError) as exc:
        print(f"Baseline FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1)
