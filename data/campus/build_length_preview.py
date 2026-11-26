"""Generate static browser data for comparing the source of each edge length."""
import json
from pathlib import Path

from shapely.geometry import LineString

ROOT = Path(__file__).resolve().parent


def build():
    graph = json.loads((ROOT / "road-graph-review.json").read_text(encoding="utf-8"))
    lengths = json.loads((ROOT / "road-length-review.json").read_text(encoding="utf-8"))
    by_id = {entry["edge_id"]: entry for entry in lengths["edges"]}
    items = []
    for edge in graph["edges"]:
        origin = by_id[edge["id"]]
        points = edge["polyline_svg"]
        center = LineString(points).interpolate(.5, normalized=True)
        items.append(dict(id=edge["id"], length=origin["length_estimate_m"],
                          method=origin["method"], osm=origin.get("osm_way"),
                          x=round(center.x, 2), y=round(center.y, 2), points=points))
    (ROOT / "road-length-preview.js").write_text(
        "window.roadLengthPreview = " + json.dumps(items, ensure_ascii=False) + ";\n",
        encoding="utf-8",
    )
    print(f"Prepared length legend and shapes for {len(items)} edges.")


if __name__ == "__main__":
    build()
