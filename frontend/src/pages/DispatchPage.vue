<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useConfig } from '../stores/config'
import { useRuntime } from '../stores/runtime'
import { algorithmNames, clock, fmt, taskProgress } from '../domain'
import CampusMap from '../components/CampusMap.vue'
const config = useConfig()
const run = useRuntime()
const selected = ref('')
const state = computed(() => run.runtime.mode === 'batch' ? null : run.state)
const params = computed(() => state.value?.context.params ?? config.draft.params)
const name = (id: string) => state.value?.stations.find(station => station.id === id)?.name ?? config.stationName(id)
onMounted(() => run.watchSupply(true))
onUnmounted(() => run.watchSupply(false))
</script>

<template>
  <section class="page-heading"><div><h1>智能调度</h1><p>观察供需估算，在交互运行中手动触发当前策略。</p></div>
    <button class="primary" :disabled="!run.active || run.pending" @click="run.dispatch">手动触发调度</button>
  </section>
  <section class="panel">
    <header class="section-head"><h2>{{ state ? '本次策略' : '待运行策略' }}</h2><a href="#/control">查看运行配置</a></header>
    <dl class="scale-list">
      <div><dt>策略</dt><dd>{{ algorithmNames[state?.algorithm ?? config.draft.algorithm] }}</dd></div>
      <div><dt>预测窗口</dt><dd>{{ params.horizon_min }} 分钟</dd></div>
      <div><dt>安全库存</dt><dd>{{ params.safety_stock }} 辆</dd></div>
      <div><dt>调度上限</dt><dd>{{ params.max_dispatch }} 辆</dd></div>
      <div><dt>运输速度</dt><dd>{{ params.dispatch_speed_kmh }} km/h</dd></div>
    </dl>
  </section>
  <section class="panel">
    <header class="section-head"><div><h2>站点供需</h2>
      <p v-if="state && run.supply">估算时刻 {{ clock(state.context.start_minute, run.supply.now_sec) }} · 有效窗口 {{ fmt(run.supply.horizon_sec / 60) }} 分钟</p></div></header>
    <div v-if="state && run.supply?.stations.length" class="table-scroll">
      <table><thead><tr><th scope="col">站点</th><th scope="col">潜在借车</th><th scope="col">预计借出</th><th scope="col">预计归还</th>
        <th scope="col">目标库存</th><th scope="col">有效库存</th><th scope="col">供给</th><th scope="col">需求</th></tr></thead>
        <tbody><tr v-for="item in run.supply.stations" :key="item.station_id"><th scope="row">{{ name(item.station_id) }}</th>
          <td>{{ fmt(item.expected_borrow) }}</td><td>{{ fmt(item.expected_served_borrow) }}</td><td>{{ fmt(item.expected_return) }}</td>
          <td>{{ item.target }}</td><td>{{ item.effective_stock }}</td><td>{{ item.supply }}</td><td>{{ item.demand }}</td>
        </tr></tbody>
      </table><p class="table-caption">供需和库存以辆为单位，预测需求和归还以辆次为单位。</p>
    </div>
    <p v-else class="empty-state">暂无供需数据</p>
  </section>
  <section class="panel">
    <header class="section-head"><h2>运输任务</h2><button v-if="selected" @click="selected = ''">显示全部运输路线</button></header>
    <div v-if="state?.tasks.length" class="table-scroll">
      <table><thead><tr><th scope="col">路线</th><th scope="col">数量</th><th scope="col">距离</th><th scope="col">出发 / 预计到达</th><th scope="col">运输进度</th></tr></thead>
        <tbody><tr v-for="task in state.tasks" :key="task.id">
          <th scope="row"><button class="text-button" :aria-pressed="selected === task.id" @click="selected = task.id">{{ name(task.source_id) }} → {{ name(task.destination_id) }}</button></th>
          <td>{{ task.quantity }} 辆</td><td>{{ fmt(task.distance_m) }} m</td>
          <td>{{ clock(state.context.start_minute, task.depart_sec) }} / {{ clock(state.context.start_minute, task.arrival_sec) }}</td>
          <td><div class="cell-progress"><progress :value="taskProgress(task, state.sim_time_sec)" max="1" aria-label="运输进度" />
            <span>{{ task.status === 'completed' ? '已到达' : fmt(100 * taskProgress(task, state.sim_time_sec), 0) + '%' }}</span></div></td>
        </tr></tbody>
      </table>
    </div>
    <p v-else class="empty-state">{{ state?.algorithm === 'none' ? '无调度策略不发出运输任务。' : '暂无调度任务' }}</p>
    <div v-if="config.map" class="dispatch-map"><CampusMap :info="config.map" :roads="config.roads"
      :stations="run.currentStations" :tasks="state?.tasks" :time="state?.sim_time_sec" :task-id="selected" /></div>
  </section>
</template>
