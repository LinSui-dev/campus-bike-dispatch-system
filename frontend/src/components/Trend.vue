<script setup lang="ts">
import { computed } from 'vue'
import Chart from './Chart.vue'
import type { Sample } from '../types'
import { clock } from '../domain'
const props = defineProps<{ samples: Sample[]; start: number }>()
const lines = [
  { key: 'borrow_success', name: '借车成功', color: '#18766b' },
  { key: 'borrow_failed', name: '借车失败', color: '#bb553f' },
  { key: 'first_return_success', name: '首次还车成功', color: '#4577af' },
] as const
const options = computed(() => props.samples.length ? {
  grid: { left: 60, right: 30, bottom: 54, top: 32 },
  tooltip: { trigger: 'axis', valueFormatter: (value: number) => value + ' 辆次' },
  legend: { bottom: 0 },
  xAxis: { type: 'value', axisLabel: { formatter: (value: number) => clock(props.start, Math.floor(value)).replace(/:\d{2}$/, '') } },
  yAxis: { type: 'value', name: '辆次', minInterval: 1 },
  series: lines.map(({ key, name, color }) => ({
    type: 'line', name, color, symbol: 'circle', symbolSize: 5,
    data: props.samples.map(sample => [sample.sim_time_sec, sample.metrics[key]]),
  })),
} : null)
</script>

<template><Chart :option="options" label="按仿真时刻统计的借还累计趋势" /></template>
