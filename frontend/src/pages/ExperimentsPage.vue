<script setup lang="ts">
import { computed, onMounted, ref, watch } from 'vue'
import { algorithmNames, batchError, clock, defaultParams, metricValue, statusNames, timestamp } from '../domain'
import { useConfig } from '../stores/config'
import { useRuntime } from '../stores/runtime'
import { useHistory } from '../stores/history'
import { algorithms } from '../types'
import type { Algorithm, BatchInput, Params } from '../types'
import ParamsFields from '../components/ParamsFields.vue'
import BatchResults from '../components/BatchResults.vue'
import Trend from '../components/Trend.vue'
import MetricList from '../components/MetricList.vue'
import CampusMap from '../components/CampusMap.vue'

const config = useConfig()
const run = useRuntime()
const history = useHistory()
const tab = ref<'batch' | 'history'>('batch')
const scenarioIds = ref<string[]>([])
const strategies = ref<Algorithm[]>([...algorithms])
const seedsText = ref('42, 43, 44, 45, 46')
const triggersText = ref('0, 900, 1800, 2700, 3600, 4500, 5400, 6300')
const params = ref<Params>({ ...defaultParams })
const error = ref('')
const selectedTask = ref('')
const finished = computed(() => [run.state?.status, run.batch?.status].join('/'))
const snapshot = computed(() => history.detail?.snapshot)
const lastSample = computed(() => history.samples.at(-1))
const archivedMap = computed(() => config.map?.network_version === snapshot.value?.network.version ? config.map : null)

function seedScenarios() {
  if (!scenarioIds.value.length) scenarioIds.value = config.scenarios.filter(item => item.is_preset).map(item => item.id)
}
onMounted(() => { seedScenarios(); void history.load() })
watch(() => config.scenarios, seedScenarios)
watch(finished, () => {
  if (tab.value === 'history') void history.load()
})
const parseList = (value: string) => value.trim() ? value.trim().split(/[\s,，]+/).map(token => /^\d+$/.test(token) ? Number(token) : NaN) : []
const seeds = computed(() => parseList(seedsText.value))
const total = computed(() => scenarioIds.value.length * strategies.value.length * seeds.value.length)
function start() {
  const input: BatchInput = {
    scenario_ids: [...scenarioIds.value], algorithms: [...strategies.value], seeds: seeds.value,
    params: { ...params.value }, dispatch_times_sec: parseList(triggersText.value),
  }
  error.value = batchError(input, config.scenarios, config.stations)
  if (!error.value) void run.startBatch(input)
}
function open(id: string) {
  if (tab.value !== 'history') showHistory()
  selectedTask.value = ''
  void history.open(id)
}
function showHistory() {
  tab.value = 'history'
  void history.load()
}
</script>

<template>
  <section class="page-heading"><h1>实验分析</h1><p>配置批量对照，按策略比较结果，查阅已保存运行。</p></section>
  <div class="tab-bar" aria-label="实验分析视图">
    <button :aria-pressed="tab === 'batch'" @click="tab = 'batch'">批量实验</button>
    <button :aria-pressed="tab === 'history'" @click="showHistory">保存历史</button>
  </div>
  <template v-if="tab === 'batch'">
    <section v-if="run.runtime.mode !== 'batch'" class="panel form-panel">
      <header class="section-head"><div><h2>{{ run.batch ? '下一批次配置' : '批量组合' }}</h2><p>每个场景对所选策略与随机种子各执行一次。</p></div>
        <span class="pill">{{ scenarioIds.length }} 场景 × {{ strategies.length }} 策略 × {{ seeds.length }} 种子 = {{ total }} 组</span></header>
      <fieldset class="fields fields-2" :disabled="run.busy || run.pending">
        <div><h3>场景</h3><div class="checks"><label v-for="item in config.scenarios" :key="item.id" class="check">
          <input v-model="scenarioIds" type="checkbox" :value="item.id" />{{ item.name }}</label></div></div>
        <div><h3>策略</h3><div class="checks"><label v-for="item in algorithms" :key="item" class="check">
          <input v-model="strategies" type="checkbox" :value="item" />{{ algorithmNames[item] }}</label></div></div>
        <label class="field">种子（用逗号或空格分隔）<input v-model="seedsText" /></label>
        <label class="field">调度触发时刻（仿真秒）<input v-model="triggersText" /></label>
      </fieldset>
      <ParamsFields v-model="params" :disabled="run.busy || run.pending" />
      <p v-if="error" class="banner error" role="alert">{{ error }}</p>
      <div class="form-footer toolbar"><button class="primary" :disabled="run.busy || run.pending" @click="start">启动批量实验</button>
        <span v-if="run.busy" class="muted">运行槽空闲后可启动新批次。</span></div>
    </section>
    <BatchResults v-if="run.batch" :batch="run.batch" @open="open" />
    <p v-else-if="run.runtime.mode === 'batch'" class="empty-state panel" role="status">正在恢复批次进度…</p>
    <p v-else class="empty-state panel">暂无当前批次</p>
  </template>
  <template v-else>
    <p v-if="history.error" role="alert" class="banner error">{{ history.error }}</p>
    <section class="panel">
      <header class="section-head"><div><h2>已保存运行</h2><p>时间使用北京时间（Asia/Shanghai）。</p></div><button @click="history.load">刷新历史</button></header>
      <div v-if="history.runs.length" class="table-scroll"><table>
        <thead><tr><th scope="col">结束时间</th><th scope="col">策略</th><th scope="col">种子</th><th scope="col">状态</th>
          <th scope="col">借车成功率</th><th scope="col">运行</th></tr></thead>
        <tbody><tr v-for="item in history.runs" :key="item.id" :class="{ 'selected-row': item.id === history.selected }">
          <th scope="row">{{ timestamp(item.ended_at) }}</th><td>{{ algorithmNames[item.algorithm] }}</td><td>{{ item.seed }}</td>
          <td>{{ statusNames[item.status] }}</td><td>{{ metricValue('borrow_success_rate', item.summary.borrow_success_rate) }}{{ item.summary.borrow_success_rate == null ? '' : '%' }}</td>
          <td><button class="text-button" :aria-pressed="item.id === history.selected" @click="open(item.id)">查看详情</button></td>
        </tr></tbody>
      </table></div>
      <p v-else class="empty-state">暂无已保存运行</p>
    </section>
    <p v-if="history.loading" role="status">正在加载运行详情…</p>
    <template v-if="history.detail && snapshot">
      <section class="panel">
        <header class="section-head"><div><h2>{{ snapshot.scenario.name }}</h2><p class="identifier">{{ history.detail.run.id }}</p></div>
          <span class="pill">{{ statusNames[history.detail.run.status] }}</span></header>
        <dl class="scale-list">
          <div><dt>起点</dt><dd>{{ clock(snapshot.scenario.start_minute) }}</dd></div>
          <div><dt>策略</dt><dd>{{ algorithmNames[snapshot.algorithm] }}</dd></div>
          <div><dt>种子</dt><dd>{{ snapshot.seed }}</dd></div>
          <div><dt>步长</dt><dd>{{ snapshot.params.step_sec }} 秒</dd></div>
          <div><dt>路网版本</dt><dd>{{ snapshot.versions.network }}</dd></div>
        </dl>
        <MetricList :metrics="history.detail.run.summary" />
      </section>
      <section class="panel"><header class="section-head"><h2>保存时的借还趋势</h2></header>
        <Trend :samples="history.samples" :start="snapshot.scenario.start_minute" /></section>
      <section class="panel"><header class="section-head"><h2>历史站点与运输</h2></header>
        <div class="table-scroll"><table>
          <thead><tr><th scope="col">站点</th><th scope="col">初始库存</th><th scope="col">容量</th><th scope="col">末步库存</th><th scope="col">末步预留</th></tr></thead>
          <tbody><tr v-for="station in snapshot.stations" :key="station.id"><th scope="row">{{ station.name }}</th>
            <td>{{ station.initial_stock }} 辆</td><td>{{ station.capacity }} 辆</td>
            <td>{{ lastSample?.stations.find(item => item.id === station.id)?.stock ?? '—' }}</td>
            <td>{{ lastSample?.stations.find(item => item.id === station.id)?.reserved_inbound ?? '—' }}</td>
          </tr></tbody>
        </table></div>
        <div v-if="history.tasks.length" class="table-scroll"><table>
          <thead><tr><th scope="col">路线</th><th scope="col">车辆</th><th scope="col">距离</th><th scope="col">保存时状态</th></tr></thead>
          <tbody><tr v-for="task in history.tasks" :key="task.id"><th scope="row">
            <button class="text-button" @click="selectedTask = task.id">
              {{ snapshot.stations.find(station => station.id === task.source_id)?.name ?? task.source_id }} →
              {{ snapshot.stations.find(station => station.id === task.destination_id)?.name ?? task.destination_id }}
            </button></th><td>{{ task.quantity }} 辆</td><td>{{ task.distance_m }} m</td><td>{{ task.status === 'completed' ? '已到达' : '运输中' }}</td>
          </tr></tbody>
        </table></div>
        <p v-else class="empty-state">暂无已保存任务</p>
        <div v-if="archivedMap" class="dispatch-map"><CampusMap :info="archivedMap" :roads="snapshot.network"
          :stations="lastSample?.stations ?? snapshot.stations" :tasks="history.tasks" :task-id="selectedTask" :time="lastSample?.sim_time_sec" /></div>
      </section>
      <BatchResults v-if="history.archiveBatch" :batch="history.archiveBatch" @open="open" />
    </template>
  </template>
</template>
