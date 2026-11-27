import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, message } from '../api'
import { defaultParams } from '../domain'
import type { Config, MapInfo, RoadNetwork, RunInput, Scenario, Station } from '../types'

export const useConfig = defineStore('config', () => {
  const map = ref<MapInfo | null>(null)
  const roads = ref<RoadNetwork | null>(null)
  const stations = ref<Station[]>([])
  const scenarios = ref<Scenario[]>([])
  const configs = ref<Config[]>([])
  const issues = ref<string[]>([])
  const draft = ref<RunInput>({ scenario_id: '', params: { ...defaultParams }, seed: 42, algorithm: 'none' })

  async function load() {
    const responses = await Promise.allSettled([
      api.map().then(value => { map.value = value }),
      api.roads().then(value => { roads.value = value }),
      api.stations.list().then(value => { stations.value = value.items }),
      api.scenarios.list().then(value => {
        scenarios.value = value.items
        if (!draft.value.scenario_id && value.items[0]) {
          draft.value.scenario_id = value.items[0].id
          draft.value.params.duration_min = value.items[0].duration_min
        }
      }),
      api.configs.list().then(value => { configs.value = value.items }),
    ])
    const resources = ['底图', '道路', '站点', '场景', '配置']
    issues.value = responses.flatMap((response, index) =>
      response.status === 'rejected' ? [resources[index] + '：' + message(response.reason)] : [])
  }

  const stationName = (id: string) => stations.value.find(station => station.id === id)?.name ?? id
  const scenarioName = (id: string) => scenarios.value.find(scenario => scenario.id === id)?.name ?? id
  return { map, roads, stations, scenarios, configs, issues, draft, load, stationName, scenarioName }
})
