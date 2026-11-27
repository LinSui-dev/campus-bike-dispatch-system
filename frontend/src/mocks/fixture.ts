import mapImage from '../../../data/fixtures/campus_map.svg?url'
import metadata from '../../../data/fixtures/metadata.json'
import roadFixture from '../../../data/fixtures/road_network.json'
import stationFixture from '../../../data/fixtures/default_stations.json'
import scenarioFixture from '../../../data/fixtures/scenarios.json'
import configFixture from '../../../data/fixtures/default_config.json'
import stateExample from '../../../contracts/examples/state.json'
import type { Config, MapInfo, RoadNetwork, Scenario, State, Station } from '../types'

export const map: MapInfo = {
  profile: metadata.profile, width: metadata.width, height: metadata.height, synthetic: metadata.synthetic,
  network_version: metadata.network_version, snap_tolerance_px: metadata.snap_tolerance_px, image_url: mapImage,
}
export const roads = roadFixture as RoadNetwork
export const stations = stationFixture as Station[]
export const scenarios: Scenario[] = scenarioFixture
export const config = configFixture as Config
export const emptyMetrics = (stateExample as State).metrics
