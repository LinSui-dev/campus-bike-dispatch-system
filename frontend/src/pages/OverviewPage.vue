<script setup lang="ts">
import { computed, ref } from 'vue'
import { useConfig } from '../stores/config'
import { useRuntime } from '../stores/runtime'
import { campusNames, metricValue, reserved, stationStatus, stock } from '../domain'
import type { Campus, Metrics } from '../types'
import CampusMap from '../components/CampusMap.vue'
import Trend from '../components/Trend.vue'
import MetricList from '../components/MetricList.vue'
const config = useConfig()
const run = useRuntime()
const selected = ref('')
const current = computed(() => run.runtime.mode === 'batch' ? null : run.state)
const selection = computed(() => run.currentStations.find(station => station.id === selected.value))
const cards: { key: keyof Metrics; label: string; unit: string }[] = [
  { key: 'request_count', label: '借车请求', unit: '辆次' },
  { key: 'borrow_success_rate', label: '借车成功率', unit: '%' },
  { key: 'first_return_success_rate', label: '首次还车成功率', unit: '%' },
  { key: 'utilization', label: '车辆利用率', unit: '%' },
]
const totals = computed(() => (Object.keys(campusNames) as Campus[]).map(campus => {
  const stations = run.currentStations.filter(station => station.active && station.campus === campus)
  return {
    campus, count: stations.length,
    stock: stations.reduce((sum, station) => sum + stock(station), 0),
    capacity: stations.reduce((sum, station) => sum + station.capacity, 0),
    reserved: stations.reduce((sum, station) => sum + reserved(station), 0),
    empty: stations.filter(station => !stock(station)).length,
    full: stations.filter(station => station.capacity === stock(station) + reserved(station)).length,
  }
}))
const alerts = computed(() => run.currentStations.filter(station => ['empty', 'full'].includes(stationStatus(station).key)))
</script>

<template>
  <section class="page-heading">
    <h1>运营总览</h1>
    <p>{{ current ? '本次运行的借还表现与站点库存。' : '查看双校区站点分布。开始仿真后查看借还与车辆状态。' }}</p>
  </section>
  <div class="stats-strip" aria-label="运行指标">
    <div v-for="card in cards" :key="card.key">
      <span>{{ card.label }}</span>
      <strong>{{ metricValue(card.key, current?.metrics[card.key]) }}<small v-if="current?.metrics[card.key] != null">{{ card.unit }}</small></strong>
    </div>
  </div>
  <div class="overview-grid">
    <section class="panel map-panel">
      <header class="section-head"><div><h2>双校区站点地图</h2><p>{{ current ? '运行库存' : '初始库存' }} · 点击站点查看详情</p></div></header>
      <CampusMap v-if="config.map" :info="config.map" :roads="config.roads" :stations="run.currentStations"
        :tasks="current?.tasks" :time="current?.sim_time_sec" :selected="selected" @select="selected = $event" />
      <p v-else class="empty-state">暂无地图</p>
      <div v-if="selection" class="map-selection">
        <div><strong>{{ selection.name }}</strong><span>{{ campusNames[selection.campus] }}</span></div>
        <span class="pill" :class="stationStatus(selection).key">{{ stationStatus(selection).label }}</span>
        <span>库存 {{ stock(selection) }} / {{ selection.capacity }} 辆</span>
        <span>预留 {{ reserved(selection) }} 辆</span>
        <button class="text-button" @click="selected = ''">关闭详情</button>
      </div>
    </section>
    <aside class="panel campus-panel">
      <header class="section-head"><div><h2>校区库存</h2><p>{{ current ? '实时库存及预留' : '已启用站点的初始库存' }}</p></div></header>
      <div v-if="run.currentStations.length" class="campus-summary">
        <div v-for="group in totals" :key="group.campus" class="campus-row">
          <div class="row-between"><strong>{{ campusNames[group.campus] }}</strong><span>{{ group.count }} 站</span></div>
          <div class="campus-total">{{ group.stock }} <small>/ {{ group.capacity }} 辆</small></div>
          <progress :value="group.stock + group.reserved" :max="group.capacity || 1" :aria-label="campusNames[group.campus] + '库存和预留占比'" />
          <div class="row-between muted"><span>预留 {{ group.reserved }} 辆</span><span>缺车 {{ group.empty }} · 满载 {{ group.full }}</span></div>
        </div>
      </div>
      <p v-else class="empty-state">暂无数据</p>
      <div class="aside-section">
        <h3>站点预警</h3>
        <p v-if="!alerts.length" class="muted">{{ run.currentStations.length ? '暂无缺车或满载站点' : '暂无数据' }}</p>
        <button v-for="station in alerts" :key="station.id" class="alert-row" @click="selected = station.id">
          {{ station.name }} <span class="pill" :class="stationStatus(station).key">{{ stationStatus(station).label }}</span>
        </button>
      </div>
    </aside>
  </div>
  <div class="overview-grid lower-grid">
    <section class="panel"><header class="section-head"><h2>借还趋势</h2></header>
      <Trend :samples="current ? run.samples : []" :start="current?.context.start_minute ?? 0" />
    </section>
    <section class="panel"><header class="section-head"><h2>车辆状态</h2></header>
      <dl v-if="current" class="vehicle-list">
        <dt>停在站点</dt><dd>{{ current.vehicles.parked }} 辆</dd>
        <dt>骑行中</dt><dd>{{ current.vehicles.riding }} 辆</dd>
        <dt>等待还车</dt><dd>{{ current.vehicles.waiting }} 辆</dd>
        <dt>运输中</dt><dd>{{ current.vehicles.transporting }} 辆</dd>
        <dt>车辆总数</dt><dd>{{ current.vehicles.total }} 辆</dd>
      </dl>
      <p v-else class="empty-state">暂无数据</p>
    </section>
  </div>
  <details v-if="current" class="panel expandable"><summary>全部运行指标</summary><MetricList :metrics="current.metrics" /></details>
</template>
