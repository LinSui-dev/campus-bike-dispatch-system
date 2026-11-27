// A tab-local API fixture for C's manual and automated checks.
import { ApiError } from '../transport'
import type { Api, StreamMessage } from '../transport'
import { CONTRACT_VERSION } from '../types'
import type * as D from '../types'
import { batchError, metricKeys, runError, scenarioError, stationError } from '../domain'
import * as fixture from './fixture'

const key = 'bike-simulation-fixture-v1'
const copy = <T>(data: T): T => structuredClone(data)
const list = <T>(items: T[]): D.List<T> => ({ items, total: items.length })
interface SavedRun {
  detail: D.RunDetail
  samples: D.Sample[]
  tasks: D.Task[]
}
interface Model {
  stations: D.Station[]
  scenarios: D.Scenario[]
  configs: D.Config[]
  current: D.State | null
  last: D.State | null
  samples: D.Sample[]
  history: SavedRun[]
  batches: Record<string, D.BatchResult>
  batchRequest: D.BatchRequest | null
  started: string
  commands: D.Command[]
  receipts: Record<string, { signature: string; result: unknown }>
}
const raw = sessionStorage.getItem(key)
const db: Model = raw ? JSON.parse(raw) : {
  stations: copy(fixture.stations), scenarios: copy(fixture.scenarios), configs: [copy(fixture.config)],
  current: null, last: null, samples: [], history: [], batches: {}, batchRequest: null,
  started: '', commands: [], receipts: {},
}
const save = () => sessionStorage.setItem(key, JSON.stringify(db))
const fault = { disconnected: false, timeout: false, failBatch: false, vanishOnState: false, failSave: false }
interface Listener { id: string; receive: (packet: StreamMessage) => void; disconnect: () => void }
const listeners = new Set<Listener>()
let stale: D.State | null = null

function emit(state: D.State) {
  for (const listener of listeners) {
    if (listener.id === state.run_id) listener.receive({ ...copy(state), type: 'state' })
  }
}
function closeListeners() {
  for (const listener of listeners) listener.disconnect()
  listeners.clear()
}

export const mockActions = {
  toggleConnection() {
    fault.disconnected = !fault.disconnected
    if (fault.disconnected) closeListeners()
    return fault.disconnected
  },
  stale() {
    if (stale) emit({ ...stale, context: { ...stale.context, current_speed: 599 } })
  },
  timeout() { fault.timeout = true },
  failBatch() { fault.failBatch = true },
  vanish() {
    fault.vanishOnState = true
    closeListeners()
  },
  failSave() { fault.failSave = true },
}

function fail(status: number, code: string, text: string): never {
  throw new ApiError(status, code, text)
}
function validate(text: string) {
  if (text) fail(422, 'VALIDATION_ERROR', text)
}
function requireIdle() {
  if (db.current || db.batchRequest) fail(409, 'BUSY', '已有实验占用运行槽。')
}
function find<T extends { id: string }>(items: T[], id: string) {
  return items.find(item => item.id === id) ?? fail(404, 'NOT_FOUND', '记录已不存在。')
}
function unique<T extends { id: string }>(items: T[], id: string) {
  if (items.some(item => item.id === id)) fail(409, 'DUPLICATE_ID', 'ID 已存在。')
}
function replace<T extends { id: string }>(items: T[], value: T) {
  return items.map(item => item.id === value.id ? value : item)
}
function remove<T extends { id: string }>(items: T[], id: string) {
  find(items, id)
  return items.filter(item => item.id !== id)
}
function runtime(): D.Runtime {
  if (db.current) return { mode: 'interactive', run_id: db.current.run_id, batch_id: null }
  if (db.batchRequest) return { mode: 'batch', run_id: null, batch_id: db.batchRequest.request_id }
  return { mode: 'idle', run_id: null, batch_id: null }
}
function stateFor(id: string) {
  if (db.current?.run_id === id) return db.current
  if (db.last?.run_id === id) return db.last
  return fail(404, 'NOT_FOUND', '当前运行已结束或被重置。')
}

function project(candidate: D.StationCreate): D.Station {
  validate(stationError(candidate, fixture.map))
  // The fixture consists of three collinear road segments.
  const closest = fixture.roads.edges.map(edge => {
    const [x1, y] = edge.polyline[0]
    const [x2] = edge.polyline[1]
    const x = Math.max(x1, Math.min(x2, candidate.x))
    return { x, y, edge, offset: (x - x1) / (x2 - x1), distance: Math.hypot(x - candidate.x, y - candidate.y) }
  }).sort((a, b) => a.distance - b.distance)[0]
  if (closest.distance > fixture.map.snap_tolerance_px) fail(400, 'INVALID_STATION', '站点离可骑行道路过远。')
  return { ...candidate, x: closest.x, y: closest.y, road_edge_id: closest.edge.id, road_offset: closest.offset }
}

function stations(method: string, id: string, query: URLSearchParams, body: unknown) {
  if (method === 'GET') return list(db.stations)
  requireIdle()
  if (method === 'POST') {
    const candidate = body as D.StationCreate
    unique(db.stations, candidate.id)
    const station = project(candidate)
    db.stations.push(station)
    return station
  }
  const { road_edge_id: _edge, road_offset: _offset, ...old } = find(db.stations, id)
  if (method === 'PATCH') {
    const patch = body as D.StationPatch
    if (('x' in patch) !== ('y' in patch)) fail(422, 'VALIDATION_ERROR', 'x 和 y 须同时提供。')
    const normalized = project({ ...old, ...patch })
    db.stations = replace(db.stations, normalized)
    return normalized
  }
  const related = (od: D.OD) => od.origin_id === id || od.destination_id === id
  if (db.scenarios.some(scenario => scenario.od_demands.some(related)) && query.get('clear_related_od') !== 'true')
    fail(409, 'RELATED_OD', '该站点关联了 OD 需求。')
  db.stations = remove(db.stations, id)
  db.scenarios = db.scenarios.map(scenario => ({ ...scenario, od_demands: scenario.od_demands.filter(od => !related(od)) }))
}

function scenarios(method: string, id: string, body: unknown) {
  if (method === 'GET') return id ? find(db.scenarios, id) : list(db.scenarios)
  requireIdle()
  if (method === 'POST') {
    const scenario = body as D.Scenario
    unique(db.scenarios, scenario.id)
    validate(scenarioError(scenario, db.stations))
    db.scenarios.push(scenario)
    return scenario
  }
  const previous = find(db.scenarios, id)
  if (method === 'DELETE') {
    if (previous.is_preset) fail(409, 'PRESET_SCENARIO', '预设场景不能删除。')
    if (db.configs.some(item => item.scenario_id === id)) fail(409, 'IN_USE', '此场景仍被已保存配置引用。')
    db.scenarios = remove(db.scenarios, id)
    return
  }
  const scenario = { ...previous, ...(body as D.ScenarioPatch | { od_demands: D.OD[] }) }
  validate(scenarioError(scenario, db.stations))
  db.scenarios = replace(db.scenarios, scenario)
  return scenario
}

function configs(method: string, id: string, body: unknown) {
  if (method === 'GET') return list(db.configs)
  requireIdle()
  if (method === 'DELETE') {
    db.configs = remove(db.configs, id)
    return
  }
  const config = method === 'POST' ? body as D.Config : { ...find(db.configs, id), ...body as Partial<D.Config> }
  validate(config.name.trim() && config.name.length <= 128 ? '' : '请输入配置名称。')
  validate(runError(config, db.scenarios, db.stations))
  if (method === 'POST') {
    unique(db.configs, config.id)
    db.configs.push(config)
  } else db.configs = replace(db.configs, config)
  return config
}

function receipt<T>(operation: string, id: string, body: unknown, execute: () => T) {
  const slot = operation + '/' + id
  const signature = JSON.stringify(body)
  const existing = db.receipts[slot]
  if (existing) {
    if (existing.signature !== signature) fail(409, 'IDEMPOTENCY_CONFLICT', '重复 ID 的请求内容不同。')
    return existing.result as T
  }
  const result = execute()
  db.receipts[slot] = { signature, result: copy(result) }
  return result
}

function supply(state: D.State): D.SupplyDemand {
  const horizon = Math.min(state.duration_sec - state.sim_time_sec, state.context.params.horizon_min * 60)
  return {
    estimator_version: 'fixture-only', now_sec: state.sim_time_sec, horizon_sec: horizon,
    stations: state.stations.filter(station => station.active).map((station, index) => {
      const effective_stock = station.stock + station.reserved_inbound
      const target = Math.min(station.capacity, Math.max(0, station.initial_stock + (index % 2 === 0 ? -4 : 4)))
      const expected_borrow = horizon ? index + 1 : 0
      return {
        station_id: station.id, target, effective_stock, expected_borrow,
        expected_served_borrow: Math.min(station.stock, expected_borrow), expected_return: 0,
        supply: Math.min(station.stock, Math.max(0, effective_stock - target)), demand: Math.max(0, target - effective_stock),
      }
    }),
  }
}

function refreshCounts(state: D.State) {
  const parked = state.stations.reduce((sum, station) => sum + station.stock, 0)
  const transporting = state.tasks.filter(task => task.status === 'transporting').reduce((sum, task) => sum + task.quantity, 0)
  const riding = state.rides.length
  const waiting = state.waiting.length
  state.vehicles = { parked, riding, waiting, transporting, total: parked + riding + waiting + transporting }
  state.metrics.unfinished_transporting = transporting
  state.metrics.unfinished_riding = riding
  state.metrics.unfinished_waiting = waiting
  state.metrics.target_deviation = supply(state).stations.reduce((sum, station) => sum + Math.abs(station.effective_stock - station.target), 0)
}

function sample(state: D.State): D.Sample {
  return copy({ sim_time_sec: state.sim_time_sec, metrics: state.metrics, stations: state.stations })
}
function publish(state: D.State) {
  state.seq++
  refreshCounts(state)
  const point = sample(state)
  if (db.samples.at(-1)?.sim_time_sec === point.sim_time_sec) db.samples.pop()
  db.samples.push(point)
  emit(state)
  save()
}
function newState(input: D.RunInput, id: string): D.State {
  const scenario = find(db.scenarios, input.scenario_id)
  const result: D.State = {
    run_id: id, contract_version: CONTRACT_VERSION, seq: 0, sim_time_sec: 0,
    duration_sec: input.params.duration_min * 60, status: 'running', algorithm: input.algorithm,
    context: {
      scenario_id: scenario.id, scenario_name: scenario.name, start_minute: scenario.start_minute, seed: input.seed,
      params: copy(input.params), current_speed: input.params.speed, network_version: fixture.roads.version,
    },
    vehicles: { parked: 0, riding: 0, waiting: 0, transporting: 0, total: 0 },
    stations: db.stations.filter(station => station.active)
      .map(station => ({ ...station, stock: station.initial_stock, reserved_inbound: 0 })),
    metrics: copy(fixture.emptyMetrics), tasks: [], rides: [], waiting: [],
  }
  refreshCounts(result)
  return result
}

function storeRun(state: D.State, samples: D.Sample[], batchRequest: D.BatchRequest | null, status: D.RunSummary['status']) {
  if (db.history.some(row => row.detail.run.id === state.run_id)) return
  const commands = batchRequest ? [] : db.commands
  const snapshot: D.ConfigSnapshot = {
    versions: { contract: CONTRACT_VERSION, engine: 'fixture-only', generator: 'fixture-only', network: fixture.roads.version, python: 'fixture-only', networkx: 'fixture-only' },
    network: fixture.roads, stations: db.stations.filter(station => station.active),
    scenario: find(db.scenarios, state.context.scenario_id),
    params: state.context.params, seed: state.context.seed, algorithm: state.algorithm,
    dispatch_times_sec: batchRequest?.dispatch_times_sec ?? [], batch_request: batchRequest, commands,
  }
  const ended_at = new Date().toISOString()
  db.history.unshift(copy({
    detail: {
      run: {
        id: state.run_id, batch_id: batchRequest?.request_id ?? null, status, algorithm: state.algorithm,
        seed: state.context.seed, summary: state.metrics, created_at: batchRequest ? ended_at : db.started, ended_at,
      },
      snapshot, commands,
    },
    samples, tasks: state.tasks,
  }))
}

function control(id: string, body: D.Control) {
  if (body.action === 'reset') {
    return receipt('reset', id, body, () => {
      const state = stateFor(id)
      if (body.save) {
        checkSave()
        storeRun(state, db.samples, null, state.status === 'completed' ? 'completed' : 'stopped')
      }
      if (state.status !== 'completed') state.status = 'stopped'
      publish(state)
      db.current = db.last = null
      closeListeners()
      return { mode: 'idle', saved: body.save, run_id: id }
    })
  }
  const state = stateFor(id)
  if (state !== db.current) {
    if (body.action === 'stop' && state.status === 'stopped') return state
    fail(409, 'RUN_ENDED', '运行已结束。')
  }
  stale = copy(state)
  if (body.action === 'stop') {
    state.status = 'stopped'
    if (fault.failSave) publish(state)
    checkSave()
  }
  if (body.action === 'pause') state.status = 'paused'
  if (body.action === 'resume') state.status = 'running'
  if (body.action === 'speed') state.context.current_speed = body.value
  db.commands.push({ command_seq: db.commands.length + 1, sim_time_sec: state.sim_time_sec, action: body.action, payload: { ...body }, result: {} })
  publish(state)
  if (body.action === 'stop') end(state, 'stopped')
  return state
}

function end(state: D.State, status: D.RunSummary['status']) {
  storeRun(state, db.samples, null, status)
  db.current = null
  db.last = state
}
function checkSave() {
  if (!fault.failSave) return
  fault.failSave = false
  fail(500, 'MOCK_SAVE_FAILED', '虚拟保存失败。可重试或舍弃。')
}

function dispatch(state: D.State, request_id: string): D.DispatchReceipt {
  return receipt('dispatch/' + state.run_id, request_id, { request_id }, () => {
    if (state !== db.current) fail(409, 'RUN_ENDED', '运行已结束。')
    const supply_demand = supply(state)
    const tasks: D.Task[] = []
    if (state.algorithm !== 'none') {
      const source = supply_demand.stations.find(item => item.supply > 0)
      // Prefer a cross-campus pair so the path covers more than one fixture edge.
      const destination = [...supply_demand.stations].reverse().find(item => item.demand > 0)
      if (source && destination && source.station_id !== destination.station_id) {
        const from = find(state.stations, source.station_id)
        const to = find(state.stations, destination.station_id)
        const quantity = Math.min(source.supply, destination.demand, state.context.params.max_dispatch)
        if (quantity > 0) {
          const route: D.Point[] = [[from.x, from.y]]
          const between = fixture.roads.nodes.filter(node => node.x > Math.min(from.x, to.x) && node.x < Math.max(from.x, to.x))
          if (from.x > to.x) between.reverse()
          route.push(...between.map((node): D.Point => [node.x, node.y]), [to.x, to.y])
          const distance_m = Math.abs(to.x - from.x)
          const step = state.context.params.step_sec
          const seconds = Math.max(step, Math.ceil(distance_m / (state.context.params.dispatch_speed_kmh / 3.6) / step) * step)
          const task: D.Task = {
            id: 'mock-task-' + (state.tasks.length + 1), source_id: from.id, destination_id: to.id,
            quantity, distance_m, route, depart_sec: state.sim_time_sec, arrival_sec: state.sim_time_sec + seconds, status: 'transporting',
          }
          from.stock -= quantity
          to.reserved_inbound += quantity
          state.metrics.dispatch_quantity += quantity
          state.metrics.dispatch_cost_bike_m += quantity * distance_m
          state.tasks.push(task)
          tasks.push(task)
        }
      }
    }
    publish(state)
    return { request_id, tasks, supply_demand }
  })
}

function fixtureStep(state: D.State) {
  const step = state.context.params.step_sec
  state.sim_time_sec = Math.min(state.duration_sec, state.sim_time_sec + step)
  for (const task of state.tasks) {
    if (task.status === 'completed' || task.arrival_sec > state.sim_time_sec) continue
    const destination = find(state.stations, task.destination_id)
    destination.stock += task.quantity
    destination.reserved_inbound -= task.quantity
    task.status = 'completed'
  }
  // Illustrative counters exercise chart states while leaving fixture bike stocks to transport.
  const metrics = state.metrics
  if (state.sim_time_sec < state.duration_sec && state.sim_time_sec / step % 2 === 0) {
    metrics.request_count++
    if (metrics.request_count % 4 === 0) metrics.borrow_failed++
    else {
      metrics.borrow_success++
      metrics.first_return_attempts++
      metrics.first_return_success++
    }
    metrics.borrow_success_rate = metrics.borrow_success / metrics.request_count
    metrics.first_return_success_rate = metrics.first_return_attempts ? 1 : null
  }
  if (state.sim_time_sec === state.duration_sec) state.status = 'completed'
  publish(state)
  if (state.status === 'completed') end(state, 'completed')
}

function aggregate(batch: D.BatchResult) {
  const groups = new Map<string, D.Aggregate>()
  for (const item of batch.items) {
    const key = JSON.stringify([item.scenario_id, item.algorithm])
    if (groups.has(key)) continue
    const eligible = batch.items.filter(row => row.scenario_id === item.scenario_id && row.algorithm === item.algorithm && row.run_id)
    const metrics = Object.fromEntries(metricKeys.map(metric => {
      const values = eligible.map(row => db.history.find(run => run.detail.run.id === row.run_id)?.detail.run.summary[metric])
        .filter((value): value is number => value != null)
      const n = values.length
      const mean = n ? values.reduce((sum, value) => sum + value, 0) / n : null
      const stddev = n > 1 && mean !== null
        ? Math.sqrt(values.reduce((sum, value) => sum + (value - mean) ** 2, 0) / (n - 1)) : null
      return [metric, { mean, stddev, n }]
    })) as D.Aggregate['metrics']
    groups.set(key, { scenario_id: item.scenario_id, algorithm: item.algorithm, metrics })
  }
  return [...groups.values()]
}

function advanceBatch(request: D.BatchRequest) {
  const batch = db.batches[request.request_id]
  const item = batch.items[batch.finished]
  if (item.status === 'pending') {
    item.status = 'running'
    return
  }
  if (fault.failBatch) {
    fault.failBatch = false
    item.status = 'failed'
    item.error = { code: 'MOCK_ITEM_FAILED', message: '注入的虚拟子项失败。', details: {} }
  } else {
    const state = newState({ ...item, params: request.params }, crypto.randomUUID())
    const first = sample(state)
    state.sim_time_sec = state.duration_sec
    state.status = 'completed'
    item.status = 'completed'
    item.run_id = state.run_id
    storeRun(state, [first, sample(state)], request, 'completed')
  }
  batch.finished++
  if (batch.finished === batch.total) {
    const failed = batch.items.filter(row => row.status === 'failed').length
    batch.status = failed === 0 ? 'completed' : failed === batch.total ? 'failed' : 'partial_failed'
    batch.aggregates = aggregate(batch)
    db.batchRequest = null
  }
}

let elapsed = 0
window.setInterval(() => {
  if (db.current?.status === 'running') {
    elapsed += db.current.context.current_speed / 2
    const step = db.current.context.params.step_sec
    while (elapsed >= step && db.current?.status === 'running') {
      stale = copy(db.current)
      fixtureStep(db.current)
      elapsed -= step
    }
    save()
  }
  if (db.batchRequest) {
    advanceBatch(db.batchRequest)
    save()
  }
}, 500)

function runs(method: string, id: string, part: string, body: unknown) {
  if (method === 'POST' && !id) {
    const request = body as D.RunRequest
    return receipt('start', request.request_id, request, () => {
      requireIdle()
      validate(runError(request, db.scenarios, db.stations))
      db.current = newState(request, crypto.randomUUID())
      db.last = null
      db.started = new Date().toISOString()
      db.commands = []
      elapsed = 0
      db.samples = [sample(db.current)]
      return db.current
    })
  }
  if (method === 'POST' && part === 'control') return control(id, body as D.Control)
  if (method === 'POST' && part === 'dispatch') return dispatch(stateFor(id), (body as { request_id: string }).request_id)
  if (part === 'state') {
    if (fault.vanishOnState) {
      fault.vanishOnState = false
      db.current = db.last = null
      closeListeners()
      save()
    }
    return stateFor(id)
  }
  if (part === 'supply-demand') return supply(stateFor(id))
  if (!id) return list(db.history.map(row => row.detail.run))
  const archived = db.history.find(row => row.detail.run.id === id)
  if (part === 'tasks') return list(archived?.tasks ?? stateFor(id).tasks)
  if (!archived) fail(404, 'NOT_FOUND', '历史记录未找到。')
  return part === 'metrics' ? list(archived.samples) : archived.detail
}

function batches(method: string, id: string, body: unknown) {
  if (method === 'GET') return db.batches[id] ?? fail(404, 'NOT_FOUND', '批次未找到。')
  const request = body as D.BatchRequest
  return receipt('batch', request.request_id, request, () => {
    requireIdle()
    validate(batchError(request, db.scenarios, db.stations))
    const items = request.scenario_ids.flatMap(scenario_id => request.algorithms.flatMap(algorithm => request.seeds.map((seed): D.BatchItem => ({
      scenario_id, algorithm, seed, status: 'pending', run_id: null, error: null,
    }))))
    db.batchRequest = request
    const batch: D.BatchResult = { id: request.request_id, status: 'running', total: items.length, finished: 0, items, aggregates: [] }
    db.batches[batch.id] = batch
    return batch
  })
}

function logRequest(method: string, path: string, body: unknown) {
  const log = JSON.parse(sessionStorage.getItem(key + '-requests') ?? '[]') as unknown[]
  log.push({ method, path, body })
  sessionStorage.setItem(key + '-requests', JSON.stringify(log.slice(-400)))
}

function handle(method: string, url: URL, body: unknown) {
  const [resource, id = '', part = ''] = url.pathname.split('/').slice(1).map(decodeURIComponent)
  switch (resource) {
    case 'runtime': return runtime()
    case 'map': return fixture.map
    case 'roads': return fixture.roads
    case 'stations': return stations(method, id, url.searchParams, body)
    case 'scenarios': return scenarios(method, id, body)
    case 'configs': return configs(method, id, body)
    case 'runs': return runs(method, id, part, body)
    case 'batches': return batches(method, id, body)
    default: return fail(501, 'NOT_IMPLEMENTED', '虚拟接口未实现。')
  }
}

export const mock: Api = {
  async request<T>(method: string, path: string, body?: unknown) {
    await new Promise(resolve => setTimeout(resolve, method === 'GET' ? 30 : 230))
    const payload = body === undefined ? undefined : JSON.parse(JSON.stringify(body))
    logRequest(method, path, payload)
    const timeout = fault.timeout && method === 'POST' && Boolean(payload?.request_id)
    const timeoutMessage = '虚拟响应超时，可使用同一请求重试。'
    if (timeout) fault.timeout = false
    // Exercise failure before creation and a lost response after dispatch took effect.
    if (timeout && !path.endsWith('/dispatch')) fail(0, 'TIMEOUT', timeoutMessage)
    const result = handle(method, new URL(path, location.origin), payload)
    if (method !== 'GET') save()
    if (timeout) fail(0, 'TIMEOUT', timeoutMessage)
    return copy(result) as T
  },
  stream(id, receive, disconnect) {
    if (fault.disconnected) return { ready: Promise.reject(new Error('虚拟连接断开')), close: () => {} }
    const listener: Listener = { id, receive, disconnect }
    listeners.add(listener)
    const ready = new Promise<void>(resolve => setTimeout(() => {
      if (db.current?.run_id === id && listeners.has(listener)) receive({ ...copy(db.current), type: 'state' })
      resolve()
    }, 20))
    return { ready, close: () => { listeners.delete(listener) } }
  },
}
