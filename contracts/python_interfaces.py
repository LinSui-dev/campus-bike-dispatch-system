"""Frozen 1.1.0 ports. DTO definitions live in schema.json and docs/07."""
from __future__ import annotations

from typing import Any, Callable, Protocol

DTO = dict[str, Any]


class NetworkError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class NetworkPort(Protocol):
    def validate_station(self, candidate: DTO) -> DTO:
        """Accept complete StationCreate, return Station or raise NetworkError.

        A merges PATCH and removes derived edge/offset before calling this port.
        Normalizing an existing id replaces that station, not a duplicate insert.
        """
        ...

    def route(self, source_id: str, destination_id: str) -> DTO:
        """Return Route {distance_m, polyline}; raise on unreachable."""
        ...


class DispatchPort(Protocol):
    def estimate(self, snapshot: DTO, scenario: DTO, params: DTO,
                 network: NetworkPort) -> DTO:
        """Return SupplyDemand; snapshot is full State, no future requests."""
        ...

    def plan(self, algorithm: str, supply_demand: DTO,
             network: NetworkPort, max_dispatch: int) -> list[DTO]:
        """Return DispatchPlanItem list; never mutate snapshot or stocks."""
        ...


class EnginePort(Protocol):
    def step(self) -> DTO:
        """Process current boundary and return State; end is idempotent."""
        ...

    def snapshot(self) -> DTO:
        ...

    def dispatch(self, request_id: str) -> DTO:
        """Compute and atomically execute current configured strategy."""
        ...


RunOnce = Callable[[DTO], DTO]
OnProgress = Callable[[DTO], None]


class ExperimentPort(Protocol):
    def run_batch(self, request: DTO, run_once: RunOnce,
                  on_progress: OnProgress) -> DTO:
        """run_once gets RunSpec, returns RunOutcome. Errors become failed items."""
        ...
