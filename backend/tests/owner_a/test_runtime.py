"""A-side batch callback, slot and real worker tests. Coordinator here is an explicit double."""
from copy import deepcopy
import threading
import time
import pytest
from fastapi.testclient import TestClient
from app.engine.errors import DomainError
from app.models import tables as t
from app.services.validation import validate
from .conftest import read, request, DispatchDouble, NetworkDouble
from .test_api import P, start, control, count


class SerialRunnerDouble:
    """No B aggregation/optimization: just exercise A's real run_once callback."""
    def run_batch(self, request, run_once, on_progress):
        items = [{'scenario_id':s,'algorithm':a,'seed':seed,'status':'pending','run_id':None,'error':None}
            for s in request['scenario_ids'] for a in request['algorithms'] for seed in request['seeds']]
        result = {'id':request['request_id'],'status':'running','total':len(items),'finished':0,
                  'items':items,'aggregates':[]}
        for item in items:
            item['status'] = 'running'
            on_progress(deepcopy(result))
            spec = {k:item[k] for k in ('scenario_id','algorithm','seed')}
            spec.update(batch_id=request['request_id'],params=request['params'],
                        dispatch_times_sec=request['dispatch_times_sec'],batch_request=deepcopy(request))
            try:
                outcome = run_once(spec)
                validate('RunOutcome',outcome)
                item.update(status='completed',run_id=outcome['run_id'])
            except DomainError as exc:
                item.update(status='failed',error=exc.dto())
            result['finished'] += 1
            on_progress(deepcopy(result))
        failures = sum(i['status']=='failed' for i in items)
        result['status'] = 'failed' if failures==len(items) else ('partial_failed' if failures else 'completed')
        return result


def batch_request(key='batch-1'):
    return {'request_id':key,'scenario_ids':['morning'],'algorithms':['none','greedy'],
            'seeds':[42,43], 'params':read('default_config.json')['params'] | {'duration_min':1},
            'dispatch_times_sec':[0]}


def empty_od(client):
    assert client.put(P+'/scenarios/morning/od',json={'od_demands':[]}).status_code==200


def test_real_a_run_once_callback_rebuilds_and_persists_each_run(app_factory):
    app = app_factory(runner_factory=SerialRunnerDouble)
    with TestClient(app) as client:
        empty_od(client)
        request = batch_request()
        response = client.post(P+'/batches',json=request)
        assert response.status_code == 202
        assert all(i['status']=='pending' for i in response.json()['items'])
        app.state.manager.batch_thread.join(timeout=10)
        assert not app.state.manager.batch_thread.is_alive()
        result = client.get(P+'/batches/batch-1').json()
        validate('BatchResult',result)
        assert result['status']=='completed' and result['finished']==4
        assert len({i['run_id'] for i in result['items']})==4
        assert client.get(P+'/runtime').json()['mode']=='idle'
        assert client.get(P+'/runs').json()['total']==4
        for item in result['items']:
            history = client.get(P+'/runs/'+item['run_id']).json()
            assert history['snapshot']['batch_request']==request
            assert history['snapshot']['dispatch_times_sec']==[0]
            assert history['run']['summary']['request_count']==0
            assert history['run']['summary']['utilization']==0
            assert client.get(P+'/runs/'+item['run_id']+'/metrics').json()['total']==2
    with TestClient(app_factory(runner_factory=SerialRunnerDouble)) as client:
        assert client.get(P+'/batches/batch-1').json()==result
        assert client.post(P+'/batches',json=request).json()['code']=='DUPLICATE_ID'


def test_a07_entire_batch_holds_slot_even_between_children(app_factory):
    entered, release = threading.Event(), threading.Event()
    class BlockingRunner(SerialRunnerDouble):
        def run_batch(self, request, run_once, on_progress):
            entered.set()
            assert release.wait(10)
            return super().run_batch(request,run_once,on_progress)
    app = app_factory(runner_factory=BlockingRunner)
    with TestClient(app) as client:
        empty_od(client)
        original = client.post(P+'/batches',json=batch_request())
        assert entered.wait(2)
        try:
            assert client.get(P+'/runtime').json()=={'mode':'batch','batch_id':'batch-1','run_id':None}
            assert client.post(P+'/batches',json=batch_request()).json()==original.json()
            assert client.post(P+'/runs',json=request('interactive')).json()['code']=='BUSY'
            assert client.post(P+'/batches',json=batch_request('other-batch')).json()['code']=='BUSY'
            assert client.patch(P+'/stations/s1',json={'name':'blocked'}).json()['code']=='BUSY'
        finally:
            release.set()
        app.state.manager.batch_thread.join(timeout=10)
        assert client.get(P+'/runtime').json()['mode']=='idle'


def test_a07_interactive_and_batch_concurrent_start_only_one_slot(app_factory):
    entered, release = threading.Event(), threading.Event()
    class Block:
        def run_batch(self,*args):
            entered.set()
            release.wait(10)
            raise DomainError('TEST_EXIT','Test coordinator exit')
    app = app_factory(runner_factory=Block)
    with TestClient(app) as client:
        empty_od(client)
        barrier = threading.Barrier(2)
        results=[]
        def interactive():
            barrier.wait()
            results.append(client.post(P+'/runs',json=request()))
        def batch():
            barrier.wait()
            results.append(client.post(P+'/batches',json=batch_request()))
        threads=[threading.Thread(target=interactive),threading.Thread(target=batch)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(5)
        try:
            assert sorted(r.status_code for r in results) in ([201,409],[202,409])
        finally:
            release.set()


def test_default_runner_runs_batch_and_releases_slot(app_factory):
    app = app_factory()
    with TestClient(app) as client:
        empty_od(client)
        assert client.post(P+'/batches',json=batch_request()).status_code==202
        app.state.manager.batch_thread.join(120)
        response = client.get(P+'/batches/batch-1')
        assert response.status_code==200
        result=response.json()
        assert result['status']=='completed' and result['finished']==result['total']==4
        assert all(i['status']=='completed' and i['run_id'] for i in result['items'])
        assert client.get(P+'/runs').json()['total']==4
        assert client.get(P+'/runtime').json()['mode']=='idle'


def test_interrupted_batch_history_is_read_only_from_committed_children(app_factory):
    class Interrupted(SerialRunnerDouble):
        def run_batch(self, req, run_once, on_progress):
            run_once({'batch_id':req['request_id'],'scenario_id':'morning','algorithm':'none','seed':42,
                      'params':req['params'],'dispatch_times_sec':req['dispatch_times_sec'], 'batch_request':req})
            raise RuntimeError('Injected interruption after committed child')
    with TestClient(app_factory(runner_factory=Interrupted)) as client:
        empty_od(client)
        assert client.post(P+'/batches',json=batch_request()).status_code==202
        client.app.state.manager.batch_thread.join(5)
        assert client.get(P+'/runs').json()['total']==1
    with TestClient(app_factory()) as client:
        result=client.get(P+'/batches/batch-1').json()
        validate('BatchResult',result)
        assert result['status']=='interrupted' and result['finished']==1 and result['total']==4
        assert result['aggregates']==[]
        assert client.get(P+'/runtime').json()['mode']=='idle'


def test_background_worker_completes_saves_and_releases(tmp_path):
    from app.main import create_app
    app=create_app(database_url='sqlite:///'+(tmp_path/'worker.db').as_posix(),data_profile='fixture',
                   network_factory=NetworkDouble,dispatch_factory=DispatchDouble,auto_advance=True)
    with TestClient(app) as client:
        empty_od(client)
        params=read('default_config.json')['params'] | {'duration_min':1,'speed':600}
        run=start(client,params=params)
        deadline=time.monotonic()+5
        while time.monotonic()<deadline and client.get(P+'/runtime').json()['mode']!='idle':
            time.sleep(0.02)
        assert client.get(f'{P}/runs/{run}/state').json()['status']=='completed'
        assert client.get(P+'/runs').json()['total']==1


def test_a06_completion_save_failure_holds_slot_until_retry(client,monkeypatch):
    run=start(client)
    m=client.app.state.manager
    original=m.store.save_run
    def fail(*args):
        raise RuntimeError('INJECTED save failure')
    monkeypatch.setattr(m.store,'save_run',fail)
    for _ in range(120):
        m.advance()
    assert m.state(run)['status']=='completed' and m.runtime()['mode']=='interactive'
    assert count(m.store,t.runs)==0
    assert client.post(P+'/runs',json=request('blocked')).status_code==409
    monkeypatch.setattr(m.store,'save_run',original)
    assert control(client,run,action='stop').json()['status']=='completed'
    assert count(m.store,t.runs)==1 and m.runtime()['mode']=='idle'


def test_a06_engine_exception_aborts_without_history_and_can_discard(client,monkeypatch):
    run=start(client)
    m=client.app.state.manager
    def fail(*args):
        raise RuntimeError('INJECTED engine failure')
    monkeypatch.setattr(m.get_engine(run),'step',fail)
    m.advance()
    assert m.state(run)['status']=='aborted' and m.runtime()['mode']=='idle'
    assert client.get(P+'/runs').json()['total']==0
    assert control(client,run,action='stop').status_code==409
    assert control(client,run,action='reset',save=False).status_code==200


def test_a04_api_dispatch_retry_and_a08_task_history_survives_deletion(app_factory):
    from .conftest import DispatchDouble
    class Planned(DispatchDouble):
        def plan(self, algorithm, supply_demand, network, max_dispatch):
            route=network.route('s1','s2')
            return [{'source_id':'s1','destination_id':'s2','quantity':4,
                     'distance_m':route['distance_m'],'route':route['polyline']}]
    app=app_factory()
    # Injection remains test-only, before any engine construction.
    with TestClient(app) as client:
        app.state.manager.dispatch_factory=Planned
        run=start(client,algorithm='greedy')
        original=client.post(f'{P}/runs/{run}/dispatch',json={'request_id':'dispatch-1'})
        assert original.status_code==200
        assert client.post(f'{P}/runs/{run}/dispatch',json={'request_id':'dispatch-1'}).json()==original.json()
        state=client.get(f'{P}/runs/{run}/state').json()
        assert state['stations'][0]['stock']==6 and state['stations'][1]['reserved_inbound']==4
        assert state['metrics']['dispatch_quantity']==4
        control(client,run,action='stop')
        saved_tasks=app.state.store.all(t.tasks)
        assert len(saved_tasks)==1 and saved_tasks[0]['status']=='transporting'
        assert client.delete(P+'/stations/s1?clear_related_od=true').status_code==204
        assert app.state.store.all(t.tasks)==saved_tasks


def test_run_once_cannot_bypass_global_slot(client):
    req=batch_request()
    spec={'batch_id':req['request_id'],'scenario_id':'morning','algorithm':'none','seed':42,
          'params':req['params'],'dispatch_times_sec':[],'batch_request':req}
    with pytest.raises(DomainError,match='run_once'):
        client.app.state.manager.run_once(spec)


@pytest.mark.parametrize('times', [[1],[60]])
def test_batch_rejects_unaligned_or_terminal_triggers(client,times):
    empty_od(client)
    response=client.post(P+'/batches',json=batch_request() | {'dispatch_times_sec':times})
    assert response.status_code==400 and response.json()['code']=='INVALID_DISPATCH_TIME'
    assert client.get(P+'/runtime').json()['mode']=='idle'


def test_batch_summary_failure_keeps_children_and_is_reported_as_contract_gap(app_factory,monkeypatch):
    app=app_factory(runner_factory=SerialRunnerDouble)
    with TestClient(app) as client:
        empty_od(client)
        def fail(*args):
            raise RuntimeError('INJECTED batch summary persistence failure')
        monkeypatch.setattr(app.state.store,'save_batch',fail)
        assert client.post(P+'/batches',json=batch_request()).status_code==202
        app.state.manager.batch_thread.join(10)
        assert client.get(P+'/batches/batch-1').status_code==500
        assert count(app.state.store,t.batches)==0
        assert count(app.state.store,t.runs)==4
    with TestClient(app_factory()) as client:
        recovered=client.get(P+'/batches/batch-1').json()
        assert recovered['status']=='interrupted' and recovered['finished']==4
        assert recovered['aggregates']==[]  # No fabricated recovered statistics.
