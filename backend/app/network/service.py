"""Framework-independent road projection and routing."""
from __future__ import annotations

from bisect import bisect_right
from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from math import dist, isfinite
from typing import Any

import networkx as nx

from contracts.python_interfaces import DTO, NetworkError


Point = tuple[float, float]
Node = tuple[str, ...] | tuple[str, str, float]
COORDINATE_EPSILON = 1e-5


def _number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError("Expected a finite number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError("Expected a finite number") from exc
    if not isfinite(result):
        raise ValueError("Expected a finite number")
    return result


def _identifier(value: Any) -> str:
    if not isinstance(value, str) or not 1 <= len(value) <= 128:
        raise ValueError("Expected a nonempty ID of at most 128 characters")
    return value


def _interpolate(start: Point, end: Point, fraction: float) -> Point:
    if fraction == 0:
        return start
    if fraction == 1:
        return end
    return (start[0] + fraction * (end[0] - start[0]),
            start[1] + fraction * (end[1] - start[1]))


@dataclass(frozen=True)
class _Road:
    id: str
    start: str
    end: str
    length_m: float
    points: tuple[Point, ...]
    cumulative: tuple[float, ...]

    @property
    def pixel_length(self) -> float:
        return self.cumulative[-1]

    def point_at(self, offset: float) -> Point:
        if offset == 0:
            return self.points[0]
        if offset == 1:
            return self.points[-1]
        target = offset * self.pixel_length
        index = min(bisect_right(self.cumulative, target) - 1, len(self.points) - 2)
        fraction = (target - self.cumulative[index]) / (
            self.cumulative[index + 1] - self.cumulative[index]
        )
        return _interpolate(self.points[index], self.points[index + 1], fraction)

    def section(self, start: float, end: float) -> tuple[Point, ...]:
        low, high = start * self.pixel_length, end * self.pixel_length
        return (
            self.point_at(start),
            *(p for p, at in zip(self.points, self.cumulative) if low < at < high),
            self.point_at(end),
        )

    def project(self, point: Point) -> tuple[float, float, Point]:
        best: tuple[float, float, Point] | None = None
        for i, (start, end) in enumerate(zip(self.points, self.points[1:])):
            dx, dy = end[0] - start[0], end[1] - start[1]
            span = self.cumulative[i + 1] - self.cumulative[i]
            fraction = ((point[0] - start[0]) * (dx / span) +
                        (point[1] - start[1]) * (dy / span)) / span
            fraction = min(1.0, max(0.0, fraction))
            position = _interpolate(start, end, fraction)
            offset = (self.cumulative[i] + span * fraction) / self.pixel_length
            result = dist(point, position), offset, position
            if best is None or result[:2] < best[:2]:
                best = result
        assert best is not None
        return best

    def node_at(self, offset: float) -> Node:
        if offset == 0:
            return "road-node", self.start
        if offset == 1:
            return "road-node", self.end
        return "road-point", self.id, offset


class NetworkService:
    """A read-only snapshot of the public road network and station attachments."""

    def __init__(self, network: DTO, stations: list[DTO], snap_tolerance_px: float = 40):
        self._width = _number(network["width"])
        self._height = _number(network["height"])
        self._snap_tolerance = _number(snap_tolerance_px)
        if min(self._width, self._height) <= 0 or self._snap_tolerance < 0:
            raise ValueError("Map dimensions must be positive and snap tolerance nonnegative")

        points: dict[str, Point] = {}
        for node in network["nodes"]:
            node_id = _identifier(node["id"])
            if node_id in points:
                raise ValueError(f"Duplicate road node: {node_id}")
            if node["campus"] not in {"main", "east", "connector"}:
                raise ValueError(f"Invalid road node campus: {node_id}")
            points[node_id] = self._map_point(node["x"], node["y"])

        self._roads: dict[str, _Road] = {}
        base = nx.Graph()
        base.add_nodes_from(sorted(points))
        for raw in network["edges"]:
            road = self._read_road(raw, points)
            if road.id in self._roads:
                raise ValueError(f"Duplicate road edge: {road.id}")
            self._roads[road.id] = road
            base.add_edge(road.start, road.end)
        self._component = {
            node: index
            for index, component in enumerate(nx.connected_components(base))
            for node in component
        }

        self._graph = nx.MultiGraph()
        self._graph.add_nodes_from((("road-node", i), {"point": points[i]}) for i in sorted(points))
        self._station_nodes: dict[str, Node] = {}
        self._active_components: dict[str, int] = {}
        splits: dict[str, set[float]] = defaultdict(set)
        for station in stations:
            station_id, road, offset = self._read_station(station)
            if station_id in self._station_nodes:
                raise NetworkError("INVALID_STATION", f"Duplicate station: {station_id}")
            self._station_nodes[station_id] = road.node_at(offset)
            if station["active"]:
                self._active_components[station_id] = self._component[road.start]
            splits[road.id].add(offset)

        for road in sorted(self._roads.values(), key=lambda edge: edge.id):
            cuts = sorted({0.0, 1.0, *splits[road.id]})
            for offset in cuts:
                self._graph.add_node(road.node_at(offset), point=road.point_at(offset))
            for low, high in zip(cuts, cuts[1:]):
                start, end = road.node_at(low), road.node_at(high)
                self._graph.add_edge(
                    start, end, key=road.id, weight=(high - low) * road.length_m,
                    start=start, polyline=road.section(low, high),
                )
        self._route_cache: dict[tuple[str, str], tuple[float, tuple[Point, ...]]] = {}

    def _map_point(self, x: Any, y: Any) -> Point:
        point = _number(x), _number(y)
        if not (0 <= point[0] <= self._width and 0 <= point[1] <= self._height):
            raise ValueError("Coordinate outside map bounds")
        return point

    def _read_road(self, raw: DTO, nodes: dict[str, Point]) -> _Road:
        road_id = _identifier(raw["id"])
        start, end = _identifier(raw["from"]), _identifier(raw["to"])
        length_m = _number(raw["length_m"])
        if start == end or start not in nodes or end not in nodes or length_m <= 0:
            raise ValueError(f"Invalid endpoints or length for road: {road_id}")
        if not isinstance(raw["cross_campus"], bool):
            raise ValueError(f"Invalid cross_campus marker for road: {road_id}")
        points = tuple(self._map_point(*point) for point in raw["polyline"])
        if len(points) < 2 or points[0] != nodes[start] or points[-1] != nodes[end]:
            raise ValueError(f"Polyline endpoints do not match nodes for road: {road_id}")
        cumulative = [0.0]
        for a, b in zip(points, points[1:]):
            distance = dist(a, b)
            total = cumulative[-1] + distance
            if not isfinite(total) or total <= cumulative[-1]:
                raise ValueError(f"Invalid polyline segment for road: {road_id}")
            cumulative.append(total)
        return _Road(road_id, start, end, length_m, points, tuple(cumulative))

    def _read_station(self, station: DTO) -> tuple[str, _Road, float]:
        try:
            station_id = _identifier(station["id"])
            road = self._roads[_identifier(station["road_edge_id"])]
            offset = _number(station["road_offset"])
            position = self._map_point(station["x"], station["y"])
            if not 0 <= offset <= 1 or dist(position, road.point_at(offset)) > COORDINATE_EPSILON:
                raise ValueError("Station coordinates do not match its road attachment")
            if not isinstance(station["active"], bool):
                raise ValueError("Invalid station active flag")
        except (KeyError, TypeError, ValueError) as exc:
            raise NetworkError("INVALID_STATION", f"Invalid station attachment: {station.get('id')}") from exc
        return station_id, road, offset

    def validate_station(self, candidate: DTO) -> DTO:
        """Project StationCreate without changing the service or the input."""
        try:
            station_id = _identifier(candidate["id"])
            point = self._map_point(candidate["x"], candidate["y"])
        except (KeyError, TypeError, ValueError) as exc:
            raise NetworkError("INVALID_STATION", "Station coordinates or ID are invalid") from exc
        if not self._roads:
            raise NetworkError("INVALID_STATION", "No road is available for station projection")
        options = []
        for road in self._roads.values():
            distance, offset, position = road.project(point)
            options.append((distance, road.id, offset, position))
        distance, road_id, offset, position = min(options)
        if distance > self._snap_tolerance:
            raise NetworkError("INVALID_STATION", "Station exceeds road projection tolerance")
        component = self._component[self._roads[road_id].start]
        if any(other != station_id and current != component
               for other, current in self._active_components.items()):
            raise NetworkError("UNREACHABLE", "Station is disconnected from another active station")
        result = deepcopy(candidate)
        result.update(x=position[0], y=position[1], road_edge_id=road_id, road_offset=offset)
        return result

    def route(self, source_id: str, destination_id: str) -> DTO:
        """Return a shortest route over split road segments in travel order."""
        if source_id not in self._station_nodes or destination_id not in self._station_nodes:
            raise NetworkError("UNREACHABLE", "Unknown route station")
        key = tuple(sorted((source_id, destination_id)))
        if key not in self._route_cache:
            self._route_cache[key] = self._shortest(*key)
        distance, polyline = self._route_cache[key]
        ordered = polyline if source_id == key[0] else reversed(polyline)
        return {"distance_m": distance, "polyline": [list(point) for point in ordered]}

    def _shortest(self, first: str, second: str) -> tuple[float, tuple[Point, ...]]:
        start, end = self._station_nodes[first], self._station_nodes[second]
        if start == end:
            point = self._graph.nodes[start]["point"]
            return 0.0, (point, point)
        try:
            distance, path = nx.single_source_dijkstra(self._graph, start, end, weight="weight")
        except nx.NetworkXNoPath as exc:
            raise NetworkError("UNREACHABLE", f"No road route between {first} and {second}") from exc
        points: list[Point] = []
        for a, b in zip(path, path[1:]):
            road_options = self._graph[a][b]
            _, data = min(road_options.items(), key=lambda item: (item[1]["weight"], item[0]))
            part = data["polyline"] if data["start"] == a else data["polyline"][::-1]
            points.extend(part[1:] if points else part)
        return distance, tuple(points)
