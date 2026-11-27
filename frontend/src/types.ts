// DTO fields from contracts/schema.json (1.1.0). The transport envelope is defined in docs/07.
export const CONTRACT_VERSION = '1.1.0'
export interface ErrorBody {
  code: string
  message: string
  details: Record<string, unknown>
}
export interface Station {
  id: string
  name: string
  campus: "main" | "east"
  zone: string
  x: number
  y: number
  capacity: number
  initial_stock: number
  road_edge_id: string
  road_offset: number
  active: boolean
}
export interface RoadNetwork {
  version: string
  width: number
  height: number
  synthetic: boolean
  nodes: Array<{ id: string; x: number; y: number; campus: "main" | "east" | "connector" }>
  edges: Array<{ id: string; from: string; to: string; length_m: number; polyline: Array<[number, number]>; cross_campus: boolean }>
}
export interface Period {
  start_min: number
  end_min: number
  multiplier: number
}
export interface OD {
  origin_id: string
  destination_id: string
  rate_per_min: number
  periods: Array<Period>
}
export interface Scenario {
  id: string
  name: string
  start_minute: number
  duration_min: number
  description: string
  is_preset: boolean
  od_demands: Array<OD>
}
export interface Params {
  duration_min: number
  step_sec: number
  ride_speed_kmh: number
  dispatch_speed_kmh: number
  speed: number
  horizon_min: number
  safety_stock: number
  max_dispatch: number
}
export interface RunRequest {
  request_id: string
  scenario_id: string
  params: Params
  seed: number
  algorithm: "none" | "greedy" | "min_cost_flow"
}
export interface Config {
  id: string
  name: string
  scenario_id: string
  params: Params
  seed: number
  algorithm: "none" | "greedy" | "min_cost_flow"
}
export type Control = { action: "pause" | "resume" | "stop" } | { action: "speed"; value: number } | { action: "reset"; save: boolean }
export interface Task {
  id: string
  source_id: string
  destination_id: string
  quantity: number
  distance_m: number
  route: Array<[number, number]>
  depart_sec: number
  arrival_sec: number
  status: "transporting" | "completed"
}
export interface StationState {
  id: string
  name: string
  campus: "main" | "east"
  zone: string
  x: number
  y: number
  capacity: number
  initial_stock: number
  road_edge_id: string
  road_offset: number
  active: boolean
  stock: number
  reserved_inbound: number
}
export interface RideState {
  id: string
  origin_id: string
  destination_id: string
  depart_sec: number
  arrival_sec: number
  first_attempted: boolean
  reroute_count: number
  extra_distance_m: number
}
export interface WaitingState {
  id: string
  station_id: string
  since_sec: number
  first_attempted: boolean
  reroute_count: number
  extra_distance_m: number
}
export interface Metrics {
  request_count: number
  borrow_success: number
  borrow_failed: number
  first_return_attempts: number
  first_return_success: number
  dispatch_quantity: number
  target_deviation: number
  unfinished_riding: number
  unfinished_waiting: number
  unfinished_transporting: number
  shortage_station_min: number
  full_station_min: number
  extra_ride_distance_m: number
  dispatch_cost_bike_m: number
  algorithm_compute_ms: number
  borrow_success_rate: number | null
  first_return_success_rate: number | null
  utilization: number | null
}
export interface State {
  contract_version: "1.1.0"
  run_id: string
  seq: number
  sim_time_sec: number
  duration_sec: number
  status: "running" | "paused" | "completed" | "stopped" | "aborted"
  algorithm: "none" | "greedy" | "min_cost_flow"
  stations: Array<StationState>
  vehicles: { parked: number; riding: number; waiting: number; transporting: number; total: number }
  rides: Array<RideState>
  waiting: Array<WaitingState>
  metrics: Metrics
  tasks: Array<Task>
  context: RunContext
}
export interface SupplyDemand {
  estimator_version: string
  now_sec: number
  horizon_sec: number
  stations: Array<{ station_id: string; expected_borrow: number; expected_served_borrow: number; expected_return: number; target: number; effective_stock: number; supply: number; demand: number }>
}
export interface BatchRequest {
  request_id: string
  scenario_ids: Array<string>
  algorithms: Array<"none" | "greedy" | "min_cost_flow">
  seeds: Array<number>
  params: Params
  dispatch_times_sec: Array<number>
}
export interface Command {
  command_seq: number
  sim_time_sec: number
  action: string
  payload: Record<string, unknown>
  result: Record<string, unknown>
}
export interface Versions {
  contract: string
  engine: string
  generator: string
  network: string
  python: string
  networkx: string
}
export interface RunSummary {
  id: string
  batch_id: string | null
  status: "completed" | "stopped"
  algorithm: "none" | "greedy" | "min_cost_flow"
  seed: number
  created_at: string
  ended_at: string
  summary: Metrics
}
export interface StationCreate {
  id: string
  name: string
  campus: "main" | "east"
  zone: string
  x: number
  y: number
  capacity: number
  initial_stock: number
  active: boolean
}
export interface RunContext {
  scenario_id: string
  scenario_name: string
  start_minute: number
  seed: number
  params: Params
  current_speed: number
  network_version: string
}

export type Campus = Station['campus']
export type Algorithm = RunRequest['algorithm']
export const algorithms = ['none', 'greedy', 'min_cost_flow'] as const
export type Point = [number, number]
export type List<T> = { items: T[]; total: number }
export type MapInfo = {
  profile: string; image_url: string; width: number; height: number
  network_version: string; synthetic: boolean; snap_tolerance_px: number
}
type StationFields = Omit<StationCreate, 'id' | 'x' | 'y'>
type Nonempty<T> = { [K in keyof T]: Pick<T, K> & Partial<Omit<T, K>> }[keyof T]
export type StationPatch = (Partial<StationFields> & Pick<StationCreate, 'x' | 'y'>)
  | (Nonempty<StationFields> & { x?: never; y?: never })
export type ScenarioPatch = Partial<Pick<Scenario, 'name' | 'start_minute' | 'duration_min' | 'description'>>
export type Runtime = { mode: 'idle'; run_id: null; batch_id: null }
  | { mode: 'interactive'; run_id: string; batch_id: null }
  | { mode: 'batch'; run_id: null; batch_id: string }
export type RunInput = Omit<RunRequest, 'request_id'>
export type BatchInput = Omit<BatchRequest, 'request_id'>
export type ResetReceipt = { mode: 'idle'; saved: boolean; run_id: string }
export type DispatchReceipt = { request_id: string; tasks: Task[]; supply_demand: SupplyDemand }
export type Sample = Pick<State, 'sim_time_sec' | 'metrics' | 'stations'>
export type Statistics = { mean: number | null; stddev: number | null; n: number }
export type Aggregate = { scenario_id: string; algorithm: Algorithm; metrics: Record<keyof Metrics, Statistics> }
export interface BatchItem {
  scenario_id: string
  algorithm: Algorithm
  seed: number
  status: 'pending' | 'running' | 'completed' | 'failed'
  run_id: string | null
  error: ErrorBody | null
}
export interface BatchResult {
  id: string
  status: 'running' | 'completed' | 'partial_failed' | 'failed' | 'interrupted'
  total: number
  finished: number
  items: BatchItem[]
  aggregates: Aggregate[]
}
export interface ConfigSnapshot {
  versions: Versions
  network: RoadNetwork
  stations: Station[]
  scenario: Scenario
  params: Params
  seed: number
  algorithm: Algorithm
  dispatch_times_sec: number[]
  commands: Command[]
  batch_request: BatchRequest | null
}
export type RunDetail = { run: RunSummary; snapshot: ConfigSnapshot; commands: Command[] }
