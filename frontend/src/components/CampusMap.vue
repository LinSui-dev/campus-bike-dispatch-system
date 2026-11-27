<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import L from 'leaflet'
import type { LayerGroup, Map as LeafletMap, Marker } from 'leaflet'
import { campusNames, fromMap, reserved, routePoint, stationStatus, stock, taskProgress, toMap } from '../domain'
import type { MapInfo, Point, RoadNetwork, Station, StationState, Task } from '../types'

type MapStation = Station | StationState
const props = withDefaults(defineProps<{
  info: MapInfo
  roads: RoadNetwork | null
  stations: MapStation[]
  tasks?: Task[]
  time?: number
  selected?: string
  taskId?: string
  editable?: boolean
  choosing?: boolean
}>(), { tasks: () => [], time: 0 })
const emit = defineEmits<{ select: [id: string]; place: [point: Point]; move: [id: string, point: Point] }>()
const mapElement = ref<HTMLElement>()
const roadsVisible = ref(false)
const failed = ref(false)
let map: LeafletMap
let background: LayerGroup
let roadLayer: LayerGroup
let stationsLayer: LayerGroup
let routes: LayerGroup
let observer: ResizeObserver
let framing = true
const markers = new Map<string, Marker>()
const dragging = new Set<string>()

const latLng = (point: Point) => L.latLng(...toMap(point, props.info.height))
const bounds = () => L.latLngBounds([0, 0], [props.info.height, props.info.width])
function fit() {
  map.setMinZoom(-8)
  map.fitBounds(bounds(), { padding: [10, 10], animate: false })
  map.setMinZoom(map.getZoom() - 1)
  framing = true
}
function showBase() {
  failed.value = false
  background.clearLayers()
  L.imageOverlay(props.info.image_url, bounds(), { alt: props.info.profile === 'fixture' ? '双校区虚拟联调底图' : '校园地图' })
    .on('error', () => { failed.value = true })
    .addTo(background)
  map.setMaxBounds(bounds().pad(0.75))
  fit()
}
function showRoads() {
  roadLayer.clearLayers()
  if (!roadsVisible.value || props.roads?.version !== props.info.network_version) return
  for (const road of props.roads.edges) {
    L.polyline(road.polyline.map(latLng), {
      color: road.cross_campus ? '#225f9e' : '#527589', weight: road.cross_campus ? 5 : 3,
      opacity: 0.82, dashArray: road.cross_campus ? '9 5' : undefined, interactive: false,
    }).addTo(roadLayer)
  }
}
function stationIcon(station: MapStation) {
  const status = stationStatus(station)
  const marker = document.createElement('span')
  marker.className = 'station-marker ' + status.key + (station.id === props.selected ? ' selected' : '')
  marker.textContent = String(stock(station))
  return L.divIcon({ html: marker, className: 'station-pin', iconSize: [32, 32], iconAnchor: [16, 16], tooltipAnchor: [0, -16] })
}
function stationLabel(station: MapStation) {
  return station.name + '，' + stationStatus(station).label + '，库存 ' + stock(station) + ' / ' + station.capacity + ' 辆'
}
function markerLabel(station: MapStation) {
  const element = document.createElement('span')
  element.textContent = stationLabel(station) + '，预留 ' + reserved(station) + ' 辆'
  return element
}
function showStations() {
  const ids = new Set(props.stations.map(station => station.id))
  for (const [id, marker] of markers) {
    if (!ids.has(id)) {
      stationsLayer.removeLayer(marker)
      markers.delete(id)
      dragging.delete(id)
    }
  }
  for (const station of props.stations) {
    if (dragging.has(station.id)) continue
    const location = latLng([station.x, station.y])
    let marker = markers.get(station.id)
    if (!marker) {
      const id = station.id
      marker = L.marker(location, { icon: stationIcon(station), draggable: Boolean(props.editable), keyboard: true })
        .bindTooltip(markerLabel(station)).addTo(stationsLayer)
      marker.on('click', () => emit('select', id))
      marker.on('dragstart', () => dragging.add(id))
      marker.on('dragend', event => {
        const target = event.target as Marker
        const position = target.getLatLng()
        const old = props.stations.find(item => item.id === id)
        dragging.delete(id)
        if (old) target.setLatLng(latLng([old.x, old.y]))
        emit('move', id, fromMap(position.lat, position.lng, props.info.height))
      })
      markers.set(id, marker)
    } else {
      marker.setLatLng(location).setIcon(stationIcon(station)).setTooltipContent(markerLabel(station))
    }
    const element = marker.getElement()
    element?.setAttribute('aria-label', stationLabel(station))
    element?.setAttribute('data-station', station.id)
    marker.setZIndexOffset(station.id === props.selected ? 400 : 100)
    if (props.editable) marker.dragging?.enable()
    else marker.dragging?.disable()
  }
}
function showRoutes() {
  routes.clearLayers()
  for (const task of props.tasks) {
    if (!task.route.length || task.id !== props.taskId && (props.taskId || task.status !== 'transporting')) continue
    L.polyline(task.route.map(latLng), { color: '#734bb4', weight: 5, opacity: 0.88, interactive: false }).addTo(routes)
    const point = routePoint(task.route, taskProgress(task, props.time))
    const dot = L.circleMarker(latLng(point), { radius: 7, weight: 3, color: 'white', fillColor: '#734bb4', fillOpacity: 1 })
    dot.bindTooltip('运输 ' + task.quantity + ' 辆').addTo(routes)
    dot.getElement()?.setAttribute('data-transport', task.id)
  }
}
function focus() {
  const station = props.stations.find(item => item.id === props.selected)
  if (!station) return
  map.panInside(latLng([station.x, station.y]), { animate: false, padding: [40, 40] })
  markers.get(station.id)?.openTooltip()
}
onMounted(() => {
  if (!mapElement.value) return
  map = L.map(mapElement.value, { crs: L.CRS.Simple, minZoom: -8, maxZoom: 4, zoomSnap: 0.25, zoomDelta: 0.5, attributionControl: false })
  background = L.layerGroup().addTo(map)
  roadLayer = L.layerGroup().addTo(map)
  routes = L.layerGroup().addTo(map)
  stationsLayer = L.layerGroup().addTo(map)
  map.on('moveend', () => { framing = false })
  map.on('click', event => {
    if (props.choosing) emit('place', fromMap(event.latlng.lat, event.latlng.lng, props.info.height))
  })
  showBase()
  showRoads()
  showStations()
  showRoutes()
  observer = new ResizeObserver(() => {
    const initial = framing
    map.invalidateSize({ pan: false })
    if (initial) fit()
  })
  observer.observe(mapElement.value)
})
watch(() => props.info, () => { if (map) { showBase(); showRoads(); showStations(); showRoutes() } })
watch([roadsVisible, () => props.roads], () => { if (map) showRoads() })
watch(() => [props.stations, props.editable, props.selected], () => { if (map) showStations() })
watch(() => props.selected, () => { if (map) focus() })
watch(() => [props.tasks, props.time, props.taskId], () => { if (map) showRoutes() })
onBeforeUnmount(() => { observer?.disconnect(); map?.remove() })
</script>

<template>
  <div class="map-frame">
    <div class="map-controls toolbar">
      <label class="check"><input v-model="roadsVisible" type="checkbox" :disabled="!roads || roads.version !== info.network_version" />显示道路</label>
      <button class="compact" @click="fit">全图</button>
    </div>
    <div ref="mapElement" class="campus-map" :class="{ choosing }" aria-label="校园站点地图" />
    <p v-if="failed" class="banner error" role="alert">底图加载失败。</p>
    <div class="map-legend">
      <span><i class="legend-dot normal" />正常</span><span><i class="legend-dot empty" />缺车</span>
      <span><i class="legend-dot full" />满载</span><span><i class="legend-dot inactive" />已停用</span>
      <span v-if="roadsVisible"><i class="legend-line" />跨校区道路</span>
      <span v-if="tasks.length"><i class="legend-dot route" />调度路线</span>
      <span v-if="info.synthetic" class="map-source">{{ info.profile === 'fixture' ? '虚拟联调底图' : '合成数据' }}</span>
    </div>
  </div>
</template>
