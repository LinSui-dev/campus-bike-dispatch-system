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

def minute(hour, minute=0):
    return 60 * hour + minute


# Synthetic rates are trips per minute while a window is active.
# M06 is an existing access point on the road south of the library.
SCENARIOS = (
    ("morning", "早课", ((minute(7,30),minute(8)),),
     "宿舍到教学楼，含双向跨校区上课和少量图书馆自习。", (
        ("M04","M13",.20), ("M04","M16",.16), ("M04","M08",.17),
        ("M04","M10",.18), ("M04","M18",.11), ("M04","E04",.09),
        ("E01","E04",.24), ("E03","E04",.20), ("E01","M16",.10),
        ("E03","M10",.08), ("M04","M06",.04), ("E03","M06",.025),
    )),
    ("morning-dismissal", "上午下课", ((minute(9,50),minute(10,10)),(minute(10,30),minute(10,50))),
     "教学楼到宿舍、教学楼之间换课，并有少量流向图书馆。", (
        ("M13","M04",.15), ("M16","M04",.12), ("M08","M04",.12),
        ("M10","E03",.07), ("M16","E01",.06), ("E04","M04",.06),
        ("E04","E01",.14), ("E04","E03",.12), ("M13","M08",.10),
        ("M10","M16",.10), ("M18","M10",.07), ("M08","M06",.04),
        ("M13","M06",.04), ("E04","M06",.025),
    )),
    ("lunch", "午餐", ((minute(11,30),minute(12,50)),),
     "教学楼和宿舍流向明湖餐厅、留园餐厅和东区食堂接入点。", (
        ("M13","M02",.12), ("M16","M02",.12), ("M08","M02",.08),
        ("M04","M02",.08), ("M10","M21",.12), ("M18","M21",.09),
        ("M04","M21",.05), ("E04","E01",.18), ("E03","E01",.12),
        ("M06","M02",.04), ("M06","M21",.04), ("E04","M02",.025),
    )),
    ("afternoon-class", "午课", ((minute(13,30),minute(14,10)),),
     "宿舍到教学楼、教学楼之间换课，含双向跨校区和图书馆出行。", (
        ("M04","M13",.15), ("M04","M10",.14), ("M04","M08",.12),
        ("M04","E04",.07), ("E01","E04",.19), ("E03","E04",.17),
        ("E01","M16",.08), ("E03","M18",.07), ("M13","M10",.08),
        ("M08","M16",.07), ("M10","M06",.04), ("M06","M18",.035),
    )),
    ("afternoon-dismissal", "下午下课", ((minute(16),minute(16,20)),),
     "教学楼到宿舍、教学楼之间换课，并有少量图书馆出行。", (
        ("M13","M04",.17), ("M10","M04",.15), ("M08","M04",.12),
        ("M16","E01",.09), ("M18","E03",.08), ("E04","M04",.07),
        ("E04","E01",.18), ("E04","E03",.15), ("M13","M16",.09),
        ("M08","M10",.08), ("M16","M06",.045), ("M18","M06",.04),
    )),
    ("dinner", "晚餐", ((minute(17),minute(17,30)),(minute(18,10),minute(18,30))),
     "教学楼和宿舍流向三个就餐接入点。", (
        ("M13","M02",.12), ("M16","M02",.10), ("M08","M02",.09),
        ("M04","M02",.09), ("M10","M21",.12), ("M18","M21",.10),
        ("M04","M21",.07), ("E04","E01",.17), ("E03","E01",.12),
        ("M06","M02",.04), ("M06","M21",.04),
    )),
    ("evening-class", "晚课", ((minute(18,30),minute(19)),),
     "餐厅和宿舍到教学楼，含双向跨校区通学和少量自习。", (
        ("M02","M13",.12), ("M02","M16",.10), ("M21","M10",.13),
        ("M21","M18",.10), ("M04","M08",.11), ("M04","E04",.06),
        ("E01","E04",.18), ("E03","E04",.14), ("E01","M16",.07),
        ("E03","M10",.06), ("M02","M06",.045), ("M21","M06",.035),
    )),
    ("evening", "返寝", ((minute(20,50),minute(21,10)),(minute(21,50),minute(22,10))),
     "教学区和图书馆流向宿舍，含双向跨校区返寝。", (
        ("M13","M04",.18), ("M16","M04",.16), ("M08","M04",.14),
        ("M10","M04",.15), ("M18","M04",.10), ("E04","E01",.20),
        ("E04","E03",.17), ("M16","E01",.09), ("M10","E03",.08),
        ("E04","M04",.07), ("M06","M04",.065), ("M06","E03",.035),
    )),
)

PARAMS = dict( step_sec=60, ride_speed_kmh=12,
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


def scenario_draft(item):
    sid, name, windows, description, flows = item
    start = windows[0][0]
    gaps = [
        dict(start_min=before_end-start, end_min=after_start-start, multiplier=0)
        for (_,before_end),(after_start,_) in zip(windows,windows[1:])
    ]
    return dict(id=sid,name=name,start_minute=start,duration_min=windows[-1][1]-start,
                description="课程合成需求。"+description,is_preset=True,
                od_demands=[dict(origin_id=origin,destination_id=destination,
                                 rate_per_min=rate,periods=gaps)
                            for origin,destination,rate in flows])


def hhmm(value):
    return f"{value//60:02}:{value%60:02}"


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
<p>需求为课程合成假设。正式实验采用以下八个独立场景，共用已选站点及统一初始车辆配置。各自从默认库存开始，窗口间继续处理已发生的行程。</p>
<a href="map-preview.html?stations">查看站点位置</a></header>"""]
    page.append(f'<p>当前 {len(stations)} 站，初始车辆 {sum(station["initial_stock"] for station in stations)} 辆。</p>')
    for scenario,(_,_,windows,_,_) in zip(scenarios,SCENARIOS):
        active = "、".join(f"{hhmm(first)}–{hhmm(last)}" for first,last in windows)
        page.append(f'<details><summary>{scenario["name"]} · {active}</summary>')
        page.append(f'<p>{escape(scenario["description"])}</p>')
        page.append("<table><thead><tr><th>起点</th><th>终点</th><th>窗口内需求（次／分钟）</th></tr></thead><tbody>")
        for od in scenario["od_demands"]:
            origin,destination = od["origin_id"],od["destination_id"]
            page.append(f'<tr><td>{origin} {escape(names[origin])}</td><td>{destination} {escape(names[destination])}</td>'
                        f'<td>{od["rate_per_min"]}</td></tr>')
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

    scenarios = [scenario_draft(s) for s in SCENARIOS]
    config = dict(id="campus-default",name="校园默认配置",scenario_id="morning",
                  params=dict(duration_min=scenarios[0]["duration_min"],**PARAMS),
                  seed=42,algorithm="none")
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
                                             "用户确认正式实验采用 8 组，公共批次和验收口径待 E 同步",
                                             "其余边长含底图比例估计",
                                             "底图与数据验收待执行"]))
    print(f"Draft generated: {len(stations)} stations, {len(scenarios)} scenarios.")


if __name__ == "__main__":
    build()
