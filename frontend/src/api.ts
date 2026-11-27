import type * as D from './types'
import type { Api, StreamMessage } from './transport'
import { ApiError } from './transport'
export { ApiError, message } from './transport'

export const mockMode = import.meta.env.VITE_USE_MOCK === 'true'

const http: Api = {
  async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    let response: Response
    try {
      response = await fetch('/api/v1' + path, {
        method, cache: 'no-store', signal: AbortSignal.timeout(8000),
        headers: body === undefined ? undefined : { 'Content-Type': 'application/json' },
        body: body === undefined ? undefined : JSON.stringify(body),
      })
    } catch (error) {
      const timeout = error instanceof DOMException && error.name === 'TimeoutError'
      throw new ApiError(0, timeout ? 'TIMEOUT' : 'NETWORK', timeout ? '请求超时，可以重试。' : '无法连接后端，请检查服务。')
    }
    if (response.status === 204) return undefined as T
    const payload = await response.json().catch(() => null)
    if (!response.ok) {
      const failure = payload as Partial<D.ErrorBody> | null
      throw new ApiError(response.status, failure?.code ?? 'HTTP_ERROR', failure?.message ?? 'HTTP ' + response.status, failure?.details)
    }
    if (payload === null) throw new ApiError(0, 'INVALID_RESPONSE', '后台未返回有效 JSON。')
    return payload as T
  },
  stream(id, receive, disconnected) {
    const url = new URL('/ws/runs/' + encodeURIComponent(id), location.href)
    url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
    const socket = new WebSocket(url)
    const ready = new Promise<void>((resolve, reject) => {
      const timer = window.setTimeout(() => reject(new Error('状态连接超时')), 2400)
      socket.addEventListener('open', () => { clearTimeout(timer); resolve() }, { once: true })
      socket.addEventListener('close', () => { clearTimeout(timer); reject(new Error('状态连接关闭')); disconnected() }, { once: true })
      socket.addEventListener('error', () => { clearTimeout(timer); reject(new Error('状态连接失败')) }, { once: true })
    })
    socket.addEventListener('message', event => {
      try {
        const packet = JSON.parse(event.data) as StreamMessage
        if (packet.type === 'state' || packet.type === 'error') receive(packet)
      } catch {
        // Keep the last valid snapshot when a frame is malformed.
      }
    })
    return { ready, close: () => socket.close() }
  },
}
const transport = mockMode ? import('./mocks/transport').then(module => module.mock) : Promise.resolve(http)
const send = <T>(method: string, path: string, body?: unknown) => transport.then(api => api.request<T>(method, path, body))
const get = <T>(path: string) => send<T>('GET', path)
const idPath = (base: string, id: string) => base + '/' + encodeURIComponent(id)
const resource = <T, Create, Patch>(base: string) => ({
  list: () => get<D.List<T>>(base),
  create: (body: Create) => send<T>('POST', base, body),
  update: (id: string, body: Patch) => send<T>('PATCH', idPath(base, id), body),
  remove: (id: string, query = '') => send<void>('DELETE', idPath(base, id) + query),
})
const run = (id: string) => idPath('/runs', id)
export const api = {
  runtime: () => get<D.Runtime>('/runtime'),
  map: () => get<D.MapInfo>('/map'),
  roads: () => get<D.RoadNetwork>('/roads'),
  stations: resource<D.Station, D.StationCreate, D.StationPatch>('/stations'),
  scenarios: resource<D.Scenario, D.Scenario, D.ScenarioPatch>('/scenarios'),
  configs: resource<D.Config, D.Config, Partial<Omit<D.Config, 'id'>>>('/configs'),
  replaceOD: (id: string, od_demands: D.OD[]) => send<D.Scenario>('PUT', idPath('/scenarios', id) + '/od', { od_demands }),
  start: (body: D.RunRequest) => send<D.State>('POST', '/runs', body),
  state: (id: string) => get<D.State>(run(id) + '/state'),
  control: (id: string, body: D.Control) => send<D.State | D.ResetReceipt>('POST', run(id) + '/control', body),
  supply: (id: string) => get<D.SupplyDemand>(run(id) + '/supply-demand'),
  dispatch: (id: string, request_id: string) => send<D.DispatchReceipt>('POST', run(id) + '/dispatch', { request_id }),
  tasks: (id: string) => get<D.List<D.Task>>(run(id) + '/tasks'),
  history: () => get<D.List<D.RunSummary>>('/runs'),
  detail: (id: string) => get<D.RunDetail>(run(id)),
  metrics: (id: string) => get<D.List<D.Sample>>(run(id) + '/metrics'),
  startBatch: (body: D.BatchRequest) => send<D.BatchResult>('POST', '/batches', body),
  batch: (id: string) => get<D.BatchResult>(idPath('/batches', id)),
  stream: async (id: string, receive: Parameters<Api['stream']>[1], disconnect: () => void) =>
    (await transport).stream(id, receive, disconnect),
}

export async function retryable<T>(operation: string, payload: object, sendRequest: (id: string) => Promise<T>) {
  const key = 'bike-command-' + (mockMode ? 'mock-' : 'real-') + operation
  const signature = JSON.stringify(payload)
  const raw = sessionStorage.getItem(key)
  const previous = raw ? JSON.parse(raw) as { signature: string; id: string } : null
  const id = previous?.signature === signature ? previous.id : crypto.randomUUID()
  sessionStorage.setItem(key, JSON.stringify({ signature, id }))
  try {
    const response = await sendRequest(id)
    sessionStorage.removeItem(key)
    return response
  } catch (error) {
    if (!(error instanceof ApiError && error.uncertain)) sessionStorage.removeItem(key)
    throw error
  }
}
