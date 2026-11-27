import type { ErrorBody, State } from './types'
export class ApiError extends Error {
  constructor(readonly status: number, readonly code: string, text: string, readonly details: Record<string, unknown> = {}) {
    super(status === 501 ? '业务接口尚未实现：' + text : text)
    this.name = 'ApiError'
  }

  get uncertain() {
    return this.status === 0 || this.status >= 500 && this.status !== 501
  }
}
export const message = (error: unknown) => error instanceof Error ? error.message : '请求失败，请重试。'
export type StreamMessage = ({ type: 'state' } & State) | ({ type: 'error' } & ErrorBody)
export type Api = {
  request<T>(method: string, path: string, body?: unknown): Promise<T>
  stream(id: string, receive: (packet: StreamMessage) => void, disconnected: () => void):
    { ready: Promise<void>; close: () => void }
}
