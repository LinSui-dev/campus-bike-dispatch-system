from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from threading import Barrier
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, func
from app.models import tables as t
from app.services.validation import validate
from .conftest import read, request, assert_state

P = '/api/v1'


def start(client, key='r1', **updates):
    response = client.post(P+'/runs', json=request(key, **updates))
    assert response.status_code == 201, response.text
    assert_state(response.json())
    return response.json()['run_id']


def control(client, run, **command):
    return client.post(f'{P}/runs/{run}/control', json=command)


def count(store, table):
    with store.engine.connect() as db:
        return db.execute(select(func.count()).select_from(table)).scalar_one()


def test_a01_station_create_patch_normalization_and_reference_delete(client):
    value = {k:v for k,v in read('default_stations.json')[0].items() if k not in ('road_edge_id','road_offset')}
    value['id'] = 'new-station'
    response = client.post(P+'/stations', json=value)
    assert response.status_code == 201
    validate('Station', response.json())
    assert client.post(P+'/stations', json=value).json()['code'] == 'DUPLICATE_ID'
    moved = client.patch(P+'/stations/new-station', json={'x':120, 'y':210})
    assert moved.status_code == 200 and moved.json()['x'] == 120
    assert 'road_offset' in moved.json()
    assert client.delete(P+'/stations/s1').json()['code'] == 'RELATED_OD'
    assert client.delete(P+'/stations/s1?clear_related_od=true').status_code == 204
    assert all('s1' not in (o['origin_id'],o['destination_id'])
               for s in client.get(P+'/scenarios').json()['items'] for o in s['od_demands'])


@pytest.mark.parametrize('patch,status,code', [
    ({'capacity':0},422,'VALIDATION_ERROR'),
    ({'initial_stock':21},400,'INVALID_STATION'),
    ({'x':120},422,'VALIDATION_ERROR'),
    ({'road_offset':0.5},422,'VALIDATION_ERROR'),
    ({'id':'override'},422,'VALIDATION_ERROR'),
    ({'x':1200,'y':20},400,'INVALID_STATION'),
    ({'active':False},409,'RELATED_OD'),
    ({},422,'VALIDATION_ERROR'),
    ({'capacity':True},422,'VALIDATION_ERROR'),
])
def test_a01_invalid_patch_leaves_db_unchanged(client, patch, status, code):
    before = client.get(P+'/stations').json()
    response = client.patch(P+'/stations/s1', json=patch)
    assert response.status_code == status and response.json()['code'] == code
    assert response.json()['details'] is not None
    assert client.get(P+'/stations').json() == before


def test_a01_scenario_config_crud_and_references(client):
    value = read('scenarios.json')[0] | {'id':'custom','is_preset':False}
    assert client.post(P+'/scenarios',json=value).status_code == 201
    assert client.patch(P+'/scenarios/custom', json={'name':'test'}).json()['name'] == 'test'
    assert client.patch(P+'/scenarios/custom', json={'is_preset':True}).status_code == 422
    config = read('default_config.json') | {'id':'custom-config','scenario_id':'custom'}
    assert client.post(P+'/configs',json=config).status_code == 201
    assert client.delete(P+'/scenarios/custom').json()['code'] == 'IN_USE'
    assert client.patch(P+'/configs/custom-config',json={'seed':43}).json()['seed'] == 43
    assert client.delete(P+'/configs/custom-config').status_code == 204
    assert client.delete(P+'/scenarios/custom').status_code == 204
    assert client.delete(P+'/scenarios/morning').json()['code'] == 'PRESET_SCENARIO'
    assert client.post(P+'/scenarios',json=read('scenarios.json')[0]).status_code == 400


@pytest.mark.parametrize('demands,code', [
    ([{'origin_id':'s1','destination_id':'s1','rate_per_min':1,'periods':[]}], 'INVALID_OD'),
    ([{'origin_id':'missing','destination_id':'s2','rate_per_min':1,'periods':[]}], 'INVALID_OD'),
    ([{'origin_id':'s1','destination_id':'s2','rate_per_min':1,'periods':[
        {'start_min':0,'end_min':30,'multiplier':1}, {'start_min':20,'end_min':40,'multiplier':2}]}], 'INVALID_PERIOD'),
    ([{'origin_id':'s1','destination_id':'s2','rate_per_min':1,'periods':[
        {'start_min':0,'end_min':121,'multiplier':1}]}], 'INVALID_PERIOD'),
])
def test_a01_od_invalid_replace_is_atomic(client, demands, code):
    before = client.get(P+'/scenarios/morning').json()
    response = client.put(P+'/scenarios/morning/od',json={'od_demands':demands})
    assert response.status_code == 400 and response.json()['code'] == code
    assert client.get(P+'/scenarios/morning').json() == before


def test_a01_paused_configuration_is_frozen_and_context_is_atomic(client):
    run = start(client)
    assert control(client,run,action='pause').json()['status'] == 'paused'
    before = client.get(P+'/stations').json()
    assert client.patch(P+'/stations/s1',json={'name':'blocked'}).json()['code'] == 'BUSY'
    assert client.put(P+'/scenarios/morning/od',json={'od_demands':[]}).status_code == 409
    assert client.delete(P+'/configs/fixture-default').status_code == 409
    assert client.get(P+'/stations').json() == before
    state = control(client,run,action='speed',value=120).json()
    assert state['context']['params']['speed'] == 60 and state['context']['current_speed'] == 120
    assert client.get(f'{P}/runs/{run}/state').json() == state
    assert control(client,run,action='pause').json() == state
    assert control(client,run,action='resume').json()['seq'] > state['seq']


@pytest.mark.parametrize('update,status,code', [
    ({'seed':-1},422,'VALIDATION_ERROR'),
    ({'seed':4294967296},422,'VALIDATION_ERROR'),
    ({'algorithm':'other'},422,'VALIDATION_ERROR'),
    ({'unexpected':1},422,'VALIDATION_ERROR'),
    ({'scenario_id':'missing'},404,'NOT_FOUND'),
])
def test_invalid_run_errors_are_uniform(client,update,status,code):
    response = client.post(P+'/runs',json=request(**update))
    assert response.status_code == status
    validate('Error',response.json())
    assert response.json()['code'] == code
    assert client.get(P+'/runtime').json()['mode'] == 'idle'


def test_invalid_control_and_params(client):
    params = read('default_config.json')['params'] | {'step_sec':61}
    assert client.post(P+'/runs',json=request(params=params)).json()['code'] == 'INVALID_PARAMS'
    short = read('default_config.json')['params'] | {'duration_min':1}
    assert client.post(P+'/runs',json=request('short',params=short)).json()['code'] == 'INVALID_PERIOD'
    run = start(client,'valid')
    for command in [{'action':'reset'}, {'action':'pause','save':False}, {'action':'speed','value':0}]:
        assert client.post(f'{P}/runs/{run}/control',json=command).status_code == 422
    assert client.post(P+'/runs',json=[]).status_code == 422


def test_a06_stop_is_saved_once_and_cannot_resume(client):
    run = start(client)
    stopped = control(client,run,action='stop')
    assert stopped.status_code == 200 and stopped.json()['status'] == 'stopped'
    assert control(client,run,action='stop').json() == stopped.json()
    assert client.get(P+'/runs').json()['total'] == 1
    assert client.get(P+'/runtime').json()['mode'] == 'idle'
    assert control(client,run,action='resume').status_code == 409
    validate('RunSummary',client.get(f'{P}/runs/{run}').json()['run'])
    assert client.get(f'{P}/runs/{run}/metrics').json()['total'] == 1


@pytest.mark.parametrize('save', [False,True])
def test_a06_reset_choice_retry_conflict_and_no_history_for_discard(client, save):
    run = start(client)
    response = control(client,run,action='reset',save=save)
    assert response.status_code == 200
    assert response.json() == {'mode':'idle','saved':save,'run_id':run}
    assert client.get(P+'/runs').json()['total'] == int(save)
    assert control(client,run,action='reset',save=save).json() == response.json()
    assert control(client,run,action='reset',save=not save).json()['code'] == 'IDEMPOTENCY_CONFLICT'
    assert client.get(f'{P}/runs/{run}/state').status_code == 404


def test_a06_transaction_failure_holds_slot_rolls_back_and_retry_saves_once(client,monkeypatch):
    run = start(client)
    store = client.app.state.store
    original = store._save_children
    def fail_after_first_write(db,engine):
        original(db,engine)
        raise RuntimeError('INJECTED failure before commit')
    monkeypatch.setattr(store,'_save_children',fail_after_first_write)
    response = control(client,run,action='stop')
    assert response.status_code == 500 and response.json()['code'] == 'SAVE_FAILED'
    for table in [t.runs,t.metrics,t.tasks]:
        assert count(store,table) == 0
    assert client.get(P+'/runtime').json()['mode'] == 'interactive'
    assert client.post(P+'/runs',json=request('blocked')).json()['code'] == 'BUSY'
    monkeypatch.setattr(store,'_save_children',original)
    assert control(client,run,action='stop').status_code == 200
    assert count(store,t.runs) == 1 and count(store,t.metrics) == 1
    commands = client.get(f'{P}/runs/{run}').json()['commands']
    assert len([c for c in commands if c['action']=='stop']) == 1


def test_a06_save_failure_can_be_explicitly_discarded(client,monkeypatch):
    run = start(client)
    monkeypatch.setattr(client.app.state.store,'save_run',lambda *args: (_ for _ in ()).throw(RuntimeError('injected')))
    assert control(client,run,action='stop').status_code == 500
    assert control(client,run,action='reset',save=False).json()['saved'] is False
    assert client.get(P+'/runtime').json()['mode'] == 'idle'
    assert client.get(P+'/runs').json()['total'] == 0


def test_a06_abnormal_shutdown_restarts_idle_without_partial_history(app_factory):
    app = app_factory()
    with TestClient(app) as client:
        old = start(client,'saved')
        assert control(client,old,action='stop').status_code == 200
        start(client,'unfinished')
        client.patch(P+'/stations/s1',json={'name':'busy'})
    with TestClient(app_factory()) as client:
        assert client.get(P+'/runtime').json()['mode'] == 'idle'
        assert client.get(P+'/runs').json()['total'] == 1
        assert client.get(f'{P}/runs/{old}').status_code == 200


def test_a07_two_concurrent_interactive_creates_and_failed_idempotency(client):
    barrier = Barrier(2)
    def call(key):
        barrier.wait()
        return client.post(P+'/runs',json=request(key))
    with ThreadPoolExecutor(2) as pool:
        responses = list(pool.map(call,['one','two']))
    assert sorted(r.status_code for r in responses) == [201,409]
    successful = next(r for r in responses if r.status_code == 201).json()
    key = next(key for key,r in zip(['one','two'],responses) if r.status_code == 201)
    assert client.post(P+'/runs',json=request(key)).json() == successful
    assert client.post(P+'/runs',json=request(key,seed=43)).json()['code'] == 'IDEMPOTENCY_CONFLICT'
    failed_key = 'two' if key == 'one' else 'one'
    control(client,successful['run_id'],action='reset',save=False)
    assert client.post(P+'/runs',json=request(failed_key)).json()['code'] == 'BUSY'
    assert client.post(P+'/runs',json=request('new-id')).status_code == 201


def test_a08_historical_snapshot_metrics_tasks_survive_live_station_delete(client):
    run = start(client)
    control(client,run,action='stop')
    before = client.get(f'{P}/runs/{run}').json()
    before_metrics = client.get(f'{P}/runs/{run}/metrics').json()
    assert client.delete(P+'/stations/s1?clear_related_od=true').status_code == 204
    assert client.get(f'{P}/runs/{run}').json() == before
    assert client.get(f'{P}/runs/{run}/metrics').json() == before_metrics
    assert any(s['id']=='s1' for s in before['snapshot']['stations'])
    validate('ConfigSnapshot',before['snapshot'])


def test_restart_keeps_edited_configuration_and_does_not_reimport_deleted_defaults(app_factory):
    with TestClient(app_factory()) as client:
        assert client.patch(P+'/stations/s1',json={'name':'edited'}).status_code == 200
        assert client.delete(P+'/configs/fixture-default').status_code == 204
    with TestClient(app_factory()) as client:
        assert client.get(P+'/stations').json()['items'][0]['name'] == 'edited'
        assert client.get(P+'/configs').json()['total'] == 0


def test_websocket_context_seq_pause_reset_and_unknown_run(client):
    run = start(client)
    with client.websocket_connect('/ws/runs/'+run) as socket:
        initial = socket.receive_json()
        assert initial['type'] == 'state'
        assert initial['context']['seed'] == 42
        changed = control(client,run,action='pause').json()
        pushed = socket.receive_json()
        assert pushed['seq'] == changed['seq'] > initial['seq']
        control(client,run,action='reset',save=False)
        final = socket.receive_json()
        assert final['status'] == 'stopped' and final['seq'] > pushed['seq']
        assert socket.receive()['type'] == 'websocket.close'
    with client.websocket_connect('/ws/runs/unknown') as socket:
        error = socket.receive_json()
        assert error['type'] == 'error' and error['code'] == 'NOT_FOUND'
        assert socket.receive()['code'] == 1008


def test_default_production_ports_use_real_modules_and_no_test_doubles(tmp_path):
    from app.main import create_app
    app = create_app(database_url='sqlite:///'+(tmp_path/'real.db').as_posix(),data_profile='fixture',auto_advance=False)
    with TestClient(app,raise_server_exceptions=False) as client:
        assert client.get(P+'/health').json()['stage'] == 'implemented'
        response = client.post(P+'/runs',json=request())
        assert response.status_code == 201 and response.json()['status'] == 'running'
        assert client.get(P+'/runtime').json()['mode']=='interactive'
        assert client.post(P+'/runs/'+response.json()['run_id']+'/control',json={'action':'stop'}).status_code==200
        assert client.get(P+'/runtime').json()['mode']=='idle'
        assert client.get(P+'/runs').json()['total']==1


def test_api_openapi_uses_contract_schemas_and_uniform_errors(client):
    schema = client.get('/openapi.json').json()
    assert schema['components']['schemas']['RunContext']['required']
    reference = schema['paths'][P+'/stations']['post']['requestBody']['content']['application/json']['schema']['$ref']
    assert reference == '#/components/schemas/StationCreate'
    for url in [P+'/missing',P+'/scenarios/missing']:
        response = client.get(url)
        assert response.status_code == 404
        validate('Error',response.json())


def test_empty_active_set_rejected_and_zero_vehicle_run_is_valid(client):
    for scenario in client.get(P+'/scenarios').json()['items']:
        assert client.put(P+'/scenarios/'+scenario['id']+'/od',json={'od_demands':[]}).status_code==200
    for station in client.get(P+'/stations').json()['items']:
        assert client.patch(P+'/stations/'+station['id'],json={'active':False}).status_code==200
    assert client.post(P+'/runs',json=request()).json()['code']=='NO_ACTIVE_STATIONS'
    assert client.patch(P+'/stations/s1',json={'active':True,'initial_stock':0}).status_code==200
    run=start(client,'zero')
    state=client.get(f'{P}/runs/{run}/state').json()
    assert len(state['stations'])==1 and state['vehicles']['total']==0
    assert state['metrics']['utilization'] is None
    assert state['metrics']['borrow_success_rate'] is None


def test_campus_missing_data_does_not_fall_back_to_fixture(tmp_path, monkeypatch):
    import app.main as main_module
    monkeypatch.setattr(main_module, 'ROOT', tmp_path)  # empty data root: campus files absent
    app=main_module.create_app(database_url='sqlite:///'+(tmp_path/'campus.db').as_posix(),data_profile='campus')
    with pytest.raises(RuntimeError,match='DATA_PROFILE=campus'):
        with TestClient(app):
            pass
