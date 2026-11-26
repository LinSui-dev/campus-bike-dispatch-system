"""D-owned checks for the campus review bundle, separate from formal acceptance."""
import json
import struct
from collections import Counter
from pathlib import Path

import networkx as nx
import pytest
from jsonschema import Draft202012Validator

from app.network import NetworkService

ROOT = Path(__file__).resolve().parents[3]
CAMPUS = ROOT / "data" / "campus"
REVIEW = CAMPUS / "profile-review"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def assert_schema(name, value):
    schema = read(ROOT / "contracts" / "schema.json")
    Draft202012Validator({
        "$ref": f"#/$defs/{name}",
        "$defs": schema["$defs"],
    }).validate(value)


def test_review_map_is_a_png_with_network_dimensions():
    metadata = read(REVIEW / "metadata.json")
    network = read(REVIEW / "road_network.json")
    status = read(REVIEW / "review-status.json")
    assert status["status"] == "draft"
    assert status["ready_for_import"] is False
    assert metadata["image_file"] == "campus_map.png"
    with (REVIEW / metadata["image_file"]).open("rb") as image:
        header = image.read(24)
    assert header[:8] == b"\x89PNG\r\n\x1a\n"
    assert header[12:16] == b"IHDR"
    assert struct.unpack(">II", header[16:24]) == (4500, 3163)
    assert (metadata["width"], metadata["height"]) == (network["width"], network["height"])
    assert metadata["network_version"] == network["version"]


def test_review_scenarios_and_initial_state_match_the_selected_stations():
    network = read(REVIEW / "road_network.json")
    stations = read(REVIEW / "default_stations.json")
    scenarios = read(REVIEW / "scenarios.json")
    config = read(REVIEW / "default_config.json")
    selections = read(CAMPUS / "station-placement-review.json")
    inputs = read(CAMPUS / "profile-inputs.json")

    assert_schema("RoadNetwork", network)
    assert_schema("Config", config)
    assert selections["selected_positions_status"] == "user_confirmed"
    assert Counter(s["campus"] for s in stations) == {"main": 11, "east": 3}
    assert {s["id"] for s in stations} == set(selections["selected_station_ids"])
    assert sum(s["capacity"] for s in stations) == 565
    assert sum(s["initial_stock"] for s in stations) == 290
    ids = {s["id"] for s in stations}
    for station in stations:
        assert_schema("Station", station)
        expected = inputs["station_defaults"][station["id"]]
        assert (station["capacity"], station["initial_stock"]) == (
            expected["capacity"], expected["initial_stock"]
        )
        assert 0 <= station["initial_stock"] <= station["capacity"]
        assert station["active"]

    assert {s["id"] for s in scenarios} == {"morning", "lunch", "evening", "offpeak"}
    assert config["scenario_id"] in {s["id"] for s in scenarios}
    for scenario in scenarios:
        assert_schema("Scenario", scenario)
        assert "合成" in scenario["description"]
        assert scenario["is_preset"]
        assert scenario["duration_min"] == config["params"]["duration_min"]
        seen = set()
        for demand in scenario["od_demands"]:
            pair = demand["origin_id"], demand["destination_id"]
            assert pair[0] != pair[1] and set(pair) <= ids and pair not in seen
            seen.add(pair)
            assert demand["rate_per_min"] > 0
            previous_end = 0
            for period in sorted(demand["periods"], key=lambda p: p["start_min"]):
                assert previous_end <= period["start_min"] < period["end_min"] <= scenario["duration_min"]
                assert period["multiplier"] > 0
                previous_end = period["end_min"]
    lunch = next(s for s in scenarios if s["id"] == "lunch")
    assert {"M02", "M21", "E01"} <= {d["destination_id"] for d in lunch["od_demands"]}


def test_review_has_one_cross_campus_chain_and_bidirectional_station_routes():
    network = read(REVIEW / "road_network.json")
    stations = read(REVIEW / "default_stations.json")
    nodes = {node["id"]: node for node in network["nodes"]}
    inside = nx.Graph()
    inside.add_nodes_from(nodes)
    cross = nx.Graph()
    edges = {e["id"]: e for e in network["edges"]}
    assert len(edges) == len(network["edges"])
    assert len(nodes) == len(network["nodes"])

    for edge in edges.values():
        a, b = edge["from"], edge["to"]
        assert a != b and edge["length_m"] > 0
        assert edge["polyline"][0] == [nodes[a]["x"], nodes[a]["y"]]
        assert edge["polyline"][-1] == [nodes[b]["x"], nodes[b]["y"]]
        if edge["cross_campus"]:
            cross.add_edge(a, b)
        else:
            assert nodes[a]["campus"] == nodes[b]["campus"]
            inside.add_edge(a, b)

    assert edges["E157"]["length_m"] == 100
    assert sum(e["length_m"] for e in edges.values() if e["cross_campus"]) == pytest.approx(469)
    assert nx.is_tree(cross) and cross.number_of_edges() == 6
    gates = {n for n, degree in cross.degree if degree == 1}
    assert {nodes[n]["campus"] for n in gates} == {"main", "east"}
    assert all(cross.degree[n] == 2 and nodes[n]["campus"] == "connector"
               for n in cross if n not in gates)
    for campus in ("main", "east"):
        assert nx.is_connected(inside.subgraph(n for n, node in nodes.items() if node["campus"] == campus))

    service = NetworkService(network, stations)
    for source, destination in (("M10", "M13"), ("E01", "E04"), ("M08", "E01")):
        forward = service.route(source, destination)
        backward = service.route(destination, source)
        assert_schema("Route", forward)
        assert forward["distance_m"] > 0
        assert forward["distance_m"] == backward["distance_m"]
        assert forward["polyline"] == backward["polyline"][::-1]
    start = next(n for n in gates if nodes[n]["campus"] == "main")
    end = next(n for n in gates if nodes[n]["campus"] == "east")
    required = [[nodes[n]["x"], nodes[n]["y"]] for n in nx.shortest_path(cross, start, end)]
    points = service.route("M08", "E01")["polyline"]
    first = points.index(required[0])
    assert points[first:first+len(required)] == required
