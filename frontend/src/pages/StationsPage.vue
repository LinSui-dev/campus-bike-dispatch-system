<script setup lang="ts">
import { computed, ref } from 'vue'
import { api, ApiError, message } from '../api'
import { campusNames, stationError, stationStatus } from '../domain'
import { useConfig } from '../stores/config'
import { useRuntime } from '../stores/runtime'
import type { Campus, Point, Station, StationCreate, StationPatch } from '../types'
import CampusMap from '../components/CampusMap.vue'
import Modal from '../components/Modal.vue'

const config = useConfig()
const run = useRuntime()
const campus = ref<Campus | ''>('')
const selected = ref('')
const draft = ref<StationCreate | null>(null)
const choosing = ref(false)
const editMode = ref(false)
const itemToDelete = ref<Station | null>(null)
const related = ref(false)
const saving = ref(false)
const error = ref('')
const notice = ref('')
const locked = computed(() => run.busy || run.pending || saving.value)
const filtered = computed(() => config.stations.filter(station => !campus.value || station.campus === campus.value))
const current = computed(() => config.stations.find(station => station.id === selected.value))

async function change(work: () => Promise<void>) {
  if (locked.value) return
  saving.value = true
  error.value = notice.value = ''
  try { await work() } catch (failure) { error.value = message(failure) }
  finally { saving.value = false }
}
function update(station: Station) {
  const exists = config.stations.some(item => item.id === station.id)
  config.stations = exists ? config.stations.map(item => item.id === station.id ? station : item) : [...config.stations, station]
  selected.value = station.id
  if (campus.value && campus.value !== station.campus) campus.value = station.campus
  notice.value = '已保存 ' + station.name + '，道路标准坐标（' + station.x.toFixed(1) + '，' + station.y.toFixed(1) + '）。'
}
function open(station?: Station, point?: Point) {
  error.value = ''
  editMode.value = Boolean(station)
  draft.value = station ? {
    id: station.id, name: station.name, campus: station.campus, zone: station.zone, x: station.x, y: station.y,
    capacity: station.capacity, initial_stock: station.initial_stock, active: station.active,
  } : {
    id: crypto.randomUUID(), name: '', campus: campus.value || 'main', zone: '',
    x: point?.[0] ?? 0, y: point?.[1] ?? 0, capacity: 20, initial_stock: 10, active: true,
  }
}
function place(point: Point) {
  if (locked.value) return
  choosing.value = false
  open(undefined, point)
}
function save() {
  if (!draft.value || locked.value) return
  const input = { ...draft.value, name: draft.value.name.trim(), zone: draft.value.zone.trim() }
  error.value = stationError(input, config.map)
  if (error.value) return
  void change(async () => {
    const { id, ...fields } = input
    update(editMode.value ? await api.stations.update(id, fields) : await api.stations.create(input))
    draft.value = null
  })
}
function move(id: string, [x, y]: Point) {
  selected.value = id
  const patch: StationPatch = { x, y }
  void change(async () => { update(await api.stations.update(id, patch)) })
}
function openDelete(station: Station) {
  error.value = ''
  itemToDelete.value = station
  related.value = config.scenarios.some(scenario => scenario.od_demands.some(od => od.origin_id === station.id || od.destination_id === station.id))
}
function deleteStation() {
  const station = itemToDelete.value
  if (!station) return
  void change(async () => {
    try {
      await api.stations.remove(station.id, '?clear_related_od=' + related.value)
      config.stations = config.stations.filter(item => item.id !== station.id)
      if (related.value) config.scenarios = (await api.scenarios.list()).items
      if (selected.value === station.id) selected.value = ''
      itemToDelete.value = null
      notice.value = '已删除 ' + station.name + '。'
    } catch (failure) {
      if (failure instanceof ApiError && failure.code === 'RELATED_OD') related.value = true
      throw failure
    }
  })
}
</script>

<template>
  <section class="page-heading">
    <div><h1>停车点管理</h1><p>配置初始容量与库存。可在地图上拖动站点，保存时由道路服务校准位置。</p></div>
    <div class="toolbar"><button :disabled="locked || !config.map" @click="choosing = !choosing">{{ choosing ? '取消地图选址' : '在地图上选址' }}</button>
      <button class="primary" :disabled="locked || !config.map" @click="open()">新增停车点</button></div>
  </section>
  <p v-if="run.busy" class="banner warning">运行槽不可编辑，空闲后可修改停车点。</p>
  <p v-if="choosing" class="banner" role="status">在地图上点击新站点位置，再填写站点信息。</p>
  <p v-if="error && !draft && !itemToDelete" class="banner error" role="alert">{{ error }}</p>
  <p v-if="notice" class="banner" role="status">{{ notice }}</p>
  <div class="management-grid">
    <section class="panel map-panel">
      <header class="section-head"><h2>停车点分布</h2></header>
      <CampusMap v-if="config.map" :info="config.map" :roads="config.roads" :stations="filtered"
        :selected="selected" :choosing="choosing && !locked" :editable="!locked && !choosing"
        @select="selected = $event" @place="place" @move="move" />
      <p v-else class="empty-state">暂无地图</p>
      <div v-if="current" class="map-selection">
        <strong>{{ current.name }}</strong><span>{{ campusNames[current.campus] }}</span>
        <span class="pill" :class="stationStatus(current).key">{{ stationStatus(current).label }}</span>
        <span>初始 {{ current.initial_stock }} / {{ current.capacity }} 辆</span>
        <button :disabled="locked" @click="open(current)">编辑</button>
      </div>
    </section>
    <section class="panel">
      <header class="section-head"><h2>停车点列表 <small>{{ filtered.length }}</small></h2>
        <select v-model="campus" aria-label="筛选校区" @change="selected = ''">
          <option value="">全部校区</option>
          <option v-for="(label, value) in campusNames" :key="value" :value="value">{{ label }}</option>
        </select>
      </header>
      <div v-if="filtered.length" class="station-list">
        <article v-for="station in filtered" :key="station.id" :class="{ 'selected-row': selected === station.id }">
          <button class="station-select" :aria-pressed="selected === station.id" @click="selected = station.id">
            <strong>{{ station.name }}</strong><span>{{ campusNames[station.campus] }} · {{ station.initial_stock }} / {{ station.capacity }} 辆</span>
          </button>
          <span class="pill" :class="stationStatus(station).key">{{ stationStatus(station).label }}</span>
          <button class="text-button" :disabled="locked" :aria-label="'编辑 ' + station.name" @click="open(station)">编辑</button>
          <button class="text-button danger" :disabled="locked" :aria-label="'删除 ' + station.name" @click="openDelete(station)">删除</button>
        </article>
      </div>
      <p v-else class="empty-state">暂无停车点</p>
    </section>
  </div>
  <Modal v-if="draft" :title="editMode ? '编辑停车点' : '新增停车点'" :locked="saving" @close="draft = null">
    <form novalidate @submit.prevent="save">
      <fieldset :disabled="locked" class="fields fields-2">
        <label class="field">站点名称<input v-model="draft.name" maxlength="128" required /></label>
        <label class="field">区域<input v-model="draft.zone" maxlength="128" required /></label>
        <label class="field">校区<select v-model="draft.campus"><option v-for="(label, value) in campusNames" :key="value" :value="value">{{ label }}</option></select></label>
        <label class="check"><input v-model="draft.active" type="checkbox" />启用站点</label>
        <label class="field">X（像素）<input v-model.number="draft.x" type="number" min="0" step="any" /></label>
        <label class="field">Y（像素）<input v-model.number="draft.y" type="number" min="0" step="any" /></label>
        <label class="field">容量（辆）<input v-model.number="draft.capacity" type="number" min="1" step="1" /></label>
        <label class="field">初始库存（辆）<input v-model.number="draft.initial_stock" type="number" min="0" step="1" /></label>
      </fieldset>
      <p v-if="error" class="banner error" role="alert">{{ error }}</p>
      <footer class="toolbar dialog-actions"><button type="button" :disabled="saving" @click="draft = null">取消</button>
        <button class="primary" :disabled="locked">{{ saving ? '正在保存…' : '保存停车点' }}</button></footer>
    </form>
  </Modal>
  <Modal v-if="itemToDelete" :title="'删除 ' + itemToDelete.name + '？'" :locked="saving" @close="itemToDelete = null">
    <p>{{ related ? '该站点关联了 OD 需求。确认后同时清除关联的 OD。' : '删除后，该站点将从当前配置中移除。' }}</p>
    <p v-if="error" class="banner error" role="alert">{{ error }}</p>
    <footer class="toolbar dialog-actions"><button :disabled="saving" @click="itemToDelete = null">取消</button>
      <button class="danger filled" :disabled="locked" @click="deleteStation">{{ related ? '删除站点及关联 OD' : '删除停车点' }}</button></footer>
  </Modal>
</template>
