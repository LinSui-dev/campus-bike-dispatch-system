from contracts.python_interfaces import DTO


class NetworkService:
    """Owner D implements this entry without changing the constructor."""
    def __init__(self, network: DTO, stations: list[DTO], snap_tolerance_px: float = 40):
        self.network = network
        self.stations = stations
        self.snap_tolerance_px = snap_tolerance_px

    def validate_station(self, candidate: DTO) -> DTO:
        """candidate is StationCreate; return normalized full Station."""
        raise NotImplementedError("D: station projection and validation")

    def route(self, source_id: str, destination_id: str) -> DTO:
        raise NotImplementedError("D: weighted shortest route")
