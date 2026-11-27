"""SQLAlchemy schema. History station IDs deliberately have no live-station FK."""
from sqlalchemy import (MetaData, Table, Column, String, Integer, Float, Boolean, JSON,
                        ForeignKey, CheckConstraint, UniqueConstraint)

metadata = MetaData()
bootstrap = Table('bootstrap_state', metadata, Column('id', Integer, primary_key=True),
                  Column('profile', String, nullable=False))
stations = Table('stations', metadata,
    Column('id', String, primary_key=True), Column('name', String, nullable=False),
    Column('campus', String, nullable=False), Column('zone', String, nullable=False),
    Column('x', Float, nullable=False), Column('y', Float, nullable=False),
    Column('capacity', Integer, nullable=False), Column('initial_stock', Integer, nullable=False),
    Column('road_edge_id', String, nullable=False), Column('road_offset', Float, nullable=False),
    Column('active', Boolean, nullable=False), CheckConstraint('capacity > 0'),
    CheckConstraint('initial_stock >= 0 AND initial_stock <= capacity'))
scenarios = Table('scenarios', metadata,
    Column('id', String, primary_key=True), Column('name', String, nullable=False),
    Column('start_minute', Integer, nullable=False), Column('duration_min', Integer, nullable=False),
    Column('description', String, nullable=False), Column('is_preset', Boolean, nullable=False))
od_demands = Table('od_demands', metadata,
    Column('id', Integer, primary_key=True), Column('scenario_id', String, ForeignKey('scenarios.id'), nullable=False),
    Column('origin_id', String, ForeignKey('stations.id'), nullable=False),
    Column('destination_id', String, ForeignKey('stations.id'), nullable=False),
    Column('rate_per_min', Float, nullable=False), Column('periods_json', JSON, key='periods', nullable=False),
    UniqueConstraint('scenario_id', 'origin_id', 'destination_id'),
    CheckConstraint('origin_id != destination_id AND rate_per_min >= 0'))
configs = Table('simulation_configs', metadata,
    Column('id', String, primary_key=True), Column('name', String, nullable=False),
    Column('scenario_id', String, ForeignKey('scenarios.id'), nullable=False),
    Column('params_json', JSON, key='params', nullable=False), Column('seed', Integer, nullable=False),
    Column('algorithm', String, nullable=False))
runs = Table('simulation_runs', metadata,
    Column('id', String, primary_key=True), Column('batch_id', String),
    Column('config_snapshot_json', JSON, key='snapshot', nullable=False), Column('algorithm', String, nullable=False),
    Column('seed', Integer, nullable=False), Column('status', String, nullable=False),
    Column('created_at', String, nullable=False), Column('ended_at', String, nullable=False),
    Column('summary_json', JSON, key='summary', nullable=False), Column('commands_json', JSON, key='commands', nullable=False),
    CheckConstraint("status IN ('completed','stopped')"))
metrics = Table('simulation_metrics', metadata,
    Column('id', Integer, primary_key=True), Column('run_id', String, ForeignKey('simulation_runs.id'), nullable=False),
    Column('sim_time_sec', Integer, nullable=False), Column('metrics_json', JSON, key='metrics', nullable=False),
    Column('station_states_json', JSON, key='stations', nullable=False), UniqueConstraint('run_id', 'sim_time_sec'))
tasks = Table('dispatch_tasks', metadata,
    Column('id', String, primary_key=True), Column('run_id', String, ForeignKey('simulation_runs.id'), primary_key=True),
    Column('source_id', String, nullable=False), Column('destination_id', String, nullable=False),
    Column('quantity', Integer, nullable=False), Column('distance_m', Float, nullable=False),
    Column('route_json', JSON, key='route', nullable=False), Column('depart_sec', Integer, nullable=False),
    Column('arrival_sec', Integer, nullable=False), Column('status', String, nullable=False))
batches = Table('batches', metadata,
    Column('id', String, primary_key=True), Column('request_json', JSON, key='request', nullable=False),
    Column('created_at', String, nullable=False), Column('ended_at', String, nullable=False),
    Column('status', String, nullable=False), Column('items_json', JSON, key='items', nullable=False),
    Column('aggregates_json', JSON, key='aggregates', nullable=False))
