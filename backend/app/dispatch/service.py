from contracts.python_interfaces import DTO, NetworkPort

from . import strategies
from .forecast import forecast
from .supply_demand import build_supply_demand


class DispatchService:
    def estimate(self, snapshot: DTO, scenario: DTO, params: DTO, network: NetworkPort) -> DTO:
        """流体期望预测 + 供需计算，返回 SupplyDemand，不修改输入。"""
        predicted, horizon_sec = forecast(snapshot, scenario, params, network)
        return build_supply_demand(snapshot["stations"], predicted, int(params["safety_stock"]),
                                   int(snapshot["sim_time_sec"]), horizon_sec)

    def plan(self, algorithm: str, supply_demand: DTO, network: NetworkPort,
             max_dispatch: int) -> list[DTO]:
        """none / greedy / min_cost_flow，返回 DispatchPlanItem 列表，不修改输入。"""
        return strategies.plan(algorithm, supply_demand, network, max_dispatch)
