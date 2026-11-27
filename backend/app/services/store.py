"""Isolated SQLite repository: config transactions, immutable run snapshots, bootstrap marker."""
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
import json
from sqlalchemy import create_engine, event, select, insert, update, delete, or_
from sqlalchemy.pool import StaticPool
from app.models import tables as t
from app.engine.errors import DomainError
from .validation import validate, params_rules, station_rules, scenario_rules


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def listed(items):
    return {'items': items, 'total': len(items)}


def columns(table):
    return [column.label(column.key) for column in table.c]


class Store:
    def __init__(self, url):
        options = {'connect_args': {'check_same_thread': False}}
        if url in ('sqlite://', 'sqlite:///:memory:'):
            options['poolclass'] = StaticPool
        elif url.startswith('sqlite:///'):
            Path(url[len('sqlite:///'):]).resolve().parent.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(url, **options)
        @event.listens_for(self.engine, 'connect')
        def sqlite_setup(connection, _):
            connection.execute('PRAGMA foreign_keys=ON')
            connection.execute('PRAGMA busy_timeout=5000')
        t.metadata.create_all(self.engine)

    def close(self):
        self.engine.dispose()

    def bootstrap(self, directory, profile):
        def read(name):
            return json.loads((directory / name).read_text(encoding='utf-8'))
        # Validate required assets even on restart; campus must never fall back to fixture.
        for name in ['metadata.json', 'road_network.json', 'default_stations.json', 'scenarios.json', 'default_config.json']:
            if not (directory / name).is_file():
                raise RuntimeError(f'DATA_PROFILE={profile}: missing {directory / name}')
        self.metadata, self.network = read('metadata.json'), read('road_network.json')
        validate('RoadNetwork', self.network)
        if self.metadata['profile'] != profile:
            raise RuntimeError('Data profile metadata mismatch')
        image = (directory / self.metadata['image_file']).resolve()
        if not image.is_relative_to(directory.resolve()) or not image.is_file():
            raise RuntimeError('Map image missing or outside profile directory')
        with self.engine.begin() as db:
            marker = db.execute(select(t.bootstrap)).mappings().first()
            if marker:
                if marker['profile'] != profile:
                    raise RuntimeError('Use a separate DATABASE_URL for each DATA_PROFILE')
                return
            stations, scenarios, config = read('default_stations.json'), read('scenarios.json'), read('default_config.json')
            for station in stations:
                validate('Station', station)
                station_rules(station)
                db.execute(insert(t.stations).values(**station))
            station_map = {s['id']: s for s in stations}
            for scenario in scenarios:
                validate('Scenario', scenario)
                scenario_rules(scenario, station_map)
                self._put_scenario(db, scenario)
            validate('Config', config)
            params_rules(config['params'])
            db.execute(insert(t.configs).values(**config))
            db.execute(insert(t.bootstrap).values(id=1, profile=profile))

    def all(self, table):
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(select(*columns(table)).order_by(table.c.id)).mappings()]

    def get(self, table, identifier):
        with self.engine.connect() as db:
            row = db.execute(select(*columns(table)).where(table.c.id == identifier)).mappings().first()
            if row is None:
                raise DomainError('NOT_FOUND', '记录不存在', {'id': identifier}, 404)
            return dict(row)

    def station_map(self):
        return {s['id']: s for s in self.all(t.stations)}

    def scenario(self, identifier):
        scenario = self.get(t.scenarios, identifier)
        with self.engine.connect() as db:
            scenario['od_demands'] = [dict(o) for o in db.execute(select(
                t.od_demands.c.origin_id, t.od_demands.c.destination_id,
                t.od_demands.c.rate_per_min, t.od_demands.c.periods.label('periods')
            ).where(t.od_demands.c.scenario_id == identifier).order_by(t.od_demands.c.id)).mappings()]
        return scenario

    def _put_scenario(self, db, value, replace=False):
        row = {k: v for k, v in value.items() if k != 'od_demands'}
        if replace:
            db.execute(update(t.scenarios).where(t.scenarios.c.id == value['id']).values(**row))
            db.execute(delete(t.od_demands).where(t.od_demands.c.scenario_id == value['id']))
        else:
            db.execute(insert(t.scenarios).values(**row))
        for od in value['od_demands']:
            db.execute(insert(t.od_demands).values(scenario_id=value['id'], **od))

    def ensure_new(self, table, identifier):
        with self.engine.connect() as db:
            if db.execute(select(table.c.id).where(table.c.id == identifier)).first():
                raise DomainError('DUPLICATE_ID', 'ID已存在', {'id': identifier}, 409)

    def save_station(self, station, replace=False):
        # Network construction is performed before this transaction by the manager.
        if not station['active']:
            with self.engine.connect() as db:
                related = db.execute(select(t.od_demands.c.id).where(or_(
                    t.od_demands.c.origin_id == station['id'], t.od_demands.c.destination_id == station['id']))).first()
                if related:
                    raise DomainError('RELATED_OD', '停用前请清理关联OD', status=409)
        with self.engine.begin() as db:
            if replace:
                db.execute(update(t.stations).where(t.stations.c.id == station['id']).values(**station))
            else:
                db.execute(insert(t.stations).values(**station))
        return deepcopy(station)

    def delete_station(self, identifier, clear):
        self.get(t.stations, identifier)
        related = or_(t.od_demands.c.origin_id == identifier, t.od_demands.c.destination_id == identifier)
        with self.engine.begin() as db:
            if db.execute(select(t.od_demands.c.id).where(related)).first() and not clear:
                raise DomainError('RELATED_OD', '确认清理关联OD后再删除站点', status=409)
            if clear:
                db.execute(delete(t.od_demands).where(related))
            db.execute(delete(t.stations).where(t.stations.c.id == identifier))

    def create_scenario(self, value):
        validate('Scenario', value)
        if value['is_preset']:
            raise DomainError('INVALID_SCENARIO', '用户创建场景必须is_preset=false')
        self.ensure_new(t.scenarios, value['id'])
        scenario_rules(value, self.station_map())
        with self.engine.begin() as db:
            self._put_scenario(db, value)
        return value

    def patch_scenario(self, identifier, patch, *, od=False):
        value = self.scenario(identifier)
        if od:
            if not isinstance(patch, dict) or set(patch) != {'od_demands'}:
                raise DomainError('VALIDATION_ERROR', '只接受od_demands', status=422)
        else:
            validate('Scenario', patch, fields={'name','start_minute','duration_min','description'}, partial=True)
        value.update(patch)
        validate('Scenario', value)
        scenario_rules(value, self.station_map())
        with self.engine.begin() as db:
            self._put_scenario(db, value, replace=True)
        return value

    def delete_scenario(self, identifier):
        value = self.scenario(identifier)
        if value['is_preset']:
            raise DomainError('PRESET_SCENARIO', '不能删除预设场景', status=409)
        with self.engine.begin() as db:
            if db.execute(select(t.configs.c.id).where(t.configs.c.scenario_id == identifier)).first():
                raise DomainError('IN_USE', '场景已被配置引用', status=409)
            db.execute(delete(t.od_demands).where(t.od_demands.c.scenario_id == identifier))
            db.execute(delete(t.scenarios).where(t.scenarios.c.id == identifier))

    def save_config(self, value, identifier=None):
        if identifier:
            validate('Config', value, fields={'name','scenario_id','params','seed','algorithm'}, partial=True)
            value = self.get(t.configs, identifier) | value
        else:
            validate('Config', value)
            self.ensure_new(t.configs, value['id'])
        validate('Config', value)
        params_rules(value['params'])
        scenario_rules(self.scenario(value['scenario_id']), self.station_map(), value['params']['duration_min'])
        with self.engine.begin() as db:
            if identifier:
                db.execute(update(t.configs).where(t.configs.c.id == identifier).values(**value))
            else:
                db.execute(insert(t.configs).values(**value))
        return value

    def delete_config(self, identifier):
        self.get(t.configs, identifier)
        with self.engine.begin() as db:
            db.execute(delete(t.configs).where(t.configs.c.id == identifier))

    def save_run(self, engine, created_at, batch_id=None):
        state = engine.snapshot()
        if state['status'] not in ('completed', 'stopped'):
            raise DomainError('INVALID_STATE', '只能保存已完成或已停止的运行', status=409)
        config = deepcopy(engine.config) | {'commands': deepcopy(engine.commands)}
        row = {'id': engine.run_id, 'batch_id': batch_id, 'snapshot': config,
               'algorithm': config['algorithm'], 'seed': config['seed'], 'status': state['status'],
               'created_at': created_at, 'ended_at': utc_now(), 'summary': state['metrics'],
               'commands': deepcopy(engine.commands)}
        with self.engine.begin() as db:
            if db.execute(select(t.runs.c.id).where(t.runs.c.id == engine.run_id)).first():
                return
            db.execute(insert(t.runs).values(**row))
            self._save_children(db, engine)

    def _save_children(self, db, engine):
        # Kept as a transaction seam for failure-injection tests.
        for sample in engine.samples:
            db.execute(insert(t.metrics).values(run_id=engine.run_id, **sample))
        for task in engine.tasks.values():
            db.execute(insert(t.tasks).values(run_id=engine.run_id, **task))

    def run_summaries(self):
        return [{k: v for k, v in row.items() if k not in ('snapshot', 'commands')} for row in self.all(t.runs)]

    def history(self, identifier):
        row = self.get(t.runs, identifier)
        return {'run': {k: v for k, v in row.items() if k not in ('snapshot','commands')},
                'snapshot': row['snapshot'], 'commands': row['commands']}

    def run_metrics(self, identifier):
        self.get(t.runs, identifier)
        with self.engine.connect() as db:
            return [dict(row) for row in db.execute(select(t.metrics.c.sim_time_sec, t.metrics.c.metrics.label('metrics'),
                t.metrics.c.stations.label('stations')).where(t.metrics.c.run_id == identifier).order_by(t.metrics.c.sim_time_sec)).mappings()]

    def save_batch(self, request, result, created_at):
        with self.engine.begin() as db:
            db.execute(insert(t.batches).values(id=result['id'], request=request, status=result['status'],
                                               items=result['items'], aggregates=result['aggregates'],
                                               created_at=created_at, ended_at=utc_now()))

    def batch_history(self, identifier):
        with self.engine.connect() as db:
            row = db.execute(select(*columns(t.batches)).where(t.batches.c.id == identifier)).mappings().first()
            if row:
                request = row['request']
                return {'id': identifier, 'status': row['status'], 'items': row['items'],
                        'aggregates': row['aggregates'],
                        'total': len(request['scenario_ids']) * len(request['algorithms']) * len(request['seeds']),
                        'finished': sum(i['status'] in ('completed', 'failed') for i in row['items'])}
            rows = db.execute(select(*columns(t.runs)).where(t.runs.c.batch_id == identifier)).mappings().all()
        if not rows:
            raise DomainError('NOT_FOUND', '批次不存在', status=404)
        # No fabricated failed/pending items or aggregate statistics after process interruption.
        request = rows[0]['snapshot']['batch_request']
        items = [{'scenario_id': r['snapshot']['scenario']['id'], 'algorithm': r['algorithm'],
                  'seed': r['seed'], 'status': 'completed', 'run_id': r['id'], 'error': None} for r in rows]
        return {'id': identifier, 'status': 'interrupted',
                'total': len(request['scenario_ids']) * len(request['algorithms']) * len(request['seeds']),
                'finished': len(items), 'items': items, 'aggregates': []}
