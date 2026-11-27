"""One process, one experiment slot. Every engine command and step uses the same RLock."""
from copy import deepcopy
from importlib.metadata import version
import json
import platform
import threading
import time
from uuid import uuid4
from contracts.python_interfaces import NetworkError

from app.engine import Engine
from app.engine.errors import DomainError
from app.models import tables as t
from .store import utc_now
from .validation import validate, params_rules, scenario_rules, dispatch_times_rules, station_rules


def dependency_error(exc):
    if isinstance(exc, DomainError):
        return exc
    if isinstance(exc, NetworkError):
        return DomainError(exc.code, str(exc))
    if isinstance(exc, NotImplementedError):
        return DomainError('NOT_IMPLEMENTED', '依赖模块尚未实现', status=501)
    return DomainError('INTERNAL_ERROR', '内部执行失败', status=500)


class RunManager:
    def __init__(self, store, network_factory, dispatch_factory, runner_factory, *, auto_advance=True):
        self.store = store
        self.network_factory, self.dispatch_factory, self.runner_factory = network_factory, dispatch_factory, runner_factory
        self.lock = threading.RLock()
        self.mode, self.run_id, self.batch_id = 'idle', None, None
        self.engines, self.created, self.saved = {}, {}, set()
        self.receipts, self.reset_receipts, self.closed_states = {}, {}, {}
        self.batch_results, self.batch_errors = {}, {}
        self.save_error = None
        self.next_tick = 0
        self.shutdown = threading.Event()
        self.batch_thread = None
        self.worker = None
        if auto_advance:
            self.worker = threading.Thread(target=self._work, daemon=True, name='simulation-owner')
            self.worker.start()

    def close(self):
        self.shutdown.set()
        if self.worker:
            self.worker.join()
        if self.batch_thread:
            self.batch_thread.join()
        # Deliberately do not save partial experiments on shutdown.

    def runtime(self):
        with self.lock:
            return {'mode': self.mode, 'run_id': self.run_id, 'batch_id': self.batch_id}

    def idle(self):
        if self.mode != 'idle':
            raise DomainError('BUSY', '已有实验占用运行槽；暂停或保存失败时仍占槽', status=409)

    def _release(self):
        self.mode, self.run_id, self.batch_id = 'idle', None, None
        self.save_error = None

    def network(self, stations=None):
        return self.network_factory(deepcopy(self.store.network),
            deepcopy(self.store.all(t.stations) if stations is None else stations),
            snap_tolerance_px=self.store.metadata['snap_tolerance_px'])

    def station_write(self, value, identifier=None):
        self.idle()
        if identifier:
            validate('StationPatch', value)
            old = self.store.get(t.stations, identifier)
            candidate = {k: v for k, v in (old | value).items() if k not in ('road_edge_id','road_offset')}
        else:
            validate('StationCreate', value)
            self.store.ensure_new(t.stations, value['id'])
            candidate = value
        validate('StationCreate', candidate)
        station_rules(candidate)
        station = self.network().validate_station(deepcopy(candidate))
        validate('Station', station)
        station_rules(station)
        if station['id'] != candidate['id']:
            raise DomainError('INVALID_STATION', '道路服务不能改变站点ID')
        stations = [s for s in self.store.all(t.stations) if s['id'] != station['id']] + [station]
        self.network(stations)  # Rebuild before committing; no stale cache survives a structure edit.
        return self.store.save_station(station, replace=identifier is not None)

    def snapshot_config(self, request, *, batch_request=None, dispatch_times=None):
        params_rules(request['params'])
        scenario = self.store.scenario(request['scenario_id'])
        stations = [s for s in self.store.all(t.stations) if s['active']]
        if not stations:
            raise DomainError('NO_ACTIVE_STATIONS', '至少需要一个启用停车点')
        scenario_rules(scenario, {s['id']: s for s in stations}, request['params']['duration_min'])
        times = sorted(dispatch_times or [])
        dispatch_times_rules(times, request['params'])
        network = self.network(stations)
        # Invalid/unreachable OD must fail before any borrow or partial engine is published.
        for od in scenario['od_demands']:
            network.route(od['origin_id'], od['destination_id'])
        snapshot = {'versions': {'contract': '1.1.0', 'engine': 'a-engine-v1',
                    'generator': 'poisson-exp-v1', 'network': self.store.network['version'],
                    'python': platform.python_version(), 'networkx': version('networkx')},
                    'network': deepcopy(self.store.network), 'stations': stations, 'scenario': scenario,
                    'params': deepcopy(request['params']), 'seed': request['seed'],
                    'algorithm': request['algorithm'], 'dispatch_times_sec': times,
                    'commands': [], 'batch_request': deepcopy(batch_request)}
        validate('ConfigSnapshot', snapshot)
        return snapshot, network

    def _idempotent(self, namespace, request, operation):
        key = namespace, request['request_id']
        payload = json.dumps(request, sort_keys=True, separators=(',', ':'), allow_nan=False)
        if key in self.receipts:
            previous, result = self.receipts[key]
            if previous != payload:
                raise DomainError('IDEMPOTENCY_CONFLICT', '相同request_id不能更改请求', status=409)
            if isinstance(result, DomainError):
                raise result
            return deepcopy(result)
        try:
            result = operation()
        except Exception as exc:
            error = dependency_error(exc)
            self.receipts[key] = payload, error
            raise error from exc
        self.receipts[key] = payload, deepcopy(result)
        return result

    def start_run(self, request):
        validate('RunRequest', request)
        with self.lock:
            def start():
                self.idle()
                self.mode = 'interactive'
                try:
                    snapshot, network = self.snapshot_config(request)
                    run_id = str(uuid4())
                    engine = Engine(run_id, snapshot, network, self.dispatch_factory())
                    engine.step()  # Public first state is t=0 after business processing.
                    engine.record_command('start', request, {'run_id': run_id})
                    self.engines[run_id], self.created[run_id] = engine, utc_now()
                    self.run_id = run_id
                    self.next_tick = time.monotonic() + engine.step_sec / engine.current_speed
                    return engine.snapshot()
                except Exception:
                    self._release()
                    raise
            return self._idempotent('runs', request, start)

    def get_engine(self, identifier):
        if identifier not in self.engines:
            raise DomainError('NOT_FOUND', '运行不在当前进程内存中', {'id': identifier}, 404)
        return self.engines[identifier]

    def state(self, identifier):
        with self.lock:
            return self.get_engine(identifier).snapshot()

    def _save(self, engine):
        if engine.run_id in self.saved:
            return
        try:
            self.store.save_run(engine, self.created[engine.run_id])
            self.saved.add(engine.run_id)
            self.save_error = None
        except Exception as exc:
            self.save_error = DomainError('SAVE_FAILED', '结果保存失败；内存已保留，可重试停止或重置', status=500)
            raise self.save_error from exc

    def control(self, identifier, command):
        validate('Control', command)
        with self.lock:
            action = command['action']
            if action == 'reset' and identifier in self.reset_receipts:
                old_save, receipt = self.reset_receipts[identifier]
                if old_save != command['save']:
                    raise DomainError('IDEMPOTENCY_CONFLICT', '重置重试的保存选择必须一致', status=409)
                return deepcopy(receipt)
            engine = self.get_engine(identifier)
            terminal = engine.status in ('completed', 'stopped', 'aborted')
            if action in ('pause', 'resume', 'speed'):
                if terminal:
                    raise DomainError('INVALID_STATE', '运行已结束', status=409)
                if identifier != self.run_id or self.mode != 'interactive':
                    raise DomainError('BUSY', '不是活动交互实验', status=409)
                if action == 'pause':
                    if engine.status == 'paused':
                        return engine.snapshot()
                    engine.status = 'paused'
                elif action == 'resume':
                    if engine.status == 'running':
                        return engine.snapshot()
                    engine.status = 'running'
                else:
                    engine.current_speed = command['value']
                self.next_tick = time.monotonic() + engine.step_sec / engine.current_speed
                engine.record_command(action, command, {'status': engine.status, 'current_speed': engine.current_speed})
                return engine.snapshot()
            if action == 'stop' and identifier in self.saved:
                return engine.snapshot()
            if engine.status == 'aborted' and (action == 'stop' or command.get('save')):
                raise DomainError('INVALID_STATE', '异常运行不能保存', status=409)
            if engine.status in ('running', 'paused'):
                engine.status = 'stopped'
            should_save = action == 'stop' or command['save']
            # Retry does not append duplicate commands after a failed save.
            if not engine.commands or engine.commands[-1]['action'] != action or engine.commands[-1]['payload'] != command:
                engine.record_command(action, command, {'status': engine.status, 'save_requested': should_save})
            if should_save:
                engine.sample()
                self._save(engine)
            if identifier == self.run_id:
                self._release()
            if action == 'reset':
                receipt = {'mode': 'idle', 'saved': identifier in self.saved, 'run_id': identifier}
                self.closed_states[identifier] = engine.snapshot()
                self.reset_receipts[identifier] = command['save'], deepcopy(receipt)
                del self.engines[identifier]
                return receipt
            return engine.snapshot()

    def dispatch(self, identifier, request):
        if not isinstance(request, dict) or set(request) != {'request_id'}:
            raise DomainError('VALIDATION_ERROR', '只接受request_id', status=422)
        validate('RunRequest', {'request_id': request['request_id']}, fields={'request_id'})
        with self.lock:
            engine = self.get_engine(identifier)
            def execute():
                if self.mode != 'interactive' or self.run_id != identifier:
                    raise DomainError('INVALID_STATE', '只能操作活动交互实验', status=409)
                result = engine.dispatch(request['request_id'])
                engine.sample()
                return result
            return self._idempotent(('dispatch', identifier), request, execute)

    def advance(self):
        """One serialized worker turn; also used by deterministic manager unit tests."""
        with self.lock:
            if self.mode != 'interactive' or self.save_error:
                return
            engine = self.get_engine(self.run_id)
            if engine.status != 'running':
                return
            try:
                engine.step()
            except Exception as exc:
                engine.status = 'aborted'
                engine.record_command('abort', {}, dependency_error(exc).dto())
                self._release()
                return
            if engine.status == 'completed':
                try:
                    self._save(engine)
                except DomainError:
                    return  # Completed in memory, slot remains reserved for retry/discard.
                self._release()

    def _work(self):
        while not self.shutdown.wait(0.02):
            with self.lock:
                if self.mode != 'interactive' or not self.run_id or self.save_error:
                    continue
                engine = self.engines[self.run_id]
                if engine.status == 'running' and time.monotonic() >= self.next_tick:
                    self.advance()
                    self.next_tick = time.monotonic() + engine.step_sec / engine.current_speed

    def start_batch(self, request):
        validate('BatchRequest', request)
        with self.lock:
            def start():
                self.idle()
                params_rules(request['params'])
                dispatch_times_rules(request['dispatch_times_sec'], request['params'])
                # Validate all scenarios before occupying the slot or launching any run.
                for scenario_id in request['scenario_ids']:
                    self.snapshot_config({'scenario_id': scenario_id, 'params': request['params'],
                                          'seed': request['seeds'][0], 'algorithm': request['algorithms'][0]})
                # Historical IDs must remain unique across process restarts.
                try:
                    self.store.batch_history(request['request_id'])
                except DomainError as exc:
                    if exc.status != 404:
                        raise
                else:
                    raise DomainError('DUPLICATE_ID', '批次ID已有历史', status=409)
                items = [{'scenario_id': s, 'algorithm': a, 'seed': seed, 'status': 'pending',
                          'run_id': None, 'error': None} for s in request['scenario_ids']
                         for a in request['algorithms'] for seed in request['seeds']]
                result = {'id': request['request_id'], 'status': 'running', 'total': len(items),
                          'finished': 0, 'items': items, 'aggregates': []}
                self.mode, self.batch_id = 'batch', request['request_id']
                self.batch_results[self.batch_id] = deepcopy(result)
                self.batch_thread = threading.Thread(target=self._run_batch,
                    args=(deepcopy(request), utc_now()), daemon=True, name='batch-owner')
                self.batch_thread.start()
                return result
            return self._idempotent('batches', request, start)

    def _run_batch(self, request, created):
        identifier = request['request_id']
        def progress(result):
            validate('BatchResult', result)
            if result['id'] != identifier:
                raise DomainError('INVALID_BATCH', '进度批次ID不匹配')
            with self.lock:
                self.batch_results[identifier] = deepcopy(result)
        try:
            result = self.runner_factory().run_batch(request, self.run_once, progress)
            validate('BatchResult', result)
            if result['id'] != identifier or result['status'] not in ('completed', 'partial_failed', 'failed'):
                raise DomainError('INVALID_BATCH', '批量执行器必须返回同一批次的终态')
            if self.shutdown.is_set():
                return
            self.store.save_batch(request, result, created)
            progress(result)
        except Exception as exc:
            with self.lock:
                self.batch_errors[identifier] = dependency_error(exc)
        finally:
            with self.lock:
                self._release()

    def run_once(self, spec):
        """RunSpec -> RunOutcome; callable only by the batch worker holding the global slot."""
        validate('RunSpec', spec)
        with self.lock:
            if (self.mode != 'batch' or self.batch_id != spec['batch_id']
                    or threading.current_thread() is not self.batch_thread):
                raise DomainError('BUSY', 'run_once必须由持有批量槽的工作者调用', status=409)
            snapshot, network = self.snapshot_config(spec, batch_request=spec['batch_request'],
                                                      dispatch_times=spec['dispatch_times_sec'])
        engine = Engine(str(uuid4()), snapshot, network, self.dispatch_factory())
        created = utc_now()
        while engine.status == 'running':
            if self.shutdown.is_set():
                raise DomainError('SHUTDOWN', '进程结束，本子运行不保存', status=409)
            with self.lock:
                engine.step()
        with self.lock:
            self.store.save_run(engine, created, spec['batch_id'])
        return {'run_id': engine.run_id, 'summary': engine.snapshot()['metrics']}

    def batch(self, identifier):
        with self.lock:
            if identifier in self.batch_errors:
                raise self.batch_errors[identifier]
            if identifier in self.batch_results:
                return deepcopy(self.batch_results[identifier])
            return self.store.batch_history(identifier)
