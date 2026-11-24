from contracts.python_interfaces import DTO, NetworkPort, DispatchPort


class Engine:
    def __init__(self, run_id: str, snapshot: DTO, network: NetworkPort, dispatcher: DispatchPort):
        """snapshot conforms to ConfigSnapshot; no HTTP or database objects."""
        self.run_id = run_id

    def step(self) -> DTO:
        raise NotImplementedError("A: deterministic step")

    def snapshot(self) -> DTO:
        raise NotImplementedError("A: full State")

    def dispatch(self, request_id: str) -> DTO:
        raise NotImplementedError("A: atomic execution and deduplication")
