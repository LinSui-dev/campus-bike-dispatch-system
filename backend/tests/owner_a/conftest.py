"""Explicit test-only ports: no campus routing, forecasting or optimization claims."""
from copy import deepcopy
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from contracts.python_interfaces import NetworkError
from app.main import create_app
from app.services.validation import validate
from tests.support.doubles import NetworkStub, DispatchStub

ROOT = Path(__file__).resolve().parents[3]
FIXTURE = ROOT / 'data/fixtures'


def read(name):
    return json.loads((FIXTURE / name).read_text(encoding='utf-8'))


def analysis(stations, now=0):
    return {'estimator_version': 'TEST-ONLY-zero-demand', 'now_sec': now, 'horizon_sec': 0,
            'stations': [{'station_id': s['id'], 'expected_borrow': 0, 'expected_served_borrow': 0,
                          'expected_return': 0, 'target': 0, 'effective_stock': s.get('stock', s['initial_stock']) + s.get('reserved_inbound', 0),
                          'supply': s.get('stock', s['initial_stock']), 'demand': 0} for s in stations]}


class DispatchDouble(DispatchStub):
    def __init__(self):
        super().__init__(analysis([]))

    def estimate(self, snapshot, scenario, params, network):
        return analysis(snapshot['stations'], snapshot['sim_time_sec'])


class NetworkDouble(NetworkStub):
    def __init__(self, network, stations, snap_tolerance_px=40):
        routes = {(s['id'], d['id']): {'distance_m': 0 if s['id'] == d['id'] else 200,
                  'polyline': [[s['x'], s['y']], [d['x'], d['y']]]} for s in stations for d in stations}
        super().__init__(routes)

    def validate_station(self, candidate):
        if candidate['x'] > 1000 or candidate['y'] > 400:
            raise NetworkError('INVALID_STATION', 'Test-only bounds rejection')
        return deepcopy(candidate) | {'road_edge_id': 'e1', 'road_offset': 0}


@pytest.fixture
def app_factory(tmp_path):
    def factory(name='unit.db', **kwargs):
        return create_app(database_url='sqlite:///' + (tmp_path / name).as_posix(),
                          data_profile='fixture', network_factory=NetworkDouble,
                          dispatch_factory=DispatchDouble, auto_advance=False, **kwargs)
    return factory


@pytest.fixture
def client(app_factory):
    with TestClient(app_factory(), raise_server_exceptions=False) as client:
        yield client


def request(request_id='r1', **updates):
    value = {k: v for k, v in read('default_config.json').items() if k not in ('id','name')}
    value['request_id'] = request_id
    value.update(deepcopy(updates))
    return value


def snapshot(stocks=(1, 0), duration=2):
    stations = read('default_stations.json')[:len(stocks)]
    for s, n in zip(stations, stocks):
        s['initial_stock'], s['capacity'] = n, max(n, 10)
    scenario = read('scenarios.json')[0]
    scenario['od_demands'] = []
    params = read('default_config.json')['params'] | {'duration_min': duration}
    return {'versions': {'contract': '1.1.0', 'engine': 'a-engine-v1', 'generator': 'poisson-exp-v1',
                         'network': 'fixture-v1', 'python': 'test', 'networkx': '3.4.2'},
            'network': read('road_network.json'), 'stations': stations, 'scenario': scenario,
            'params': params, 'seed': 42, 'algorithm': 'none', 'dispatch_times_sec': [],
            'commands': [], 'batch_request': None}


def make_engine(config=None):
    from app.engine import Engine
    config = deepcopy(config or snapshot())
    return Engine('unit-run', config, NetworkDouble(config['network'], config['stations']), DispatchDouble())


def event(t=0, origin='s1', destination='s2', index=1, step=60):
    return {'id': f'req-{index:012d}', 'time_sec': t, 'executed_sec': t // step * step,
            'origin_id': origin, 'destination_id': destination}


def assert_state(state):
    validate('State', state)
    v = state['vehicles']
    assert v['total'] == v['parked'] + v['riding'] + v['waiting'] + v['transporting']
    assert all(0 <= s['stock'] <= s['capacity'] - s['reserved_inbound'] for s in state['stations'])
