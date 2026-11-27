<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import type { BatchResult, Metrics } from '../types'
import { algorithms } from '../types'
import { algorithmNames, metricFields, metricKeys, metricValue, statusNames } from '../domain'
import { useConfig } from '../stores/config'
import Chart from './Chart.vue'
const props = defineProps<{ batch: BatchResult }>()
const emit = defineEmits<{ open: [runId: string] }>()
const config = useConfig()
const metric = ref<keyof Metrics>('borrow_success_rate')
const scenario = ref('')
const scenarios = computed(() => [...new Set(props.batch.aggregates.map(row => row.scenario_id))])
watch(scenarios, () => {
  if (!scenarios.value.includes(scenario.value)) scenario.value = scenarios.value[0] ?? ''
}, { immediate: true })
const groups = computed(() => algorithms.flatMap(algorithm => props.batch.aggregates
  .filter(row => row.scenario_id === scenario.value && row.algorithm === algorithm)))
const scale = computed(() => metricFields[metric.value][1] === '%' ? 100 : 1)
const compare = computed(() => groups.value.some(row => row.metrics[metric.value]?.mean != null) ? {
  grid: { left: 75, top: 28, right: 28, bottom: 36 },
  tooltip: { trigger: 'axis' },
  xAxis: { type: 'category', data: groups.value.map(row => algorithmNames[row.algorithm]) },
  yAxis: { type: 'value', name: metricFields[metric.value][1] },
  series: [{
    type: 'bar', name: metricFields[metric.value][0], barMaxWidth: 44,
    data: groups.value.map(row => {
      const value = row.metrics[metric.value]?.mean
      return value == null ? null : { value: value * scale.value, itemStyle: { color: { none: '#7690a1', greedy: '#15736e', min_cost_flow: '#446eae' }[row.algorithm] } }
    }),
  }],
} : null)
</script>

<template>
  <section class="panel">
    <header class="section-head"><div><h2>批次进度</h2><p class="identifier">{{ batch.id }}</p></div>
      <span class="pill" :class="{ empty: batch.status === 'failed', full: batch.status === 'partial_failed' }">{{ statusNames[batch.status] }}</span></header>
    <div class="batch-progress"><strong>{{ batch.finished }} / {{ batch.total }} 组已结束</strong>
      <progress :value="batch.finished" :max="batch.total || 1" aria-label="批次完成进度" /></div>
    <div v-if="batch.items.length" class="table-scroll batch-scroll">
      <table><thead><tr><th scope="col">场景</th><th scope="col">策略</th><th scope="col">种子</th><th scope="col">状态</th><th scope="col">结果</th></tr></thead>
        <tbody><tr v-for="item in batch.items" :key="[item.scenario_id, item.algorithm, item.seed].join('/')">
          <th scope="row">{{ config.scenarioName(item.scenario_id) }}</th><td>{{ algorithmNames[item.algorithm] }}</td><td>{{ item.seed }}</td>
          <td><span class="pill" :class="{ empty: item.status === 'failed' }">{{ statusNames[item.status] }}</span></td>
          <td><span v-if="item.error" class="error-text">{{ item.error.message }}（{{ item.error.code }}）</span>
            <button v-else-if="item.run_id" class="text-button" @click="emit('open', item.run_id)">查看历史</button>
            <span v-else>—</span></td>
        </tr></tbody>
      </table>
    </div>
  </section>
  <section class="panel">
    <header class="section-head"><div><h2>策略对照</h2><p>样本标准差以有效记录计算，有效 n 小于 2 时显示 —。</p></div>
      <div v-if="scenarios.length" class="toolbar">
        <select v-model="scenario" aria-label="对照场景"><option v-for="id in scenarios" :key="id" :value="id">{{ config.scenarioName(id) }}</option></select>
        <select v-model="metric" aria-label="对照指标"><option v-for="key in metricKeys" :key="key" :value="key">{{ metricFields[key][0] }}</option></select>
      </div>
    </header>
    <Chart :option="compare" :label="metricFields[metric][0] + '策略均值对照'" />
    <div v-if="groups.length" class="table-scroll"><table>
      <thead><tr><th scope="col">策略</th><th scope="col">均值（{{ metricFields[metric][1] }}）</th>
        <th scope="col">样本标准差（{{ metricFields[metric][1] }}）</th><th scope="col">有效 n</th></tr></thead>
      <tbody><tr v-for="row in groups" :key="row.algorithm"><th scope="row">{{ algorithmNames[row.algorithm] }}</th>
        <td>{{ metricValue(metric, row.metrics[metric]?.mean) }}</td><td>{{ metricValue(metric, row.metrics[metric]?.stddev) }}</td>
        <td>{{ row.metrics[metric]?.n ?? '—' }}</td></tr></tbody>
    </table></div>
  </section>
</template>
