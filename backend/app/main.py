"""FastAPI application factory. Single-worker deployment; real ports by default."""
from contextlib import asynccontextmanager
from copy import deepcopy
from pathlib import Path
import asyncio
import os
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from fastapi import FastAPI, Body, Request, Response, WebSocket, WebSocketDisconnect
from fastapi.exceptions import RequestValidationError
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException
from sqlalchemy.exc import IntegrityError
from contracts.python_interfaces import NetworkError
from app.engine.errors import DomainError
from app.models import tables as t
from app.network import NetworkService
from app.dispatch import DispatchService
from app.experiments import ExperimentRunner
from app.services.store import Store, listed
from app.services.runtime import RunManager
from app.services.validation import SCHEMA


def body_schema(name):
    return {'requestBody': {'required': True, 'content': {'application/json': {
        'schema': {'$ref': f'#/components/schemas/{name}'}}}}}


def create_app(*, database_url=None, data_profile=None, network_factory=None,
               dispatch_factory=None, runner_factory=None, auto_advance=True):
    profile = data_profile or os.getenv('DATA_PROFILE', 'fixture')
    if profile not in ('fixture', 'campus'):
        raise ValueError('DATA_PROFILE must be fixture or campus')
    directory = ROOT / 'data' / ('fixtures' if profile == 'fixture' else 'campus')
    url = database_url or os.getenv('DATABASE_URL', 'sqlite:///' + (ROOT / 'backend/var/app.db').as_posix())

    @asynccontextmanager
    async def lifespan(application):
        store = Store(url)
        try:
            store.bootstrap(directory, profile)
            manager = RunManager(store, network_factory or NetworkService, dispatch_factory or DispatchService,
                                 runner_factory or ExperimentRunner, auto_advance=auto_advance)
            application.state.store, application.state.manager = store, manager
            try:
                yield
            finally:
                manager.close()
        finally:
            store.close()

    application = FastAPI(title='校园共享单车仿真 · A后端', version='1.1.0', lifespan=lifespan)
    if directory.is_dir():
        application.mount(f'/assets/{directory.name}', StaticFiles(directory=directory), name='map-assets')

    @application.exception_handler(DomainError)
    async def domain_error(request, exc):
        return JSONResponse(status_code=exc.status, content=exc.dto())

    @application.exception_handler(NetworkError)
    async def network_error(request, exc):
        return JSONResponse(status_code=400, content={'code': exc.code, 'message': str(exc), 'details': {}})

    @application.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return JSONResponse(status_code=422, content={'code': 'VALIDATION_ERROR',
            'message': '请求字段校验失败', 'details': {'errors': [
                {'path': list(e['loc']), 'message': e['msg']} for e in exc.errors()]}})

    @application.exception_handler(HTTPException)
    async def http_error(request, exc):
        return JSONResponse(status_code=exc.status_code, content={'code': 'NOT_FOUND' if exc.status_code == 404 else 'HTTP_ERROR',
            'message': str(exc.detail), 'details': {}})

    @application.exception_handler(NotImplementedError)
    async def not_implemented(request, exc):
        return JSONResponse(status_code=501, content={'code': 'NOT_IMPLEMENTED', 'message': '依赖模块尚未实现', 'details': {}})

    @application.exception_handler(IntegrityError)
    async def integrity_error(request, exc):
        return JSONResponse(status_code=409, content={'code': 'CONSTRAINT_CONFLICT', 'message': '数据库约束冲突', 'details': {}})

    @application.exception_handler(Exception)
    async def internal_error(request, exc):
        return JSONResponse(status_code=500, content={'code': 'INTERNAL_ERROR', 'message': '内部执行失败', 'details': {}})

    prefix = '/api/v1'
    def manager(request):
        return request.app.state.manager

    @application.get(prefix + '/health')
    def health(request: Request):
        m = manager(request)
        # Read-only port probe; never return fixture example states as business results.
        with m.lock:
            try:
                config = m.store.all(t.configs)[0]
                snapshot, network = m.snapshot_config(config)
                from app.engine import Engine
                Engine('health-probe', snapshot, network, m.dispatch_factory()).supply_demand()
                stage = 'implemented'
            except (NotImplementedError, IndexError):
                stage = 'scaffold'
        return {'status': 'ok', 'stage': stage}

    @application.get(prefix + '/runtime')
    def runtime(request: Request):
        return manager(request).runtime()

    @application.get(prefix + '/map')
    def map_info(request: Request):
        meta = request.app.state.store.metadata
        return {k: meta[k] for k in ('profile','width','height','network_version','synthetic','snap_tolerance_px')} | {
            'image_url': f'/assets/{directory.name}/' + meta['image_file']}

    @application.get(prefix + '/roads')
    def roads(request: Request):
        return deepcopy(request.app.state.store.network)

    @application.get(prefix + '/stations')
    def stations(request: Request):
        m = manager(request)
        with m.lock:
            return listed(m.store.all(t.stations))

    @application.post(prefix + '/stations', status_code=201, openapi_extra=body_schema('StationCreate'))
    def create_station(request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            return m.station_write(value)

    @application.patch(prefix + '/stations/{identifier}', openapi_extra=body_schema('StationPatch'))
    def patch_station(identifier: str, request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            return m.station_write(value, identifier)

    @application.delete(prefix + '/stations/{identifier}', status_code=204)
    def delete_station(identifier: str, request: Request, clear_related_od: bool = False):
        m = manager(request)
        with m.lock:
            m.idle()
            remaining = [s for s in m.store.all(t.stations) if s['id'] != identifier]
            m.network(remaining)
            m.store.delete_station(identifier, clear_related_od)
        return Response(status_code=204)

    @application.get(prefix + '/scenarios')
    def scenarios(request: Request):
        m = manager(request)
        with m.lock:
            return listed([m.store.scenario(s['id']) for s in m.store.all(t.scenarios)])

    @application.get(prefix + '/scenarios/{identifier}')
    def get_scenario(identifier: str, request: Request):
        m = manager(request)
        with m.lock:
            return m.store.scenario(identifier)

    @application.post(prefix + '/scenarios', status_code=201, openapi_extra=body_schema('Scenario'))
    def create_scenario(request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            m.idle()
            return m.store.create_scenario(value)

    @application.patch(prefix + '/scenarios/{identifier}')
    def patch_scenario(identifier: str, request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            m.idle()
            return m.store.patch_scenario(identifier, value)

    @application.put(prefix + '/scenarios/{identifier}/od')
    def put_od(identifier: str, request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            m.idle()
            return m.store.patch_scenario(identifier, value, od=True)

    @application.delete(prefix + '/scenarios/{identifier}', status_code=204)
    def delete_scenario(identifier: str, request: Request):
        m = manager(request)
        with m.lock:
            m.idle()
            m.store.delete_scenario(identifier)
        return Response(status_code=204)

    @application.get(prefix + '/configs')
    def configs(request: Request):
        m = manager(request)
        with m.lock:
            return listed(m.store.all(t.configs))

    @application.post(prefix + '/configs', status_code=201, openapi_extra=body_schema('Config'))
    def create_config(request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            m.idle()
            return m.store.save_config(value)

    @application.patch(prefix + '/configs/{identifier}')
    def patch_config(identifier: str, request: Request, value: dict = Body(...)):
        m = manager(request)
        with m.lock:
            m.idle()
            return m.store.save_config(value, identifier)

    @application.delete(prefix + '/configs/{identifier}', status_code=204)
    def delete_config(identifier: str, request: Request):
        m = manager(request)
        with m.lock:
            m.idle()
            m.store.delete_config(identifier)
        return Response(status_code=204)

    @application.post(prefix + '/runs', status_code=201, openapi_extra=body_schema('RunRequest'))
    def create_run(request: Request, value: dict = Body(...)):
        return manager(request).start_run(value)

    @application.get(prefix + '/runs/{identifier}/state')
    def state(identifier: str, request: Request):
        return manager(request).state(identifier)

    @application.post(prefix + '/runs/{identifier}/control', openapi_extra=body_schema('Control'))
    def control(identifier: str, request: Request, value: dict = Body(...)):
        return manager(request).control(identifier, value)

    @application.get(prefix + '/runs/{identifier}/supply-demand')
    def supply(identifier: str, request: Request):
        m = manager(request)
        with m.lock:
            return m.get_engine(identifier).supply_demand()

    @application.post(prefix + '/runs/{identifier}/dispatch')
    def dispatch(identifier: str, request: Request, value: dict = Body(...)):
        return manager(request).dispatch(identifier, value)

    @application.get(prefix + '/runs/{identifier}/tasks')
    def tasks(identifier: str, request: Request):
        return listed(manager(request).state(identifier)['tasks'])

    @application.get(prefix + '/runs')
    def history_list(request: Request):
        return listed(request.app.state.store.run_summaries())

    @application.get(prefix + '/runs/{identifier}')
    def history(identifier: str, request: Request):
        return request.app.state.store.history(identifier)

    @application.get(prefix + '/runs/{identifier}/metrics')
    def metrics(identifier: str, request: Request):
        return listed(request.app.state.store.run_metrics(identifier))

    @application.post(prefix + '/batches', status_code=202, openapi_extra=body_schema('BatchRequest'))
    def create_batch(request: Request, value: dict = Body(...)):
        return manager(request).start_batch(value)

    @application.get(prefix + '/batches/{identifier}')
    def batch(identifier: str, request: Request):
        return manager(request).batch(identifier)

    @application.websocket('/ws/runs/{identifier}')
    async def websocket(identifier: str, socket: WebSocket):
        m = socket.app.state.manager
        await socket.accept()
        try:
            try:
                state = await asyncio.to_thread(m.state, identifier)
            except DomainError as exc:
                await socket.send_json({'type': 'error', **exc.dto()})
                await socket.close(code=1008)
                return
            await socket.send_json({'type': 'state', **state})
            seq, last_sent = state['seq'], time.monotonic()
            while True:
                # Receive with timeout detects disconnects even while paused with unchanged seq.
                try:
                    event = await asyncio.wait_for(socket.receive(), timeout=0.05)
                    if event['type'] == 'websocket.disconnect':
                        return
                except asyncio.TimeoutError:
                    pass
                def socket_state():
                    with m.lock:
                        closing = identifier in m.closed_states
                        state = (deepcopy(m.closed_states[identifier]) if closing
                                 else m.get_engine(identifier).snapshot())
                        return closing, state
                closing, state = await asyncio.to_thread(socket_state)
                immediate = state['status'] != 'running'
                if state['seq'] > seq and (immediate or closing or time.monotonic() - last_sent >= 1):
                    await socket.send_json({'type': 'state', **state})
                    seq, last_sent = state['seq'], time.monotonic()
                if closing:
                    await socket.close(code=1000)
                    return
        except (WebSocketDisconnect, RuntimeError):
            return

    def openapi():
        if application.openapi_schema:
            return application.openapi_schema
        schema = get_openapi(title=application.title, version=application.version, routes=application.routes)
        def rewrite(value):
            if isinstance(value, dict):
                return {k: (v.replace('#/$defs/', '#/components/schemas/') if k == '$ref' else rewrite(v))
                        for k, v in value.items()}
            if isinstance(value, list):
                return [rewrite(v) for v in value]
            return value
        schema.setdefault('components', {}).setdefault('schemas', {}).update(rewrite(SCHEMA['$defs']))
        application.openapi_schema = schema
        return schema
    application.openapi = openapi
    return application


app = create_app()
