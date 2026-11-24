from contracts.python_interfaces import DTO, RunOnce, OnProgress


class ExperimentRunner:
    def run_batch(self, request: DTO, run_once: RunOnce, on_progress: OnProgress) -> DTO:
        raise NotImplementedError("B: serial batch combinations and aggregation")
