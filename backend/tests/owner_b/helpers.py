"""owner_b 测试公用的构造函数和 Schema 校验。"""
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from tests.support.doubles import NetworkStub

ROOT = Path(__file__).resolve().parents[3]
_SCHEMA = json.loads((ROOT / "contracts" / "schema.json").read_text(encoding="utf-8"))


def schema_validator(name: str) -> Draft202012Validator:
    return Draft202012Validator({"$defs": _SCHEMA["$defs"], "$ref": f"#/$defs/{name}"})


def make_station(sid, stock, capacity=20, reserved=0, active=True):
    """只含供需计算所需字段的站点。"""
    return {"id": sid, "capacity": capacity, "stock": stock,
            "reserved_inbound": reserved, "active": active}


def make_supply_demand(supply: dict, demand: dict) -> dict:
    """直接构造 SupplyDemand（策略测试不依赖预测）。"""
    ids = sorted(set(supply) | set(demand))
    rows = [{"station_id": sid, "expected_borrow": 0.0, "expected_served_borrow": 0.0,
             "expected_return": 0.0, "target": 0, "effective_stock": 0,
             "supply": supply.get(sid, 0), "demand": demand.get(sid, 0)} for sid in ids]
    return {"estimator_version": "test", "now_sec": 0, "horizon_sec": 1800, "stations": rows}


def make_network(distances: dict) -> NetworkStub:
    """distances: {(源, 目的): 米数}；未列出的组合视为不可达。"""
    return NetworkStub({pair: {"distance_m": d, "polyline": [[0, 0], [1, 1]]}
                        for pair, d in distances.items()})
