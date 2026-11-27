import type { Algorithm, BatchInput, Campus, Metrics, Params, Point, RunInput, Scenario, Station, StationCreate, StationState, Task } from './types'
export const campusNames: Record<Campus, string> = { main: '主校区', east: '东校区' }
export const algorithmNames: Record<Algorithm, string> = { none: '无调度', greedy: '贪心', min_cost_flow: '最小费用流' }
export const statusNames = {
  idle: '空闲', running: '运行中', paused: '已暂停', stopped: '已停止', completed: '已完成', aborted: '运行中断',
  pending: '等待中', failed: '失败', partial_failed: '部分失败', interrupted: '批次中断', batch: '批量运行中',
}
export const defaultParams: Params = {
  duration_min: 120, step_sec: 60, ride_speed_kmh: 12, dispatch_speed_kmh: 10,
  speed: 60, horizon_min: 30, safety_stock: 5, max_dispatch: 50,
}
const field = (label: string, unit: string, min: number, max = Infinity, integer = true) => ({ label, unit, min, max, integer })
export const paramFields: Record<keyof Params, ReturnType<typeof field>> = {
  duration_min: field('运行时长','分钟',1,1440),
  step_sec: field('仿真步长','秒',1,300),
  ride_speed_kmh: field('骑行速度','km/h',0.1,100,false),
  dispatch_speed_kmh: field('运输速度','km/h',0.1,100,false),
  speed: field('初始倍速','×',0.1,600,false),
  horizon_min: field('预测窗口','分钟',1,1440),
  safety_stock: field('安全库存','辆',0),
  max_dispatch: field('单次调度上限','辆',0),
}
export const paramKeys = Object.keys(paramFields) as (keyof Params)[]
export const metricFields: Record<keyof Metrics, [string, string]> = {
  request_count: ['借车请求','辆次'], borrow_success: ['借车成功','辆次'], borrow_failed: ['借车失败','辆次'],
  borrow_success_rate: ['借车成功率','%'], first_return_attempts: ['首次还车尝试','辆次'],
  first_return_success: ['首次还车成功','辆次'], first_return_success_rate: ['首次还车成功率','%'],
  shortage_station_min: ['缺车时长','站·分钟'], full_station_min: ['满载时长','站·分钟'],
  extra_ride_distance_m: ['改道新增距离','m'], utilization: ['车辆利用率','%'],
  dispatch_quantity: ['调度车辆','辆'], dispatch_cost_bike_m: ['运输成本','辆·米'],
  algorithm_compute_ms: ['算法耗时','ms'], target_deviation: ['目标偏差','辆'],
  unfinished_riding: ['骑行中','辆'], unfinished_waiting: ['等待还车','辆'], unfinished_transporting: ['运输中','辆'],
}
export const metricKeys = Object.keys(metricFields) as (keyof Metrics)[]
export const fmt = (value: number, digits = 2) => value.toLocaleString('zh-CN', { maximumFractionDigits: digits })
export const metricValue = (key: keyof Metrics, value?: number | null) =>
  value == null ? '—' : fmt(value * (metricFields[key][1] === '%' ? 100 : 1))
const pad = (value: number) => String(value).padStart(2, '0')
export function clock(startMinute: number, seconds = 0) {
  const total = startMinute * 60 + seconds
  const day = Math.floor(total / 86400)
  return (day === 1 ? '次日 ' : day > 1 ? '+' + day + '天 ' : '')
    + pad(Math.floor(total / 3600) % 24) + ':' + pad(Math.floor(total / 60) % 60) + ':' + pad(total % 60)
}
export const timestamp = (iso: string) => new Intl.DateTimeFormat('zh-CN', {
  timeZone: 'Asia/Shanghai', dateStyle: 'short', timeStyle: 'medium',
}).format(new Date(iso))
export const stock = (station: Station | StationState) => 'stock' in station ? station.stock : station.initial_stock
export const reserved = (station: Station | StationState) => 'reserved_inbound' in station ? station.reserved_inbound : 0
export function stationStatus(station: Station | StationState) {
  if (!station.active) return { key: 'inactive', label: '已停用' }
  if (station.capacity <= stock(station) + reserved(station)) return { key: 'full', label: '满载' }
  if (!stock(station)) return { key: 'empty', label: '缺车' }
  return { key: 'normal', label: '正常' }
}
export const toMap = ([x, y]: Point, height: number): Point => [height - y, x]
export const fromMap = (latitude: number, longitude: number, height: number): Point => [longitude, height - latitude]
export function routePoint(route: Point[], progress: number): Point {
  const lengths = route.slice(1).map(([x, y], i) => Math.hypot(x - route[i][0], y - route[i][1]))
  let remaining = lengths.reduce((sum, length) => sum + length, 0) * Math.max(0, Math.min(1, progress))
  for (const [i, length] of lengths.entries()) {
    if (length > 0 && remaining <= length) {
      const [x, y] = route[i]
      const [endX, endY] = route[i + 1]
      return [x + (endX - x) * remaining / length, y + (endY - y) * remaining / length]
    }
    remaining -= length
  }
  return route[route.length - 1]
}
export const taskProgress = (task: Task, time: number) => task.status === 'completed' ? 1
  : Math.max(0, Math.min(1, (time - task.depart_sec) / Math.max(1, task.arrival_sec - task.depart_sec)))

export const inRange = (n: number, min: number, max = Infinity, int = false) =>
  Number.isFinite(n) && n >= min && n <= max && (!int || Number.isInteger(n))
export const validSeed = (n: number) => inRange(n, 0, 4294967295, true)
export function stationError(station: StationCreate, bounds?: { width: number; height: number } | null) {
  if (!station.name.trim() || !station.zone.trim() || station.name.length > 128 || station.zone.length > 128)
    return '请输入 1 至 128 个字符的站点名称和区域。'
  if (!inRange(station.capacity, 1, Infinity, true) || !inRange(station.initial_stock, 0, station.capacity, true))
    return '容量须为正整数，初始库存须为 0 至容量之间的整数。'
  if (!inRange(station.x, 0, bounds?.width) || !inRange(station.y, 0, bounds?.height))
    return '站点坐标须在地图内。'
  return ''
}
export function scenarioError(scenario: Scenario, stations: Station[], duration = scenario.duration_min) {
  if (!scenario.name.trim() || scenario.name.length > 128) return '请输入 1 至 128 个字符的场景名称。'
  if (!inRange(scenario.start_minute, 0, 1439, true) || !inRange(scenario.duration_min, 1, 1440, true))
    return '开始时刻须为 0 至 1439 分钟，默认时长须为 1 至 1440 分钟。'
  const stationIds = new Set(stations.filter(item => item.active).map(item => item.id))
  const routes = new Set<string>()
  for (const [index, od] of scenario.od_demands.entries()) {
    const label = '第 ' + (index + 1) + ' 条 OD'
    if (!stationIds.has(od.origin_id) || !stationIds.has(od.destination_id) || od.origin_id === od.destination_id)
      return label + '需要两个不同的有效站点。'
    const route = JSON.stringify([od.origin_id, od.destination_id])
    if (routes.has(route)) return label + '的起终点组合已存在。'
    routes.add(route)
    if (!inRange(od.rate_per_min, 0)) return label + '的基础需求率须为非负数。'
    let end = 0
    for (const period of [...od.periods].sort((a,b) => a.start_min - b.start_min)) {
      if (!inRange(period.start_min, end, duration) || !inRange(period.end_min, 0, duration)
        || period.end_min <= period.start_min || !inRange(period.multiplier, 0))
        return label + '的倍率时段须在时长内、互不重叠，且时长为正、倍率非负。'
      end = period.end_min
    }
  }
  return ''
}
export function paramsError(params: Params) {
  for (const key of paramKeys) {
    const { label, min, max, integer } = paramFields[key]
    if (!inRange(params[key], min, max, integer)) return label + '超出允许范围。'
  }
  return params.duration_min * 60 % params.step_sec === 0 ? '' : '仿真步长须整除运行时长。'
}
export function runError(input: RunInput, scenarios: Scenario[], stations: Station[]) {
  const scenario = scenarios.find(item => item.id === input.scenario_id)
  if (!scenario) return '请选择场景。'
  if (!stations.some(station => station.active)) return '至少需要一个已启用的停车点。'
  if (!validSeed(input.seed)) return '随机种子须为 0 至 4294967295 之间的整数。'
  return paramsError(input.params) || scenarioError(scenario, stations, input.params.duration_min)
}
export function batchError(input: BatchInput, scenarios: Scenario[], stations: Station[]) {
  if (!input.scenario_ids.length || !input.algorithms.length || !input.seeds.length) return '请选择场景、策略并输入种子。'
  if (!input.seeds.every(validSeed) || new Set(input.seeds).size !== input.seeds.length)
    return '种子须为互不重复的 0 至 4294967295 之间的整数。'
  const invalid = paramsError(input.params)
  if (invalid) return invalid
  if (new Set(input.dispatch_times_sec).size !== input.dispatch_times_sec.length
    || input.dispatch_times_sec.some(t => !inRange(t, 0, input.params.duration_min * 60 - 1, true) || t % input.params.step_sec))
    return '触发秒须互不重复、与步长对齐，并且早于运行终点。'
  for (const id of input.scenario_ids) {
    const error = runError({ params: input.params, scenario_id: id, seed: input.seeds[0], algorithm: input.algorithms[0] }, scenarios, stations)
    if (error) return error
  }
  return ''
}
