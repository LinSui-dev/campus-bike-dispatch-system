import json
import runpy
from collections import defaultdict, Counter
from pathlib import Path

from shapely import set_precision, union_all
from shapely.geometry import LineString, Point
from shapely.ops import substring


root = Path(__file__).resolve().parent
m = runpy.run_path(str(root / "render_editable_map.py"))
sources = {"main": {}, "east": {}}
for i, points in m["simulation_centerlines"]():
    campus = "east" if points[0][1] >= 810 and points[0][0] > 1000 else "main"
    sources[campus][i] = set_precision(LineString(points), .01)

nodes = {}
edges = []
def add(campus, points, source_ids):
    a, b = points[0], points[-1]
    if a == b:
        return
    for p in (a,b):
        if (campus,p) not in nodes:
            nodes[campus,p] = f"N{len(nodes)+1:03}"
    edges.append(dict(id=f"E{len(edges)+1:03}", area=campus,
                      from_node=nodes[campus,a], to_node=nodes[campus,b],
                      polyline_svg=points, length_m=None, svg_roads=source_ids))

def point(xy):
    return tuple(round(v,2) for v in xy)

for campus, lines in sources.items():
    # Node exact drawn intersections. Nearby endpoints remain separate for review.
    noded = union_all(list(lines.values()), grid_size=.01)
    segments = sorted(noded.geoms if hasattr(noded,"geoms") else [noded],
                      key=lambda g: tuple(g.bounds))
    for seg in segments:
        coords = [point(p) for p in seg.coords]
        ids = [i for i,line in lines.items() if line.distance(seg.interpolate(.5,normalized=True)) <= .011]
        if coords[0] == coords[-1]:
            mid=len(coords)//2
            add(campus,coords[:mid+1],ids)
            add(campus,coords[mid:],ids)
        else:
            add(campus,coords,ids)

cross = [point(p) for p in m["CROSS_CAMPUS"]]
assert ("main",cross[0]) in nodes and ("east",cross[-1]) in nodes
nodes["cross",cross[0]] = nodes["main",cross[0]]
nodes["cross",cross[-1]] = nodes["east",cross[-1]]
for start,end in zip(cross,cross[1:]):
    add("cross",[start,end],[])

labels = {cross[0]:"主校区南门",cross[-1]:"东校区小西门",
          cross[2]:"南门外转向东（走法已确认）",cross[4]:"上园村路接入（走法已确认）"}
# User confirmed these IDs are duplicated junction points, not traversable edges.
point_edges = {
    "E009","E012","E023","E027","E037","E057","E060","E065","E068","E069",
    "E070","E071","E072","E081","E104","E106","E109","E111","E114","E121",
}
overlap_junction_edges = {"E031","E075","E076","E077","E080"}
duplicate_edges = {"E024","E123"}
nonexistent_edges = {"E039"}
drop_edges = point_edges | overlap_junction_edges | duplicate_edges | nonexistent_edges
assert drop_edges <= {e["id"] for e in edges}
selected = [e for e in edges if e["id"] in point_edges | overlap_junction_edges]
coordinates = {nid:xy for (_,xy),nid in nodes.items()}
fixed = {nodes["main",cross[0]],nodes["east",cross[-1]]}
parents = {nid:nid for nid in coordinates}


def representative(nid):
    while nid != parents[nid]:
        nid = parents[nid]
    return nid


for e in selected:
    limit = 1.2 if e["id"] in point_edges else 8
    assert e["area"] != "cross" and LineString(e["polyline_svg"]).length < limit, e["id"]
    a,b = (representative(e[k]) for k in ("from_node","to_node"))
    keep,drop = sorted((a,b),key=lambda n:(n not in fixed,n))
    assert drop not in fixed or drop == keep
    parents[drop] = keep

reconnected = []
collapsed_retraces = []
for e in edges:
    if e["id"] in drop_edges:
        continue
    a,b = (representative(e[k]) for k in ("from_node","to_node"))
    if a == b:
        shape = e["polyline_svg"]
        pivot = max(range(1,len(shape)-1),key=lambda i:Point(shape[i]).distance(Point(shape[0])))
        assert LineString(shape).length < 16, e["id"]
        assert LineString(shape[:pivot+1]).hausdorff_distance(LineString(shape[pivot:])) < 1, e["id"]
        collapsed_retraces.append(e["id"])
        continue
    e.update(existence="user_confirmed",from_node=a,to_node=b,
             polyline_svg=[coordinates[a],*e["polyline_svg"][1:-1],coordinates[b]])
    reconnected.append(e)
edges = reconnected
assert all(LineString(e["polyline_svg"]).length > 0 for e in edges)
# User marked a connection east of the main library. Split the two
# existing roads in place, keeping their IDs on the first half.
def split_for_connection(edge_id, anchor, suffix_id):
    edge = next(e for e in edges if e["id"]==edge_id)
    line = LineString(edge["polyline_svg"])
    along = line.project(Point(anchor))
    assert 0 < along < line.length and line.distance(Point(anchor)) < 2, edge_id
    before = [point(xy) for xy in substring(line,0,along).coords]
    after = [point(xy) for xy in substring(line,along,line.length).coords]
    joint = before[-1]
    assert joint == after[0]
    nid = f"N{max(int(n[1:]) for n in nodes.values())+1:03}"
    nodes[edge["area"],joint] = nid
    edges.append(dict(edge,id=suffix_id,from_node=nid,polyline_svg=after))
    edge.update(to_node=nid,polyline_svg=before)
    return nid,joint


start_id,start_xy = split_for_connection("E084",(940,336),"E155")
end_id,end_xy = split_for_connection("E097",(970,434),"E156")
edges.append(dict(id="E157",area="main",from_node=start_id,to_node=end_id,
                  polyline_svg=[start_xy,end_xy],length_m=None,svg_roads=[50],
                  existence="user_confirmed",label="主校区图书馆东侧连接"))
adj = defaultdict(set)
for e in edges:
    a,b=e["from_node"],e["to_node"]
    adj[a].add(b)
    adj[b].add(a)
todo=set(adj)
components=[]
while todo:
    queue=[min(todo)]
    seen=set()
    while queue:
        n=queue.pop()
        if n in seen:
            continue
        seen.add(n)
        queue.extend(adj[n]-seen)
    components.append(seen)
    todo-=seen
components.sort(key=lambda group:(-len(group),min(group)))
index={n:i for i,c in enumerate(components,1) for n in c}
payload_nodes=[]
for (area,xy),nid in nodes.items():
    if (area=="cross" and xy in (cross[0],cross[-1])) or nid not in index:
        continue
    payload_nodes.append(dict(id=nid,area=area,xy_svg=xy,component=index[nid],name=labels.get(xy)))
payload=dict(status="draft",coordinate_system="SVG viewBox 1800×1265; no metric scale",
             rules="Undirected candidate edges. Exact drawn crossings are candidates for turn confirmation. Lengths and access unverified.",
             collapsed_point_edges=sorted(point_edges),collapsed_retraces=collapsed_retraces,
             collapsed_overlap_edges=sorted(overlap_junction_edges),
             duplicate_edges={"E024":"E022","E123":"E124"},
             nonexistent_edges=sorted(nonexistent_edges),
             nodes=payload_nodes,edges=edges)
(root/"road-graph-review.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
print("Roads", {k:len(v) for k,v in sources.items()},"nodes",len(payload_nodes),"edges",Counter(e["area"] for e in edges))
for i,c in enumerate(components,1):
    print("component",i,"nodes",len(c),"road ids",sorted({n for e in edges if e["from_node"] in c for n in e["svg_roads"]}))
print("gates",[(labels[p],nodes[k,p],index[nodes[k,p]]) for k,p in (("main",cross[0]),("east",cross[-1]))])
print("cross edges", [(e["id"],e["polyline_svg"]) for e in edges if e["area"]=="cross"])
