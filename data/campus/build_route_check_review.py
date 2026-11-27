"""Draw real NetworkService routes for D's local evidence page."""
import json
import sys
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from app.network import NetworkService  # noqa: E402

CAMPUS = ROOT / "data" / "campus"
REVIEW = CAMPUS / "profile-review"
PAIRS = [
    ("M10", "M13", "主校区内"),
    ("E01", "E04", "东校区内"),
    ("M08", "E01", "主校区到东校区"),
    ("E01", "M08", "东校区到主校区"),
]


def load(name):
    return json.loads((REVIEW / name).read_text(encoding="utf-8"))


def panel(service, stations, source, destination, title, width, height, image_file):
    start, end = stations[source], stations[destination]
    route = service.route(source, destination)
    points = route["polyline"]
    line = " ".join(f"{x:.3f},{y:.3f}" for x, y in points)
    left, top = max(0, min(p[0] for p in points)-145), max(0, min(p[1] for p in points)-145)
    right = min(width, max(p[0] for p in points)+145)
    bottom = min(height, max(p[1] for p in points)+145)
    markers = []
    for name, (x,y), color in (("起点",points[0],"#146743"),("终点",points[-1],"#b22e37")):
        markers.append(f'<circle cx="{x}" cy="{y}" r="14" stroke="white" stroke-width="5" fill="{color}"/>'
                       f'<text x="{x+20}" y="{y-17}">{name}</text>')
    distance = route["distance_m"]
    return (f'<section><h2>{title}</h2><p>{source} {escape(start["name"])} → '
            f'{destination} {escape(end["name"])} · {distance:.2f} 米（审阅包边长）</p>'
            f'<svg role="img" aria-label="{title}路线" viewBox="{left} {top} {right-left} {bottom-top}">'
            f'<image href="profile-review/{escape(image_file,quote=True)}" width="{width}" height="{height}"/>'
            f'<polyline class="halo" points="{line}"/><polyline class="route" points="{line}"/>'
            f'{"".join(markers)}</svg></section>')


def build():
    network = load("road_network.json")
    stations = load("default_stations.json")
    metadata = load("metadata.json")
    service = NetworkService(network, stations)
    lookup = {s["id"]:s for s in stations}
    html = ["""<!doctype html>
<html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>校园路网路径自测</title>
<style>
body{max-width:1050px;margin:2rem auto;padding:0 1rem;background:#f3f5ee;color:#22372f;font:16px system-ui,sans-serif}
section{margin:1rem 0;padding:1rem;background:#fff;border:1px solid #d5dfd7;border-radius:8px}
h1,h2{margin:0}svg{width:100%;max-height:620px;background:#e7ede3}
.halo,.route{fill:none;stroke-linejoin:round;stroke-linecap:round}
.halo{stroke:#fff;stroke-width:17}.route{stroke:#006d88;stroke-width:10}
text{font:700 20px system-ui;fill:#22372f;stroke:white;stroke-width:5;paint-order:stroke}
</style>
<h1>校园路网路径自测</h1>
<p>线路来自 NetworkService 的实际返回值。距离使用校园审阅包中的边长。</p>"""]
    for source,destination,title in PAIRS:
        html.append(panel(service,lookup,source,destination,title,network["width"],network["height"],
                          metadata["image_file"]))
        print(f'{source} -> {destination}: {service.route(source,destination)["distance_m"]:.2f} m')
    (CAMPUS/"route-check-review.html").write_text("\n".join(html)+"\n",encoding="utf-8")


if __name__ == "__main__":
    build()
