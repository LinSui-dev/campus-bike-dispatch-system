<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { api, message } from '../api'
import { algorithmNames, clock, runError, scenarioError } from '../domain'
import { useConfig } from '../stores/config'
import { useRuntime } from '../stores/runtime'
import { algorithms } from '../types'
import type { Config, Scenario } from '../types'
import ParamsFields from '../components/ParamsFields.vue'
import Modal from '../components/Modal.vue'

const config = useConfig()
const run = useRuntime()
const scenario = ref<Scenario | null>(null)
const original = computed(() => config.scenarios.find(item => item.id === scenario.value?.id))
const savedId = ref('')
const configName = ref('')
const removing = ref<'scenario' | 'config' | ''>('')
const saving = ref(false)
const error = ref('')
const notice = ref('')
const locked = computed(() => run.busy || run.pending || saving.value)
const clone = <T,>(data: T): T => JSON.parse(JSON.stringify(data))

function selectScenario(id: string) {
  const item = config.scenarios.find(entry => entry.id === id)
  scenario.value = item ? clone(item) : null
}
watch(() => config.scenarios, items => {
  if (!scenario.value || !items.some(item => item.id === scenario.value?.id)) selectScenario(items[0]?.id ?? '')
}, { immediate: true })
function newScenario(source?: Scenario) {
  const fields = source ? { ...clone(source), name: source.name.slice(0, 124) + '（副本）' }
    : { name: '', start_minute: 420, duration_min: 120, description: '', od_demands: [] }
  scenario.value = { ...fields, id: crypto.randomUUID(), is_preset: false }
  error.value = notice.value = ''
}
function chooseRunScenario() {
  const item = config.scenarios.find(entry => entry.id === config.draft.scenario_id)
  if (item) config.draft.params.duration_min = item.duration_min
}
async function change(work: () => Promise<void>) {
  if (locked.value) return
  error.value = notice.value = ''
  saving.value = true
  try { await work() } catch (failure) { error.value = message(failure) }
  finally { saving.value = false }
}
function updateScenario(value: Scenario) {
  config.scenarios = original.value
    ? config.scenarios.map(item => item.id === value.id ? value : item)
    : [...config.scenarios, value]
  notice.value = '已保存 ' + value.name + '。'
}
function saveScenario(part: 'meta' | 'od') {
  if (!scenario.value) return
  const edited = clone(scenario.value)
  edited.name = edited.name.trim()
  const previous = original.value
  const { name, start_minute, duration_min, description } = edited
  const candidate = previous
    ? part === 'od' ? { ...previous, od_demands: edited.od_demands } : { ...previous, name, start_minute, duration_min, description }
    : edited
  const invalid = scenarioError(candidate, config.stations)
  if (invalid) { error.value = invalid; return }
  void change(async () => {
    const result = !previous ? await api.scenarios.create(edited)
      : part === 'od' ? await api.replaceOD(edited.id, edited.od_demands)
      : await api.scenarios.update(edited.id, { name, start_minute, duration_min, description })
    updateScenario(result)
    scenario.value = clone(result)
    if (previous && part === 'meta') scenario.value.od_demands = edited.od_demands
    if (previous && part === 'od') Object.assign(scenario.value, { name, start_minute, duration_min, description })
  })
}
function loadConfig() {
  const selected = config.configs.find(item => item.id === savedId.value)
  configName.value = selected?.name ?? ''
  if (selected) {
    const { id: _id, name: _name, ...input } = selected
    config.draft = clone(input)
  }
}
function saveConfig(asNew: boolean) {
  const name = configName.value.trim()
  error.value = !name || name.length > 128 ? '请输入 1 至 128 个字符的配置名称。' : runError(config.draft, config.scenarios, config.stations)
  if (error.value) return
  const value: Config = { ...clone(config.draft), id: asNew ? crypto.randomUUID() : savedId.value, name }
  void change(async () => {
    const { id, ...fields } = value
    const result = asNew ? await api.configs.create(value) : await api.configs.update(id, fields)
    config.configs = asNew ? [...config.configs, result] : config.configs.map(item => item.id === id ? result : item)
    savedId.value = result.id
    notice.value = '已保存配置 ' + result.name + '。'
  })
}
function remove() {
  void change(async () => {
    if (removing.value === 'scenario' && original.value) {
      const { id } = original.value
      await api.scenarios.remove(id)
      config.scenarios = config.scenarios.filter(item => item.id !== id)
      if (config.draft.scenario_id === id) config.draft.scenario_id = config.scenarios[0]?.id ?? ''
      selectScenario(config.scenarios[0]?.id ?? '')
      notice.value = '已删除场景。'
    } else if (removing.value === 'config' && savedId.value) {
      await api.configs.remove(savedId.value)
      config.configs = config.configs.filter(item => item.id !== savedId.value)
      savedId.value = configName.value = ''
      notice.value = '已删除配置。'
    }
    removing.value = ''
  })
}
</script>

<template>
  <section class="page-heading"><h1>仿真控制</h1><p>设置运行参数、场景与起终点需求。准备完成后，用顶部控件开始仿真。</p></section>
  <p v-if="run.busy" class="banner warning">运行槽不可编辑。可在顶部查看活动运行的参数。</p>
  <p v-if="error && !removing" class="banner error" role="alert">{{ error }}</p>
  <p v-if="notice" class="banner" role="status">{{ notice }}</p>
  <section class="panel form-panel">
    <header class="section-head"><div><h2>运行配置</h2><p>选择已保存配置可载入场景、参数、种子和策略。</p></div></header>
    <fieldset class="fields fields-4" :disabled="locked">
      <label class="field">已保存配置<select v-model="savedId" @change="loadConfig">
        <option value="">自定义</option><option v-for="item in config.configs" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label class="field">运行场景<select v-model="config.draft.scenario_id" @change="chooseRunScenario">
        <option value="" disabled>选择场景</option>
        <option v-for="item in config.scenarios" :key="item.id" :value="item.id">{{ item.name }}</option></select></label>
      <label class="field">随机种子<input v-model.number="config.draft.seed" type="number" min="0" max="4294967295" step="1" /></label>
      <label class="field">调度策略<select v-model="config.draft.algorithm">
        <option v-for="item in algorithms" :key="item" :value="item">{{ algorithmNames[item] }}</option></select></label>
    </fieldset>
    <ParamsFields v-model="config.draft.params" :disabled="locked" />
    <div class="form-footer">
      <label class="field">配置名称<input v-model="configName" maxlength="128" :disabled="locked" /></label>
      <div class="toolbar">
        <button :disabled="locked || !savedId" @click="saveConfig(false)">更新配置</button>
        <button :disabled="locked" @click="saveConfig(true)">另存配置</button>
        <button class="text-button danger" :disabled="locked || !savedId" @click="removing = 'config'; error = ''">删除配置</button>
      </div>
    </div>
  </section>
  <section class="panel form-panel">
    <header class="section-head"><div><h2>场景与需求</h2><p>需求率单位为次/分钟，倍率时段从场景起点开始计时。</p></div>
      <div class="toolbar">
        <button :disabled="locked || !original" @click="newScenario(original)">复制场景</button>
        <button :disabled="locked" @click="newScenario()">新建场景</button>
      </div>
    </header>
    <fieldset class="fields fields-4" :disabled="locked">
      <label class="field">编辑场景<select :value="scenario?.id ?? ''" @change="selectScenario(($event.target as HTMLSelectElement).value); error = ''">
        <option v-if="!original" :value="scenario?.id ?? ''">{{ scenario ? '新场景' : '选择场景' }}</option>
        <option v-for="item in config.scenarios" :key="item.id" :value="item.id">{{ item.name }}{{ item.is_preset ? '（预设）' : '' }}</option></select></label>
      <template v-if="scenario">
        <label class="field">场景名称<input v-model="scenario.name" maxlength="128" /></label>
        <label class="field">开始时刻（当天分钟）<input v-model.number="scenario.start_minute" type="number" min="0" max="1439" step="1" /></label>
        <label class="field">默认时长（分钟）<input v-model.number="scenario.duration_min" type="number" min="1" max="1440" step="1" /></label>
        <label class="field span-all">场景说明<textarea v-model="scenario.description" rows="2" /></label>
      </template>
    </fieldset>
    <template v-if="scenario">
      <div class="toolbar form-footer">
        <span v-if="Number.isInteger(scenario.start_minute)" class="muted">起点 {{ clock(scenario.start_minute) }}</span>
        <button v-if="original" :disabled="locked" @click="saveScenario('meta')">保存场景信息</button>
        <button class="text-button danger" :disabled="locked || !original || original.is_preset" @click="removing = 'scenario'; error = ''">删除场景</button>
      </div>
      <div class="section-head subsection"><div><h3>OD 需求矩阵</h3><p>按有向起终点录入需求，未配置的组合没有需求。倍率区间外使用基础需求率。</p></div>
        <button :disabled="locked || config.stations.length < 2"
          @click="scenario.od_demands.push({ origin_id: '', destination_id: '', rate_per_min: 0, periods: [] })">添加 OD</button></div>
      <p v-if="!scenario.od_demands.length" class="empty-state">暂无 OD 需求</p>
      <fieldset v-for="(od, index) in scenario.od_demands" :key="index" class="od-row" :disabled="locked" :aria-label="'OD ' + (index + 1)">
        <div class="fields fields-4">
          <label class="field">起点<select v-model="od.origin_id"><option value="" disabled>选择起点</option>
            <option v-for="station in config.stations" :key="station.id" :value="station.id" :disabled="!station.active">{{ station.name }}</option></select></label>
          <label class="field">终点<select v-model="od.destination_id"><option value="" disabled>选择终点</option>
            <option v-for="station in config.stations" :key="station.id" :value="station.id" :disabled="!station.active">{{ station.name }}</option></select></label>
          <label class="field">基础需求率<input v-model.number="od.rate_per_min" type="number" min="0" step="any" /></label>
          <div class="toolbar field-buttons"><button @click="od.periods.push({ start_min: 0, end_min: 1, multiplier: 1 })">添加倍率时段</button>
            <button class="text-button danger" @click="scenario.od_demands.splice(index, 1)">移除 OD</button></div>
        </div>
        <div v-for="(p, periodIndex) in od.periods" :key="periodIndex" class="fields fields-4 period-row">
          <label class="field">开始（分钟）<input v-model.number="p.start_min" type="number" min="0" step="any" /></label>
          <label class="field">结束（分钟）<input v-model.number="p.end_min" type="number" min="0" step="any" /></label>
          <label class="field">倍率<input v-model.number="p.multiplier" type="number" min="0" step="any" /></label>
          <button class="text-button danger field-buttons" @click="od.periods.splice(periodIndex, 1)">移除时段</button>
        </div>
      </fieldset>
      <div class="toolbar form-footer"><button class="primary" :disabled="locked" @click="saveScenario('od')">{{ original ? '保存 OD' : '创建场景' }}</button></div>
    </template>
  </section>
  <Modal v-if="removing" :title="removing === 'scenario' ? '删除场景？' : '删除配置？'" :locked="saving" @close="removing = ''">
    <p v-if="error" class="banner error" role="alert">{{ error }}</p>
    <footer class="toolbar dialog-actions"><button :disabled="saving" @click="removing = ''">取消</button><button class="danger filled" :disabled="locked" @click="remove">确认删除</button></footer>
  </Modal>
</template>
