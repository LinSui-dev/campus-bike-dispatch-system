"""Assemble a D-owned campus review bundle from candidate geometry and approved inputs."""
from __future__ import annotations

import json
from html import escape
from pathlib import Path
from shutil import copyfile

from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "profile-review"
VERSION = "campus-review-v1"

# Rates and peak multipliers are course-model assumptions, in trips per minute.
# Unlisted OD pairs are absent. Time windows are relative to the scenario start.
SCENARIOS = (
    ("morning", "早课", 420, "宿舍流向教学楼，含少量跨校区通勤。", (
        ("M04","M13",.10,0,35,2), ("M04","M16",.08,0,35,2),
        ("M04","M08",.10,0,35,2), ("M04","M10",.09,0,35,2),
        ("M04","M18",.06,0,35,2), ("E01","E04",.12,0,35,2),
        ("E03","E04",.10,0,35,2), ("E01","M16",.05,0,40,2),
        ("E03","M10",.04,0,40,2), ("M04","E04",.035,0,40,1.5),
    )),
    ("lunch", "午餐", 660, "明湖餐厅 M02、留园餐厅 M21 和东区食堂接入点 E01 承接午餐需求，返程在后段增强。", (
        ("M13","M02",.10,10,50,2), ("M16","M02",.10,10,50,2),
        ("M08","M02",.07,10,50,2), ("M10","M21",.08,10,50,2),
        ("M18","M21",.06,10,50,2), ("E04","E01",.12,10,50,2),
        ("M02","M13",.065,60,105,1.7), ("M02","M16",.065,60,105,1.7),
        ("M21","M10",.06,60,105,1.7), ("M21","M18",.05,60,105,1.7), ("E01","E04",.09,60,105,1.7),
        ("E04","M02",.035,10,50,1.5), ("M02","E04",.035,60,105,1.5),
    )),
    ("evening", "返寝", 1230, "教学点流向宿舍，跨校区返程方向与早课对应。", (
        ("M13","M04",.10,25,75,2), ("M16","M04",.08,25,75,2),
        ("M08","M04",.10,25,75,2), ("M10","M04",.09,25,75,2),
        ("M18","M04",.06,25,75,2), ("E04","E01",.12,25,75,2),
        ("E04","E03",.10,25,75,2), ("M16","E01",.05,25,75,2),
        ("M10","E03",.04,25,75,2), ("E04","M04",.035,25,75,1.5),
    )),
    ("offpeak", "平峰", 840, "低强度分散出行，含体育场和跨校区活动。", (
        ("M01","M13",.025), ("M13","M01",.025), ("M06","M16",.025),
        ("M16","M06",.025), ("M20","M08",.03), ("M08","M20",.03),
        ("M04","M10",.03), ("M10","M04",.03), ("M18","M01",.025),
        ("M20","M13",.02), ("M13","M20",.02), ("E01","E04",.03), ("E04","E03",.03), ("E03","E01",.02),
        ("M06","E04",.015), ("E04","M06",.015),
    )),
)

PARAMS = dict(duration_min=120, step_sec=60, ride_speed_kmh=12,
              dispatch_speed_kmh=10, speed=60, horizon_min=30,
              safety_stock=5, max_dispatch=50)


def read(name):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write(name, content):
    (OUT / name).write_text(json.dumps(content, ensure_ascii=False, indent=2)+"\n",
                            encoding="utf-8")


def raster_point(point):
    # SVG centers its 4500×3162.5 content vertically in a 4500×3163 canvas.
    x,y = point
    return [round(x * 2.5, 6), round(y * 2.5 + .25, 6)]


def demand(row):
    start,end,rate,*period = row
    periods = []
    if period:
        first,last,multiplier = period
        periods.append(dict(start_min=first,end_min=last,multiplier=multiplier))
    return dict(origin_id=start,destination_id=end,rate_per_min=rate,periods=periods)


def write_scenario_preview(scenarios, stations):
    names = {s["id"]: s["name"] for s in stations}
    page = ["""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>校园预设场景审阅</title>
<style>
body{max-width:1000px;margin:2rem auto;padding:0 1rem;background:#f3f5ee;color:#263a30;font:16px system-ui,sans-serif}
details,header{background:white;border:1px solid #d1dacd;border-radius:9px;padding:1rem;margin:1rem 0}
h1{margin:0}summary{cursor:pointer;font-weight:700}table{border-collapse:collapse;width:100%}
th,td{padding:.55rem;text-align:left;border-bottom:1px solid #e0e6dc}
</style>
<header><h1>校园预设场景审阅</h1>
<p>需求为课程合成假设。四个预设共用已选站点及统一初始车辆配置。</p>
<a href="map-preview.html?stations">查看站点位置</a></header>"""]
    page.append(f'<p>当前 {len(stations)} 站，初始车辆 {sum(station["initial_stock"] for station in stations)} 辆。</p>')
    for scenario in scenarios:
        start = scenario["start_minute"]
        page.append(f'<details><summary>{scenario["name"]} · {start//60:02}:{start%60:02} · {scenario["duration_min"]} 分钟</summary>')
        page.append(f'<p>{escape(scenario["description"])}</p>')
        page.append("<table><thead><tr><th>起点</th><th>终点</th><th>基础需求（次／分钟）</th><th>场景内峰段</th></tr></thead><tbody>")
        for od in scenario["od_demands"]:
            origin,destination = od["origin_id"],od["destination_id"]
            periods = "、".join(f'{p["start_min"]}–{p["end_min"]} 分钟 ×{p["multiplier"]}'
                               for p in od["periods"]) or "全程基础需求"
            page.append(f'<tr><td>{origin} {escape(names[origin])}</td><td>{destination} {escape(names[destination])}</td>'
                        f'<td>{od["rate_per_min"]}</td><td>{periods}</td></tr>')
        page.append("</tbody></table></details>")
    (ROOT/"scenario-review.html").write_text("\n".join(page)+"\n",encoding="utf-8")


def build():
    source_graph = read("road-graph-review.json")
    lengths = {row["edge_id"]:row["length_estimate_m"]
               for row in read("road-length-review.json")["edges"]}
    selections = read("station-placement-review.json")
    chosen = set(selections["selected_station_ids"])
    inputs = read("profile-inputs.json")

    network = dict(version=VERSION,width=4500,height=3163,synthetic=False,nodes=[],edges=[])
    for node in source_graph["nodes"]:
        x,y = raster_point(node["xy_svg"])
        campus = "connector" if node["area"]=="cross" else node["area"]
        network["nodes"].append(dict(id=node["id"],x=x,y=y,campus=campus))
    for edge in source_graph["edges"]:
        network["edges"].append({
            "id":edge["id"],"from":edge["from_node"],"to":edge["to_node"],
            "length_m":lengths[edge["id"]],"cross_campus":edge["area"]=="cross",
            "polyline":[raster_point(point) for point in edge["polyline_svg"]],
        })
    edges = {edge["id"]:edge for edge in network["edges"]}
    stations = []
    for proposal in selections["stations"]:
        sid = proposal["id"]
        if sid not in chosen:
            continue
        edge_id,offset = proposal["road_edge_id"],proposal["road_offset"]
        x,y = LineString(edges[edge_id]["polyline"]).interpolate(offset,normalized=True).coords[0]
        stations.append(dict(id=sid,name=proposal["landmark"],campus=proposal["campus"],
                             zone=proposal["zone"],x=x,y=y,active=True,
                             road_edge_id=edge_id,road_offset=offset,
                             **inputs["station_defaults"][sid]))

    scenarios = [dict(id=sid,name=name,start_minute=start,duration_min=120,
                      description="课程合成需求。"+description,is_preset=True,
                      od_demands=[demand(row) for row in flows])
                 for sid,name,start,description,flows in SCENARIOS]
    config = dict(id="campus-default",name="校园默认配置",scenario_id="morning",
                  params=PARAMS,seed=42,algorithm="none")
    OUT.mkdir(exist_ok=True)
    copyfile(ROOT / "campus-map.svg", OUT / "campus-map.svg")
    write("road_network.json", network)
    write("default_stations.json", stations)
    write("scenarios.json", scenarios)
    write_scenario_preview(scenarios,stations)
    write("default_config.json", config)
    image_file = "campus_map.png" if (OUT / "campus_map.png").is_file() else "campus-map.svg"
    write("metadata.json", dict(profile="campus",image_file=image_file,
                                width=4500,height=3163,network_version=VERSION,
                                synthetic=False,snap_tolerance_px=40,
                                source="审阅包 · 校方手绘资料、OpenStreetMap 与用户确认"))
    write("review-status.json", dict(status="draft",ready_for_import=False,
                                    reasons=["14 站、11＋3 校区分布待 E 协调",
                                             "其余边长含底图比例估计",
                                             "底图与数据验收待执行"]))
    print(f"Draft generated: {len(stations)} stations, {len(scenarios)} scenarios.")


if __name__ == "__main__":
    build()
