"""Estimate draft indoor-road lengths from a supplied OSM XML snapshot."""
import argparse
import json
from hashlib import sha256
from collections import Counter
from math import atan2, cos, degrees, hypot, radians
from pathlib import Path
from statistics import mean
from xml.etree import ElementTree as ET

from shapely.geometry import LineString, Polygon
from shapely.ops import substring

ROOT = Path(__file__).resolve().parent
OSM_URL = "https://api.openstreetmap.org/api/0.6/map?bbox=116.328,39.9435,116.344,39.9545"
ROAD_TYPES = {"residential", "service", "unclassified", "living_street",
              "cycleway", "pedestrian", "footway", "path", "tertiary", "secondary"}
CONTROLS = {
    "main": {
        "思源楼": "276199049", "思源西楼": "276199074", "思源东楼": "276198909",
        "科学会堂": "276199032", "主校区图书馆": "188600671",
        "9号教学楼": "276202113", "8号教学楼": "276198844",
        "运输设备教学馆": "287663142", "天佑会堂": "276201140",
        "20号楼": "287662861", "22号楼": "287662019",
    },
    "east": {
        "东校区食堂": "265006297", "东校区体育馆": "265006298",
        "东5学生宿舍楼": "421408341", "东3学生宿舍楼": "421408345",
        "东1学生宿舍楼": "421408349", "东教二楼": "421408351",
        "东教一楼": "421408356",
    },
}
# Only attempt matched sections along individually reviewed, named public data.
ROAD_REFERENCES = {8: ("60110798", "60110831"), 27: ("266509131",),
                   34: ("60110704",), 20: ("526224706",)}


def local_m(lon, lat):
    return ((lon-116.335)*111195*cos(radians(39.95)), (39.95-lat)*111195)


def fit_similarity(pairs):
    sx = mean(p[0] for p,_ in pairs)
    sy = mean(p[1] for p,_ in pairs)
    tx = mean(p[0] for _,p in pairs)
    ty = mean(p[1] for _,p in pairs)
    offsets = [(x-sx,y-sy,X-tx,Y-ty) for (x,y),(X,Y) in pairs]
    den = sum(x*x+y*y for x,y,_,_ in offsets)
    a = sum(x*X+y*Y for x,y,X,Y in offsets)/den
    b = sum(x*Y-y*X for x,y,X,Y in offsets)/den

    def project(x,y):
        return (tx+a*(x-sx)-b*(y-sy),ty+b*(x-sx)+a*(y-sy))

    return project, hypot(a,b), degrees(atan2(b,a))


def estimate(snapshot):
    root = ET.parse(snapshot).getroot()
    raw_nodes = {n.get("id"):local_m(float(n.get("lon")),float(n.get("lat")))
                 for n in root.findall("node")}
    ways = {e.get("id"):e for e in root.findall("way")}

    def coords(way):
        return [raw_nodes[n.get("ref")] for n in ways[way].findall("nd")]

    buildings = {e.get("data-name"):e for e in ET.parse(ROOT/"campus-map.svg").iter()
                 if e.get("data-category")}
    matching = {}
    for area, controls in CONTROLS.items():
        pairs = []
        for title,way in controls.items():
            roof = buildings[title][-1].get("points")
            svg = Polygon([tuple(map(float,p.split(","))) for p in roof.split()]).centroid
            osm = Polygon(coords(way)).centroid
            pairs.append(((svg.x,svg.y),(osm.x,osm.y)))
        project,scale,angle = fit_similarity(pairs)
        errors = []
        for i, (svg,osm) in enumerate(pairs):
            leave_one_out,_,_ = fit_similarity(pairs[:i]+pairs[i+1:])
            x,y = leave_one_out(*svg)
            errors.append(hypot(x-osm[0],y-osm[1]))
        matching[area] = (project, dict(
            meters_per_svg_unit=round(scale,4),rotation_deg=round(angle,2),
            control_ways=controls,loo_mean_error_m=round(mean(errors),1),
            loo_max_error_m=round(max(errors),1)))

    reference = {}
    for way,element in ways.items():
        tags = {t.get("k"):t.get("v") for t in element.findall("tag")}
        if tags.get("highway") not in ROAD_TYPES or tags.get("area")=="yes":
            continue
        if tags.get("access") in {"no","private"} or tags.get("bicycle") in {"no","dismount"}:
            continue
        points = coords(way)
        if len(points)>=2:
            ref = LineString(points)
            if ref.length:
                reference[way] = ref,tags
    graph = json.loads((ROOT/"road-graph-review.json").read_text(encoding="utf-8"))
    cross_edges = [edge for edge in graph["edges"] if edge["area"]=="cross"]
    confirmed_cross = ["E133","E134","E135","E136","E137","E138"]
    assert [edge["id"] for edge in cross_edges] == confirmed_cross
    svg_gate_span = LineString([cross_edges[0]["polyline_svg"][0],
                               cross_edges[-1]["polyline_svg"][-1]]).length
    gate_nodes = ["5117734220","5229699412"]
    osm_gate_span = LineString([raw_nodes[node] for node in gate_nodes]).length
    cross_scale = osm_gate_span/svg_gate_span
    inputs = json.loads((ROOT/"profile-inputs.json").read_text(encoding="utf-8"))
    user_lengths = inputs["confirmed_edge_lengths_m"]
    cross_total_m = inputs["confirmed_cross_campus_total_m"]
    cross_pixels = [LineString(edge["polyline_svg"]).length for edge in cross_edges]
    cross_cents = round(cross_total_m * 100)
    cumulative_pixels = 0.0
    assigned_cents = 0
    cross_lengths = {}
    for edge,pixels in zip(cross_edges,cross_pixels):
        cumulative_pixels += pixels
        through_cents = round(cross_cents * (cumulative_pixels / sum(cross_pixels)))
        cross_lengths[edge["id"]] = (through_cents-assigned_cents)/100
        assigned_cents = through_cents
    records = []
    totals = Counter()
    for edge in graph["edges"]:
        area = edge["area"]
        result = dict(edge_id=edge["id"],area=area,length_estimate_m=None,method="pending_location")
        if edge["id"] in user_lengths:
            result.update(method="user_confirmed_edge_length",length_estimate_m=user_lengths[edge["id"]])
        elif edge["id"] in cross_lengths:
            result.update(method="user_confirmed_total_allocated_by_polyline",
                          length_estimate_m=cross_lengths[edge["id"]])
        elif area in matching:
            project,_ = matching[area]
            line = LineString([project(*p) for p in edge["polyline_svg"]])
            result["svg_scale_estimate_m"] = round(line.length,2)
            if line.length < 1:
                result["method"] = "short_geometry_only"
            else:
                result["method"] = "unmatched_online"
            candidates = []
            if line.length >= 5:
                preferred = {way for road in edge["svg_roads"] for way in ROAD_REFERENCES.get(road,())}
                samples = [line.interpolate(t,normalized=True) for t in (0,.125,.25,.375,.5,.625,.75,.875,1)]
                for way,(ref,tags) in reference.items():
                    if any(ref.distance(point)>8 for point in samples):
                        continue
                    offsets = [ref.project(point) for point in samples]
                    distance = abs(offsets[-1]-offsets[0])
                    monotone = offsets==sorted(offsets) or offsets==sorted(offsets,reverse=True)
                    if not monotone or not .8*line.length<=distance<=1.2*line.length:
                        continue
                    segment = substring(ref,min(offsets[0],offsets[-1]),max(offsets[0],offsets[-1]))
                    if segment.hausdorff_distance(line)>8:
                        continue
                    gap = max(ref.distance(point) for point in samples)
                    score = gap - (1 if way in preferred else 0)
                    candidates.append((score,gap,way,distance,segment,tags))
            candidates.sort(key=lambda item:(item[0],item[2]))
            if candidates:
                _,gap,way,distance,segment,tags = candidates[0]
                ambiguous = any(other[0]-candidates[0][0]<2 and
                                segment.hausdorff_distance(other[4])>2 for other in candidates[1:])
                if ambiguous:
                    result["method"] = "ambiguous_online_match"
                else:
                    result.update(length_estimate_m=round(distance,2),method="osm_matched_section",
                                  osm_way=way,osm_highway=tags["highway"],osm_name=tags.get("name"),
                                  max_sample_distance_m=round(gap,1),
                                  osm_start_local_m=[round(x,2) for x in segment.coords[0]],
                                  osm_end_local_m=[round(x,2) for x in segment.coords[-1]])
        if result["length_estimate_m"] is None and edge.get("existence")=="user_confirmed":
            assert area in matching and result["svg_scale_estimate_m"] > 0
            result.update(length_estimate_m=result["svg_scale_estimate_m"],
                          method="confirmed_road_svg_scale")
        records.append(result)
        totals[result["method"]] += 1
    out = dict(status="review_estimates",osm_source=OSM_URL,
               osm_snapshot_sha256=sha256(snapshot.read_bytes()).hexdigest(),
               attribution="© OpenStreetMap contributors",calibration={area:stats for area,(_,stats) in matching.items()},
               cross_calibration=dict(method="two_gate_svg_similarity_scale",osm_gate_nodes=gate_nodes,
                                      meters_per_svg_unit=round(cross_scale,4),
                                      osm_gate_chord_m=round(osm_gate_span,2),
                                      user_confirmed_edge_ids=confirmed_cross,
                                      user_confirmed_total_m=cross_total_m,
                                      allocation_method="proportional_svg_polyline_length_rounded_cumulative"),
               edges=records)
    (ROOT/"road-length-review.json").write_text(json.dumps(out,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    graph_edges = {edge["id"]:edge for edge in graph["edges"]}
    review = []
    for item in records:
        length = item["length_estimate_m"]
        if length is None:
            edge = graph_edges[item["edge_id"]]
            x,y = LineString(edge["polyline_svg"]).interpolate(.5,normalized=True).coords[0]
            review.append(dict(id=item["edge_id"],x=round(x,2),y=round(y,2),length=item.get("svg_scale_estimate_m"),method=item["method"],
                               roads=edge["svg_roads"],points=edge["polyline_svg"]))
    (ROOT/"road-review-items.js").write_text(
        "window.roadReviewItems = "+json.dumps(review,ensure_ascii=False)+";\n",encoding="utf-8")
    print(dict(totals))
    print(json.dumps(out["calibration"],ensure_ascii=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("snapshot",type=Path)
    estimate(parser.parse_args().snapshot)
