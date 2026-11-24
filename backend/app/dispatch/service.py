from contracts.python_interfaces import DTO, NetworkPort


class DispatchService:
    def estimate(self, snapshot: DTO, scenario: DTO, params: DTO, network: NetworkPort) -> DTO:
        raise NotImplementedError("B: constrained expected demand forecast")

    def plan(self, algorithm: str, supply_demand: DTO, network: NetworkPort,
             max_dispatch: int) -> list[DTO]:
        raise NotImplementedError("B: dispatch strategies")
