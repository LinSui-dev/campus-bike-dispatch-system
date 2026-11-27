<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { useConfig } from '../stores/config'
import { useRuntime } from '../stores/runtime'
import { algorithmNames, clock, inRange, paramFields, paramKeys, runError, statusNames } from '../domain'
import Modal from './Modal.vue'

const config = useConfig()
const run = useRuntime()
const dialog = ref<'reset' | 'stop' | ''>('')
const formError = ref('')
const state = computed(() => run.runtime.mode === 'batch' ? null : run.state)
const canSave = computed(() => run.runtime.mode === 'interactive' && state.value && state.value.status !== 'aborted')
const speed = ref(60)
const status = computed(() => {
  if (!run.available) return '正在连接后端'
  if (run.runtime.mode === 'batch') return statusNames.batch
  if (run.runtime.mode === 'interactive') return state.value ? statusNames[state.value.status] : '正在恢复运行'
  return statusNames.idle
})
watch(() => run.active?.context.current_speed, value => { if (value !== undefined) speed.value = value }, { immediate: true })
async function start() {
  formError.value = runError(config.draft, config.scenarios, config.stations)
  if (!formError.value) await run.start(structuredCloneInput())
}
const structuredCloneInput = () => ({ ...config.draft, params: { ...config.draft.params } })
function setSpeed() {
  formError.value = inRange(speed.value, 0.1, 600) ? '' : '倍速须为 0.1 至 600 之间的数字。'
  if (!formError.value) void run.command({ action: 'speed', value: speed.value })
}
function finish(action: 'stop' | 'reset', save?: boolean) {
  dialog.value = ''
  if (action === 'stop') void run.command({ action })
  else void run.command({ action, save: Boolean(save) })
}
</script>

<template>
  <div class="run-bar">
    <div class="run-readout">
      <span class="live-dot" :class="{ on: run.active?.status === 'running', paused: run.active?.status === 'paused' }" />
      <strong data-testid="runtime-status">{{ status }}</strong>
      <template v-if="state">
        <span class="readout-divider" />
        <span>{{ state.context.scenario_name }}</span>
        <time data-testid="sim-clock">{{ clock(state.context.start_minute, state.sim_time_sec) }}</time>
        <span>种子 {{ state.context.seed }}</span>
        <span data-testid="current-speed">{{ state.context.current_speed }}×</span>
        <details class="context-details">
          <summary>运行参数</summary>
          <dl class="facts">
            <dt>场景起点</dt><dd>{{ clock(state.context.start_minute) }}</dd>
            <dt>调度策略</dt><dd>{{ algorithmNames[state.algorithm] }}</dd>
            <dt>路网版本</dt><dd>{{ state.context.network_version }}</dd>
            <template v-for="key in paramKeys" :key="key">
              <dt>{{ paramFields[key].label }}</dt><dd>{{ state.context.params[key] }} {{ paramFields[key].unit }}</dd>
            </template>
          </dl>
        </details>
      </template>
    </div>
    <div class="toolbar run-actions">
      <template v-if="run.active">
        <button v-if="run.active.status === 'running'" :disabled="run.pending" @click="run.command({ action: 'pause' })">暂停</button>
        <button v-else class="primary" :disabled="run.pending" @click="run.command({ action: 'resume' })">继续</button>
        <form class="speed-box" novalidate @submit.prevent="setSpeed">
          <input v-model.number="speed" aria-label="运行倍速" type="number" min="0.1" max="600" step="any" :disabled="run.pending" />
          <button :disabled="run.pending">设倍速</button>
        </form>
      </template>
      <template v-if="canSave">
        <button :disabled="run.pending" @click="dialog = 'stop'">停止</button>
        <button :disabled="run.pending" @click="dialog = 'reset'">重置</button>
      </template>
      <button v-else class="primary" :disabled="run.busy || run.pending || !config.draft.scenario_id" @click="start">
        {{ run.pending ? '正在处理…' : '开始仿真' }}
      </button>
    </div>
  </div>
  <p v-if="run.connection === 'polling'" class="banner warning" role="status">实时连接已断开，正在轮询运行状态。</p>
  <p v-if="run.connectionError" class="banner warning" role="status">{{ run.connectionError }}</p>
  <p v-if="run.error || formError" class="banner error" role="alert">{{ run.error || formError }} <button v-if="formError" class="text-button" @click="formError = ''">关闭提示</button></p>

  <Modal v-if="dialog === 'reset'" title="如何处理本次运行？" @close="dialog = ''">
    <p>保存可在实验分析中查看当前结果。舍弃将清空本次运行。</p>
    <footer class="toolbar dialog-actions">
      <button @click="dialog = ''">取消</button>
      <button class="danger" @click="finish('reset', false)">舍弃并重置</button>
      <button class="primary" @click="finish('reset', true)">保存并重置</button>
    </footer>
  </Modal>
  <Modal v-if="dialog === 'stop'" title="停止并保存运行？" @close="dialog = ''">
    <p>停止后将在实验分析中保留当前结果。</p>
    <footer class="toolbar dialog-actions">
      <button @click="dialog = ''">取消</button>
      <button class="primary" @click="finish('stop')">停止并保存</button>
    </footer>
  </Modal>
</template>
