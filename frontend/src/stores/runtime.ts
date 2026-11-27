import { defineStore } from 'pinia'
import { computed, ref, shallowRef } from 'vue'
import { api, ApiError, message, retryable } from '../api'
import { CONTRACT_VERSION } from '../types'
import type { BatchInput, BatchResult, Control, RunInput, Runtime, Sample, State, SupplyDemand } from '../types'
import { useConfig } from './config'

const idle: Runtime = { mode: 'idle', run_id: null, batch_id: null }
const terminal = (state: State) => state.status !== 'running' && state.status !== 'paused'
const missing = (error: unknown) => error instanceof ApiError && error.status === 404

export const useRuntime = defineStore('runtime', () => {
  const config = useConfig()
  const runtime = shallowRef<Runtime>(idle)
  const state = shallowRef<State | null>(null)
  const batch = shallowRef<BatchResult | null>(null)
  const supply = shallowRef<SupplyDemand | null>(null)
  const samples = shallowRef<Sample[]>([])
  const connection = ref<'idle' | 'connecting' | 'live' | 'polling'>('idle')
  const available = ref(false)
  const error = ref('')
  const connectionError = ref('')
  const pending = ref(false)
  const busy = computed(() => !available.value || runtime.value.mode !== 'idle')
  const active = computed(() => runtime.value.mode === 'interactive' && state.value?.run_id === runtime.value.run_id
    && !terminal(state.value) ? state.value : null)
  const currentStations = computed(() => runtime.value.mode === 'batch' ? [] : state.value?.stations ?? config.stations)

  let generation = 0
  let closeStream: (() => void) | undefined
  let timer: number | undefined
  let running = false
  let polling = false
  let pollCount = 0
  let supplying = false
  let lastSupplySeq = -1
  let showSupply = false

  function accept(next: State) {
    if (runtime.value.mode !== 'interactive' || next.run_id !== runtime.value.run_id) return
    if (next.contract_version !== CONTRACT_VERSION) {
      connectionError.value = '运行状态的契约版本不匹配。'
      return
    }
    if (state.value?.run_id === next.run_id && state.value.seq >= next.seq) return
    state.value = next
    const point = { sim_time_sec: next.sim_time_sec, metrics: next.metrics, stations: next.stations }
    const previous = samples.value
    samples.value = previous.at(-1)?.sim_time_sec === point.sim_time_sec
      ? [...previous.slice(0, -1), point] : [...previous, point]
    if (showSupply) void refreshSupply()
  }

  function disconnect() {
    generation++
    closeStream?.()
    closeStream = undefined
    connection.value = 'idle'
  }

  async function catchUp(id: string, ticket: number) {
    const snapshot = await api.state(id)
    if (ticket === generation) accept(snapshot)
  }

  async function connect(id: string, ticket: number) {
    const buffer: State[] = []
    let synced = false
    connection.value = 'connecting'
    const socket = await api.stream(id, packet => {
      if (ticket !== generation) return
      if (packet.type === 'error') {
        connectionError.value = packet.message
        return
      }
      const { type: _type, ...next } = packet
      if (synced) accept(next)
      else buffer.push(next)
    }, () => {
      if (ticket === generation) connection.value = 'polling'
    })
    if (ticket !== generation) { socket.close(); return }
    closeStream = socket.close
    try {
      await socket.ready
    } catch {
      socket.close()
      if (ticket === generation) connection.value = 'polling'
    }
    if (ticket !== generation) return
    await catchUp(id, ticket)
    if (ticket !== generation) return
    synced = true
    for (const next of buffer.sort((a, b) => a.seq - b.seq)) accept(next)
    if (connection.value === 'connecting') connection.value = 'live'
  }

  async function follow(next: Runtime, initial?: State | BatchResult) {
    if (next.mode === runtime.value.mode && next.run_id === runtime.value.run_id && next.batch_id === runtime.value.batch_id) return
    disconnect()
    const previous = runtime.value
    runtime.value = next
    const ticket = generation
    connectionError.value = ''
    pollCount = 0
    if (next.mode === 'idle') {
      if (previous.mode === 'batch') {
        const result = await api.batch(previous.batch_id)
        if (ticket === generation) batch.value = result
      }
      if (previous.mode === 'interactive' && state.value && !terminal(state.value)) {
        state.value = null
        supply.value = null
        samples.value = []
      }
      return
    }
    state.value = null
    samples.value = []
    supply.value = null
    lastSupplySeq = -1
    if (next.mode === 'interactive') {
      if (initial && 'run_id' in initial) accept(initial)
      await connect(next.run_id, ticket)
    } else {
      batch.value = initial && 'items' in initial ? initial : null
      const progress = await api.batch(next.batch_id)
      if (ticket === generation) batch.value = progress
    }
  }

  async function reconcile() {
    const ticket = generation
    const next = await api.runtime()
    if (ticket !== generation) return
    available.value = true
    if (next.mode === 'idle' && runtime.value.mode === 'interactive') {
      try {
        await catchUp(runtime.value.run_id, ticket)
      } catch (error) {
        if (!missing(error)) throw error
      }
      if (ticket !== generation) return
    }
    try {
      await follow(next)
    } catch (err) {
      if (!missing(err)) throw err
      // The slot may have been reset between runtime and the per-run reads.
      const recovery = generation
      const latest = await api.runtime()
      if (recovery === generation) await follow(latest)
    }
  }

  async function poll() {
    if (polling || pending.value || !running) return
    polling = true
    const ticket = generation
    try {
      const current = runtime.value
      if (!available.value || current.mode === 'idle' || ++pollCount % 4 === 0 || state.value && terminal(state.value)) {
        await reconcile()
      }
      if (ticket !== generation) return
      if (current.mode === 'interactive' && connection.value !== 'live') {
        await catchUp(current.run_id, ticket)
        if (ticket === generation && pollCount % 3 === 0 && state.value && !terminal(state.value)) {
          const previous = closeStream
          generation++
          previous?.()
          await connect(current.run_id, generation)
        }
      } else if (current.mode === 'batch') {
        const progress = await api.batch(current.batch_id)
        if (ticket === generation) batch.value = progress
      }
      connectionError.value = ''
    } catch (err) {
      if (missing(err)) {
        try { await reconcile() } catch (failure) { connectionError.value = message(failure) }
      } else {
        connectionError.value = message(err)
      }
    } finally {
      polling = false
    }
  }

  function mount() {
    running = true
    void poll()
    timer = window.setInterval(poll, 1000)
  }

  function unmount() {
    running = false
    clearInterval(timer)
    disconnect()
  }

  async function act(work: () => Promise<void>) {
    if (pending.value) return
    pending.value = true
    error.value = ''
    try { await work() } catch (err) { error.value = message(err) }
    finally { pending.value = false }
  }

  function start(input: RunInput) {
    return act(async () => {
      if (busy.value) return
      const next = await retryable('start', input, request_id => api.start({ ...input, request_id }))
      try { await follow({ mode: 'interactive', run_id: next.run_id, batch_id: null }, next) }
      catch (err) { if (missing(err)) await reconcile(); else throw err }
    })
  }

  function command(body: Control) {
    const id = runtime.value.run_id
    if (!id) return
    return act(async () => {
      let result
      try {
        result = await api.control(id, body)
      } catch (err) {
        if (missing(err)) await reconcile()
        else throw err
        return
      }
      if ('mode' in result) {
        state.value = null
        samples.value = []
        supply.value = null
        await follow({ mode: 'idle', run_id: null, batch_id: null })
      } else {
        accept(result)
        if (terminal(result)) await reconcile()
      }
    })
  }

  function dispatch() {
    const id = active.value?.run_id
    if (!id) return
    return act(async () => {
      const result = await retryable('dispatch-' + id, { id }, request_id => api.dispatch(id, request_id))
      await catchUp(id, generation)
      if (runtime.value.run_id === id && (!supply.value || result.supply_demand.now_sec >= supply.value.now_sec))
        supply.value = result.supply_demand
    })
  }

  function startBatch(input: BatchInput) {
    return act(async () => {
      if (busy.value) return
      const result = await retryable('batch', input, request_id => api.startBatch({ ...input, request_id }))
      await follow({ mode: 'batch', run_id: null, batch_id: result.id }, result)
    })
  }

  async function refreshSupply(force = false) {
    const current = state.value
    if (!current || supplying || !force && current.seq <= lastSupplySeq) return
    supplying = true
    const ticket = generation
    try {
      const response = await api.supply(current.run_id)
      if (ticket === generation && state.value?.run_id === current.run_id) {
        if (!supply.value || response.now_sec >= supply.value.now_sec) supply.value = response
        lastSupplySeq = current.seq
      }
    } catch (err) {
      if (force && ticket === generation) error.value = message(err)
    } finally {
      supplying = false
    }
  }

  function watchSupply(on: boolean) {
    showSupply = on
    if (on) void refreshSupply(true)
  }

  return {
    runtime, state, batch, supply, samples, active, currentStations, connection, available,
    busy, error, connectionError, pending, mount, unmount, start, command, dispatch, startBatch, watchSupply,
  }
})
