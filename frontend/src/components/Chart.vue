<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { init, use } from 'echarts/core'
import type { EChartsCoreOption, EChartsType } from 'echarts/core'
import { BarChart, LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent, AriaComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'

use([BarChart, LineChart, GridComponent, LegendComponent, TooltipComponent, AriaComponent, CanvasRenderer])
const props = defineProps<{ option: EChartsCoreOption | null; label: string }>()
const element = ref<HTMLElement>()
let chart: EChartsType | undefined
let observer: ResizeObserver
function refresh() {
  if (!props.option) {
    chart?.clear()
    return
  }
  if (!element.value) return
  chart ??= init(element.value)
  chart.setOption({
    animation: false,
    aria: { enabled: true, label: { description: props.label } },
    ...props.option,
  }, { notMerge: true })
}
onMounted(() => {
  if (!element.value) return
  observer = new ResizeObserver(() => chart?.resize())
  observer.observe(element.value)
  refresh()
})
watch(() => [props.option, props.label], refresh, { flush: 'post' })
onBeforeUnmount(() => { observer?.disconnect(); chart?.dispose() })
</script>

<template>
  <div v-show="!!option" ref="element" class="chart" :aria-label="label" />
  <p v-if="!option" class="empty-state">暂无数据</p>
</template>
