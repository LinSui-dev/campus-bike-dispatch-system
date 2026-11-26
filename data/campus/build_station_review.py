"""Create proposed campus station access points on the reviewed road geometry."""
import json
from html import escape
from pathlib import Path

from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parent
# The coordinates are proposed access locations in the map, reviewed by zone.
# Road IDs are fixed explicitly to avoid snapping to a nearby unrelated corridor.
PROPOSALS = [
    ("M01","main","体育","主校区体育场", 401,400, (42,)),
    ("M02","main","宿舍","16号宿舍楼", 898,239, (4,)),
    ("M03","main","食堂","明湖餐厅", 868,277, (5,)),
    ("M04","main","宿舍","18号宿舍楼", 910,330, (7,)),
    ("M05","main","教学","8号教学楼", 813,355, (7,)),
    ("M06","main","体育","主校区第二体育场", 1019,401, (8,)),
    ("M07","main","图书馆","主校区图书馆", 937,445, (8,)),
    ("M08","main","教学","5号教学楼", 815,565, (37,)),
    ("M09","main","教学","机械试验馆", 1129,572, (19,36)),
    ("M10","main","教学","9号教学楼", 736,711, (27,)),
    ("M11","main","宿舍","3号宿舍楼", 943,623, (29,33)),
    ("M12","main","食堂","留园餐厅", 999,658, (33,34)),
    ("M13","main","教学","思源西楼", 568,530, (8,)),
    ("M14","main","教学","思源楼西侧", 616,498, (8,)),
    ("M15","main","教学","思源楼东侧", 692,481, (8,28)),
    ("M16","main","教学","思源东楼", 756,494, (8,)),
    ("M17","main","办公","9号办公楼", 439,571, (21,)),
    ("M18","main","教学","国家经济安全研究院", 462,664, (13,21)),
    ("M19","main","宿舍","12号宿舍楼", 537,679, (22,)),
    ("E01","east","宿舍","东5学生宿舍楼北侧", 1119,905, (43,)),
    ("E02","east","宿舍","东4学生宿舍楼北侧", 1120,938, (44,)),
    ("E03","east","宿舍","东2学生宿舍楼北侧", 1128,978, (44,)),
    ("E04","east","教学","东教三楼南侧", 1165,1064, (44,)),
]


SELECTED_IDS = ("E01","E03","E04","M10","M06","M02","M04","M01","M13","M16","M08","M18")


def build():
    graph = json.loads((ROOT/"road-graph-review.json").read_text(encoding="utf-8"))
    assert len({n["component"] for n in graph["nodes"]}) == 1
    stations = []
    for sid,campus,zone,name,x,y,roads in PROPOSALS:
        target = Point(x,y)
        candidates = []
        for edge in graph["edges"]:
            if edge["area"] != campus or not set(roads).intersection(edge["svg_roads"]):
                continue
            line = LineString(edge["polyline_svg"])
            candidates.append((line.distance(target),edge["id"],line))
        gap,edge_id,line = min(candidates,key=lambda p:(p[0],p[1]))
        offset = line.project(target,normalized=True)
        if gap > (48 if campus=="east" else 35) or not 0 <= offset <= 1:
            raise ValueError(f"{sid} needs a nearby access point: {edge_id}, gap={gap:.2f}")
        access = line.interpolate(offset,normalized=True)
        stations.append(dict(id=sid,campus=campus,zone=zone,landmark=name,
                             selection_source="user_screenshot",selected=sid in SELECTED_IDS,
                             marked_xy_svg=[x,y],
                             xy_svg=[round(access.x,4),round(access.y,4)],
                             road_edge_id=edge_id,road_offset=round(offset,8),
                             preferred_svg_roads=list(roads)))
    assert len({tuple(s["xy_svg"]) for s in stations}) == len(stations)
    return stations


def draw(stations):
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="4500" height="3163" viewBox="0 0 1800 1265">']
    for station in stations:
        x,y = station["xy_svg"]
        sid = station["id"]
        title = escape(f'{sid} {station["landmark"]} · {station["road_edge_id"]}')
        color = "#164d79" if station["campus"]=="main" else "#773a8c"
        if station["selection_source"] == "user_screenshot":
            mx,my = station["marked_xy_svg"]
            parts.append(f'<g fill="none" stroke="{color}" stroke-width="1.5">'
                         f'<path d="M{mx} {my}L{x} {y}" stroke-dasharray="3 2"/>'
                         f'<circle cx="{mx}" cy="{my}" r="3.5"/></g>')
        parts.append(f'<g id="station-{sid}" transform="translate({x} {y})"><title>{title}</title>'
                     f'<circle r="6" fill="{color}" stroke="white" stroke-width="2"/>'
                     f'<path d="M0 -6V-13" stroke="{color}" stroke-width="2"/>'
                     f'<rect x="-17" y="-32" width="34" height="20" rx="5" fill="{color}" stroke="white"/>'
                     f'<text y="-18" fill="white" text-anchor="middle" font-family="sans-serif" '
                     f'font-size="12" font-weight="700">{sid}</text></g>')
    return "\n".join([*parts,"</svg>"])+"\n"


if __name__=="__main__":
    stations = build()
    by_id = {s["id"]:s for s in stations}
    assert len(set(SELECTED_IDS)) == 12 and set(SELECTED_IDS) <= by_id.keys()
    selected = [by_id[sid] for sid in SELECTED_IDS]
    (ROOT/"station-placement-review.json").write_text(
        json.dumps({"status":"proposal","coordinate_system":"SVG viewBox 1800×1265",
                    "selected_station_ids":SELECTED_IDS,"stations":stations},ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    (ROOT/"station-review-items.js").write_text(
        "window.stationReviewItems = "+json.dumps(selected,ensure_ascii=False)+";\n",encoding="utf-8")
    (ROOT/"campus-station-proposals.svg").write_text(draw(selected),encoding="utf-8")
    print([(s["id"],s["road_edge_id"],s["xy_svg"]) for s in stations])
