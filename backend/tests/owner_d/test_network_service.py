"""AC-D01 and AC-D02 examples using an explicitly synthetic small graph."""
from copy import deepcopy

import pytest

from app.network import NetworkService
from contracts.python_interfaces import NetworkError


def node(node_id, x, y, campus="main"):
    return dict(id=node_id, x=x, y=y, campus=campus)


def edge(edge_id, start, end, length, points, cross=False):
    return {"id": edge_id, "from": start, "to": end, "length_m": length,
            "polyline": [list(point) for point in points], "cross_campus": cross}


def station_input(station_id, x, y, campus="main", active=True):
    return dict(id=station_id, name=station_id, campus=campus, zone="test",
                x=x, y=y, capacity=5, initial_stock=2, active=active)


def station(station_id, x, y, road, offset, campus="main", active=True):
    return dict(station_input(station_id, x, y, campus, active),
                road_edge_id=road, road_offset=offset)


@pytest.fixture
def small_map():
    return {
        "version": "owner-d-test",
        "width": 60,
        "height": 50,
        "synthetic": True,
        "nodes": [node("a", 0, 0), node("b", 10, 10),
                  node("c", 30, 10, "east"), node("d", 40, 10, "east"),
                  node("isolated-a", 2, 40), node("isolated-b", 12, 40)],
        "edges": [
            edge("bend", "a", "b", 120, [(0, 0), (10, 0), (10, 10)]),
            edge("connector", "b", "c", 50, [(10, 10), (30, 10)], cross=True),
            edge("east", "c", "d", 80, [(30, 10), (40, 10)]),
            edge("island", "isolated-a", "isolated-b", 10, [(2, 40), (12, 40)]),
        ],
    }


def test_routes_follow_bend_and_reverse_geometry(small_map):
    stations = [
        station("quarter", 5, 0, "bend", .25),
        station("three-quarters", 10, 5, "bend", .75),
        station("mid", 10, 0, "bend", .5),
        station("at-end", 10, 10, "bend", 1),
        station("same-end", 10, 10, "connector", 0),
        station("east", 35, 10, "east", .5, "east"),
    ]
    original_map, original_stations = deepcopy(small_map), deepcopy(stations)
    service = NetworkService(small_map, stations)
    expected = [[5, 0], [10, 0], [10, 5]]
    assert service.route("quarter", "three-quarters") == {
        "distance_m": 60, "polyline": expected
    }
    assert service.route("three-quarters", "quarter") == {
        "distance_m": 60, "polyline": expected[::-1]
    }
    assert service.route("same-end", "at-end") == {
        "distance_m": 0, "polyline": [[10, 10], [10, 10]]
    }
    assert service.route("three-quarters", "east") == {
        "distance_m": 120,
        "polyline": [[10, 5], [10, 10], [30, 10], [35, 10]],
    }
    assert small_map == original_map
    assert stations == original_stations


def test_coincident_station_offsets_and_cached_result_are_independent(small_map):
    service = NetworkService(small_map, [
        station("a", 5, 0, "bend", .25),
        station("b", 5, 0, "bend", .25),
        station("c", 10, 10, "bend", 1),
    ])
    assert service.route("a", "b") == {"distance_m": 0, "polyline": [[5, 0], [5, 0]]}
    assert service.route("a", "a") == service.route("a", "b")
    first = service.route("a", "c")
    first["polyline"][0][0] = 999
    assert service.route("a", "c") == {"distance_m": 90, "polyline": [[5, 0], [10, 0], [10, 10]]}


def test_alternative_edges_are_weighted_by_meters(small_map):
    small_map["edges"].append(edge("short", "a", "b", 30, [(0, 0), (0, 10), (10, 10)]))
    service = NetworkService(small_map, [
        station("a", 0, 0, "bend", 0),
        station("b", 10, 10, "bend", 1),
    ])
    assert service.route("a", "b") == {"distance_m": 30, "polyline": [[0, 0], [0, 10], [10, 10]]}


def test_station_projection_preserves_input_and_service(small_map):
    service = NetworkService(small_map, [station("a", 0, 0, "bend", 0)], 4)
    candidate = station_input("b", 5, 3)
    original = deepcopy(candidate)
    result = service.validate_station(candidate)
    assert result == {**original, "x": 5, "y": 0, "road_edge_id": "bend", "road_offset": .25}
    assert candidate == original
    with pytest.raises(NetworkError) as exc:
        service.route("a", "b")
    assert exc.value.code == "UNREACHABLE"


@pytest.mark.parametrize("x,y", [(-1, 0), (61, 0), (5, 20), (float("inf"), 0)])
def test_invalid_station_positions(small_map, x, y):
    service = NetworkService(small_map, [], 4)
    with pytest.raises(NetworkError) as exc:
        service.validate_station(station_input("a", x, y))
    assert exc.value.code == "INVALID_STATION"


def test_unreachable_route_and_projection(small_map):
    service = NetworkService(small_map, [
        station("a", 0, 0, "bend", 0),
        station("isolated", 2, 40, "island", 0, active=False),
    ], 4)
    for action in (lambda: service.route("a", "isolated"),
                   lambda: service.validate_station(station_input("new", 5, 40))):
        with pytest.raises(NetworkError) as exc:
            action()
        assert exc.value.code == "UNREACHABLE"


def test_station_replacement_excludes_old_attachment(small_map):
    service = NetworkService(small_map, [
        station("moving", 2, 40, "island", 0),
        station("anchor", 0, 0, "bend", 0),
    ], 4)
    result = service.validate_station(station_input("moving", 5, 2))
    assert result["road_edge_id"] == "bend"
    assert result["road_offset"] == .25
    with pytest.raises(NetworkError) as exc:
        service.route("anchor", "moving")
    assert exc.value.code == "UNREACHABLE"
    rebuilt = NetworkService(small_map, [station("anchor", 0, 0, "bend", 0), result])
    assert rebuilt.route("anchor", "moving")["distance_m"] == 30


def test_rebuild_does_not_reuse_a_previous_route(small_map):
    stations = [station("a", 0, 0, "bend", 0), station("b", 10, 10, "bend", 1)]
    original = NetworkService(small_map, stations)
    assert original.route("a", "b")["distance_m"] == 120
    small_map["edges"][0]["length_m"] = 60
    rebuilt = NetworkService(small_map, stations)
    assert rebuilt.route("a", "b")["distance_m"] == 60
    assert original.route("b", "a")["distance_m"] == 120


@pytest.mark.parametrize("problem", ["duplicate-node", "duplicate-edge", "endpoint",
                                     "zero-length", "bad-polyline"])
def test_invalid_roads_fail_construction(small_map, problem):
    if problem == "duplicate-node":
        small_map["nodes"].append(deepcopy(small_map["nodes"][0]))
    elif problem == "duplicate-edge":
        small_map["edges"].append(deepcopy(small_map["edges"][0]))
    elif problem == "endpoint":
        small_map["edges"][0]["to"] = "missing"
    elif problem == "zero-length":
        small_map["edges"][0]["length_m"] = 0
    else:
        small_map["edges"][0]["polyline"][-1] = [11, 10]
    with pytest.raises(ValueError):
        NetworkService(small_map, [])


def test_out_of_range_station_attachment_fails_construction(small_map):
    with pytest.raises(NetworkError) as exc:
        NetworkService(small_map, [station("bad", 0, 0, "bend", 1.5)])
    assert exc.value.code == "INVALID_STATION"
