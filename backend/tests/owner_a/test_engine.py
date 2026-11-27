from copy import deepcopy
from math import floor, log1p
from random import Random
import pytest
from app.engine.generator import generate_requests
from app.engine.errors import DomainError
from .conftest import snapshot, make_engine, event, assert_state


@pytest.mark.parametrize('stock', [0, 1])
def test_a02_borrow_and_first_return(stock):
    e = make_engine(snapshot((stock, 0)))
    e.requests = [event()]
    state = e.step()
    assert_state(state)
    assert state['sim_time_sec'] == 0 and e.cursor == 60
    assert state['metrics']['request_count'] == 1
    assert state['metrics']['borrow_success'] == stock
    assert state['metrics']['borrow_failed'] == 1 - stock
    assert state['vehicles']['riding'] == stock
    state = e.step()
    assert_state(state)
    assert state['sim_time_sec'] == 60
    assert state['metrics']['first_return_attempts'] == stock
    assert state['metrics']['first_return_success'] == stock
    assert state['stations'][1]['stock'] == stock
    assert state['metrics']['utilization'] == (1 if stock else None)


def test_generator_independent_rng_and_interval_oracle():
    config = snapshot()
    config['scenario']['od_demands'] = [{'origin_id':'s1','destination_id':'s2','rate_per_min':2,
        'periods':[{'start_min':0.5,'end_min':1,'multiplier':0}]}]
    events = generate_requests(config['scenario'], config['params'], 42)
    # Independent fixed-rate interval oracle, including zero-rate interval with no RNG draws.
    rng, expected, sequence = Random(42), [], 0
    for start, end in [(0,30),(60,120)]:
        time = start
        while True:
            time -= log1p(-rng.random()) / (2/60)
            if time >= end:
                break
            sequence += 1
            expected.append((floor(time), f'req-{sequence:012d}'))
    assert [(e['time_sec'],e['id']) for e in events] == sorted(expected)
    assert all(not 30 <= e['time_sec'] < 60 for e in events)
    assert all(e['executed_sec'] <= e['time_sec'] < e['executed_sec'] + 60 for e in events)
    assert events == generate_requests(config['scenario'], config['params'], 42)


def test_generator_od_input_order_and_different_seed():
    c = snapshot()
    c['scenario']['od_demands'] = [
        {'origin_id':'s2','destination_id':'s1','rate_per_min':10,'periods':[]},
        {'origin_id':'s1','destination_id':'s2','rate_per_min':10,'periods':[]}]
    original = generate_requests(c['scenario'], c['params'], 42)
    c['scenario']['od_demands'].reverse()
    assert original == generate_requests(c['scenario'], c['params'], 42)
    assert original != generate_requests(c['scenario'], c['params'], 43)


def test_a03_reroute_nearest_tie_id_and_extra_segment_only():
    c = snapshot((1,10,0,0), duration=3)
    e = make_engine(c)
    e.network.routes['s2','s1']['distance_m'] = 500
    e.network.routes['s2','s3']['distance_m'] = 100
    e.network.routes['s2','s4']['distance_m'] = 100
    e.requests = [event()]
    e.step()
    state = e.step()
    assert_state(state)
    assert len(state['rides']) == 1
    ride = state['rides'][0]
    assert ride['destination_id'] == 's3' and ride['arrival_sec'] == 120
    assert ride['extra_distance_m'] == 100 and ride['reroute_count'] == 1
    assert state['metrics']['first_return_attempts'] == 1
    assert state['metrics']['first_return_success'] == 0
    state = e.step()
    assert_state(state)
    assert state['stations'][2]['stock'] == 1
    assert state['metrics']['first_return_attempts'] == 1
    assert state['metrics']['extra_ride_distance_m'] == 100


def test_a03_no_candidate_policy_is_isolated_defensive_branch():
    e = make_engine(snapshot((10,10)))
    ride = {'id':'ride-000000000001','reroute_count':0,'extra_distance_m':0}
    # Policy branch ONLY, not a valid whole-system run (per AC-A03 warning).
    e._return(ride, 's2')
    assert e.waiting[ride['id']]['since_sec'] == 0
    assert e.waiting[ride['id']]['first_attempted'] is True


def test_a03_waiting_retry_uses_conserved_injected_initial_state():
    e = make_engine(snapshot((1,0)))
    e.stations['s1']['stock'] = 0
    e.waiting['ride-000000000001'] = {'id':'ride-000000000001','station_id':'s1','since_sec':0,
        'first_attempted':True,'reroute_count':0,'extra_distance_m':0}
    e.cursor = 60
    e.metrics['first_return_attempts'] = 1
    e.assert_invariants()
    state = e.step()
    assert_state(state)
    assert state['vehicles']['waiting'] == 0 and state['stations'][0]['stock'] == 1
    assert state['metrics']['first_return_attempts'] == 1
    assert state['metrics']['utilization'] == 0


def test_a03_new_waiting_is_not_retried_in_same_step():
    e = make_engine(snapshot((1,10)))
    # Legal disconnected graph: s1 has the freed slot but s2 cannot reach it.
    e.network.routes.pop(('s2','s1'))
    e.requests = [event()]
    e.step()
    calls = []
    original = e._return
    def observed(ride, station):
        calls.append(ride['id'])
        return original(ride, station)
    e._return = observed
    state = e.step()
    assert_state(state)
    assert len(state['waiting']) == 1 and len(calls) == 1
    e.step()
    assert len(calls) == 2


def plans(e, quantities):
    return [{'source_id':a,'destination_id':b,'quantity':q,
        'distance_m':e.network.route(a,b)['distance_m'], 'route':e.network.route(a,b)['polyline']}
        for a,b,q in quantities]


def test_a04_dispatch_reservation_arrival_idempotency():
    c = snapshot((10,0))
    c['algorithm'] = 'greedy'
    e = make_engine(c)
    e.dispatcher.plans = plans(e, [('s1','s2',4)])
    e.step()
    result = e.dispatch('confirm-1')
    assert e.dispatch('confirm-1') == result
    assert e.stations['s1']['stock'] == 6
    assert e.stations['s2']['stock'] == 0 and e.stations['s2']['reserved_inbound'] == 4
    assert e.snapshot()['vehicles']['transporting'] == 4
    assert e.snapshot()['metrics']['dispatch_cost_bike_m'] == 800
    e.step()  # 200m at 10km/h takes 120s after rounding.
    state = e.step()
    assert_state(state)
    assert e.stations['s2']['stock'] == 4 and e.stations['s2']['reserved_inbound'] == 0
    assert e.step() == state
    assert e.dispatch('confirm-1') == result


@pytest.mark.parametrize('items,code', [
    ([('s1','s2',6),('s1','s3',5)],'STALE_PLAN'),
    ([('s1','s2',6),('s3','s2',5)],'STALE_PLAN'),
    ([('s1','s2',51)],'INVALID_PLAN'),
    ([('s1','s2',0)],'INVALID_PLAN'),
])
def test_a04_invalid_whole_batch_leaves_all_business_state_unchanged(items, code):
    c = snapshot((10,0,10))
    c['algorithm'] = 'greedy'
    e = make_engine(c)
    e.step()
    before = e.snapshot()
    e.dispatcher.plans = plans(e, items)
    for _ in range(2):
        with pytest.raises(DomainError) as error:
            e.dispatch('bad-plan')
        assert error.value.code == code
        assert e.snapshot() == before


def test_a04_normal_returns_respect_transport_reservation():
    c = snapshot((2,9,1), duration=3)
    c['algorithm'] = 'greedy'
    e = make_engine(c)
    e.requests = [event(origin='s3')]
    e.step()
    e.dispatcher.plans = plans(e, [('s1','s2',1)])
    e.dispatch('reserve-last-slot')
    state = e.step()  # Ride arrives before transport; full due to reservation, must reroute.
    assert_state(state)
    assert state['metrics']['first_return_success'] == 0
    assert e.stations['s2']['stock'] == 9 and e.stations['s2']['reserved_inbound'] == 1
    assert state['rides'][0]['destination_id'] == 's1'


def test_a05_terminal_boundary_arrivals_only_and_step_idempotent():
    e = make_engine(snapshot((2,0), duration=1))
    e.requests = [event(), event(t=60, index=2)]  # Deliberately inject end-boundary request.
    e.config['dispatch_times_sec'] = [60]
    e.step()
    state = e.step()
    assert_state(state)
    assert state['status'] == 'completed' and state['sim_time_sec'] == 60
    assert state['metrics']['request_count'] == 1
    assert state['metrics']['first_return_success'] == 1
    assert e.request_cursor == 1
    assert e.step() == state
    assert [s['sim_time_sec'] for s in e.samples] == [0,60]


def test_a05_zero_distance_is_next_step_and_snapshot_is_detached():
    e = make_engine()
    e.network.routes['s1','s2']['distance_m'] = 0
    e.requests = [event()]
    state = e.step()
    assert state['rides'][0]['arrival_sec'] == 60
    state['stations'][0]['stock'] = 999
    assert e.stations['s1']['stock'] == 0


def test_a05_pause_speed_do_not_change_requests_or_business_results():
    c = snapshot((10,0), duration=5)
    c['scenario']['od_demands'] = [{'origin_id':'s1','destination_id':'s2','rate_per_min':2,'periods':[]}]
    a, b = make_engine(c), make_engine(c)
    assert a.requests == b.requests
    a.step(); b.step()
    b.status = 'paused'
    paused = b.snapshot()
    assert b.step() == paused
    b.current_speed = 600
    b.status = 'running'
    while a.status == 'running':
        a.step(); b.step()
    assert a.snapshot()['metrics'] == b.snapshot()['metrics']
    assert a.snapshot()['stations'] == b.snapshot()['stations']
    assert a.samples == b.samples
