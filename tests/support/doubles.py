"""Injected canned ports for independent module development; no real algorithms."""
from copy import deepcopy

from contracts.python_interfaces import DTO, NetworkError


class NetworkStub:
    """Supply explicit directed route pairs and optional normalized stations."""
    def __init__(self, routes: dict[tuple[str, str], DTO], normalized: dict[str, DTO] | None = None):
        self.routes = deepcopy(routes)
        self.normalized = deepcopy(normalized or {})

    def route(self, source_id: str, destination_id: str) -> DTO:
        try:
            return deepcopy(self.routes[source_id, destination_id])
        except KeyError as exc:
            raise NetworkError('UNREACHABLE', 'Test route not provided') from exc

    def validate_station(self, candidate: DTO) -> DTO:
        try:
            return deepcopy(self.normalized[candidate['id']])
        except KeyError as exc:
            raise NetworkError('INVALID_STATION', 'Normalized test station not provided') from exc


class DispatchStub:
    """Caller supplies expected analysis/plans, with no forecasting or optimization."""
    def __init__(self, analysis: DTO, plans: list[DTO] | None = None):
        self.analysis = deepcopy(analysis)
        self.plans = deepcopy(plans or [])

    def estimate(self, snapshot, scenario, params, network):
        return deepcopy(self.analysis)

    def plan(self, algorithm, supply_demand, network, max_dispatch):
        return [] if algorithm == 'none' else deepcopy(self.plans)
