"""Use the frozen JSON Schema; cross-field rules are explicit here."""
from copy import deepcopy
from pathlib import Path
import json
import math
from jsonschema import Draft202012Validator
from app.engine.errors import DomainError

ROOT = Path(__file__).resolve().parents[3]
SCHEMA = json.loads((ROOT / 'contracts/schema.json').read_text(encoding='utf-8'))


def validate(name, value, *, fields=None, partial=False):
    schema = deepcopy(SCHEMA['$defs'][name])
    if fields is not None:
        schema['properties'] = {k: v for k, v in schema['properties'].items() if k in fields}
        schema['required'] = [] if partial else [k for k in schema.get('required', []) if k in fields]
        if partial:
            schema['minProperties'] = 1
    schema['$defs'] = SCHEMA['$defs']
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda e: str(list(e.path)))
    def finite(v):
        if isinstance(v, float) and not math.isfinite(v):
            return False
        if isinstance(v, dict):
            return all(finite(x) for x in v.values())
        if isinstance(v, list):
            return all(finite(x) for x in v)
        return True
    if errors or not finite(value):
        raise DomainError('VALIDATION_ERROR', '请求字段校验失败',
                          {'errors': [{'path': list(e.path), 'message': e.message} for e in errors]}, 422)
    return deepcopy(value)


def params_rules(params):
    validate('Params', params)
    if params['duration_min'] * 60 % params['step_sec']:
        raise DomainError('INVALID_PARAMS', '仿真时长必须能被时间步长整除')


def station_rules(station):
    if station['initial_stock'] > station['capacity']:
        raise DomainError('INVALID_STATION', '初始库存不能超过容量')


def scenario_rules(scenario, stations, duration_min=None):
    seen = set()
    duration = scenario['duration_min'] if duration_min is None else duration_min
    for od in scenario['od_demands']:
        pair = od['origin_id'], od['destination_id']
        if pair[0] == pair[1] or pair in seen:
            raise DomainError('INVALID_OD', 'OD起终点必须不同且同一场景不能重复')
        seen.add(pair)
        if any(s not in stations or not stations[s]['active'] for s in pair):
            raise DomainError('INVALID_OD', 'OD必须引用存在且启用的停车点')
        end = 0
        for p in sorted(od['periods'], key=lambda p: p['start_min']):
            if p['start_min'] < end or p['end_min'] <= p['start_min'] or p['end_min'] > duration:
                raise DomainError('INVALID_PERIOD', '倍率时段必须不重叠且位于运行时长内')
            end = p['end_min']


def dispatch_times_rules(times, params):
    if any(t % params['step_sec'] or t >= params['duration_min'] * 60 for t in times):
        raise DomainError('INVALID_DISPATCH_TIME', '调度时刻必须对齐步长且早于终点')
