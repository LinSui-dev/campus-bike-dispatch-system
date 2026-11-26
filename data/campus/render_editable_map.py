"""Generate an editable campus SVG. Layout coordinates use the reference image frame."""
from html import escape
from pathlib import Path
from functools import lru_cache
import re
import json
from math import cos, sin, radians
from itertools import combinations
from xml.etree import ElementTree

from shapely.geometry import MultiPoint, Point, Polygon, LineString
from shapely.ops import substring, unary_union
from shapely.affinity import rotate

# x, y, width, depth, extruded height, category, label.
BUILDINGS = [
    (188, 310, 82, 50, 29, "public", "科技大厦"),
    (215, 402, 77, 46, 22, "sport", "体育馆"),
    (438, 272, 75, 60, 22, "sport", "综合体育馆"),
    (590, 375, 63, 23, 14, "teach", "第二教学楼"),
    (679, 359, 65, 25, 15, "teach", "第一教学楼"),
    (773, 313, 69, 27, 15, "teach", "8号教学楼"),
    (765, 246, 62, 29, 14, "teach", "运输设备教学馆"),
    (861, 236, 66, 16, 10, "dorm", "16号宿舍楼"),
    (892, 309, 64, 23, 12, "dorm", "18号宿舍楼"),
    (880, 268, 40, 31, 10, "public", "明湖餐厅"),
    (921, 284, 23, 16, 8, "public", "益民餐厅"),
    (416, 482, 67, 27, 17, "teach", "17号教学楼"),
    (425, 528, 67, 24, 13, "dorm", "15号宿舍楼"),
    (442, 565, 55, 14, 8, "public", "9号办公楼"),
    (451, 609, 54, 15, 9, "public", "8号办公楼"),
    (466, 692, 62, 19, 13, "dorm", "12号宿舍楼"),
    (454, 649, 72, 30, 18, "teach", "国家经济安全研究院"),
    (485, 750, 65, 35, 24, "dorm", "19号楼"),
    (383, 633, 42, 22, 10, "dorm", "20号楼"),
    (374, 685, 59, 33, 18, "dorm", "22号楼"),
    (285, 525, 36, 82, 17, "public", "知行大厦"),
    (337, 583, 57, 26, 14, "public", "学生活动中心"),
    (599, 463, 85, 54, 42, "teach", "思源楼"),
    (528, 492, 53, 31, 21, "teach", "思源西楼"),
    (705, 467, 73, 40, 25, "teach", "思源东楼"),
    (714, 425, 58, 22, 14, "public", "科学会堂"),
    (858, 390, 78, 44, 25, "public", "主校区图书馆"),
    (735, 521, 72, 29, 16, "teach", "7号教学楼"),
    (815, 533, 26, 29, 12, "teach", "5号教学楼"),
    (530, 573, 76, 24, 19, "public", "校史馆、档案馆"),
    (557, 669, 73, 30, 16, "public", "天佑会堂"),
    (738, 672, 125, 70, 20, "teach", "9号教学楼"),
    (576, 748, 70, 21, 12, "dorm", "2号宿舍楼"),
    (750, 783, 48, 68, 15, "dorm", "嘉园A座"),
    (822, 759, 28, 17, 11, "public", "保卫处"),
    (852, 752, 46, 18, 11, "public", "思源时光"),
    (898, 739, 34, 17, 10, "public", "国际交流合作处"),
    (932, 734, 43, 18, 10, "public", "留学生办公室"),
    (752, 782, 48, 22, 12, "public", "招生办公室"),
    (861, 699, 22, 27, 9, "public", "北京交通大学校友之家"),
    (896, 571, 56, 13, 8, "dorm", "1号宿舍楼"),
    (894, 602, 65, 24, 13, "public", "红果园宾馆"),
    (898, 637, 73, 19, 11, "dorm", "3号宿舍楼"),
    (913, 674, 66, 16, 12, "dorm", "4号宿舍楼"),
    (1010, 654, 16, 37, 9, "public", "留园餐厅"),
    (979, 719, 45, 17, 11, "dorm", "14号宿舍楼"),
    (1022, 712, 39, 14, 9, "public", "第四食堂"),
    (957, 564, 27, 18, 9, "public", "红果园餐厅"),
    (1013, 414, 138, 58, 18, "teach", "逸夫楼"),
    (1109, 491, 87, 58, 20, "teach", "机械与电子控制工程学院"),
    (1030, 536, 76, 49, 16, "teach", "机械试验馆"),
    (1047, 635, 54, 24, 13, "teach", "土木工程实验楼"),
    (1142, 614, 60, 28, 20, "teach", "土木建筑工程学院"),
    (1211, 455, 57, 27, 17, "teach", "工程训练楼"),
    (1254, 492, 36, 38, 20, "teach", "光源楼"),
    (1224, 590, 68, 33, 23, "teach", "隧道中心"),
    (1217, 242, 53, 22, 13, "public", "校医院"),
    (1094, 191, 18, 26, 15, "dorm", ""),
    (1135, 177, 18, 27, 16, "dorm", ""),
    (1121, 249, 18, 28, 15, "dorm", ""),
    (1175, 219, 17, 26, 16, "dorm", ""),
    (1075, 852, 47, 24, 17, "public", "东校区食堂"),
    (1046, 909, 49, 13, 9, "sport", "东校区体育馆"),
    *[(x, y, 57, 8, 6, "dorm", f"东{i}学生宿舍楼") for i, x, y in [
        (5,1087,927),(4,1091,952),(3,1095,968),(2,1100,994),(1,1105,1014)]],
    (1108, 1040, 51, 11, 8, "teach", "东教三楼"),
    (1170, 1028, 90, 14, 13, "teach", "东教二楼"),
    (1178, 1067, 91, 16, 12, "teach", "东教一楼"),
    (1255, 865, 55, 18, 12, "public", "东校区图书馆"),
    (1309, 894, 18, 27, 10, "public", "计算机中心"),
    (1275, 833, 34, 14, 10, "teach", "电力馆"),
    (1265, 935, 58, 12, 8, "dorm", "国际项目学生1号公寓"),
    (1255, 1110, 30, 32, 11, "dorm", "6号学生公寓"),
    (1103, 1108, 61, 19, 10, "public", "国家大学科技园"),
    (800, 829, 76, 31, 15, "dorm", "嘉园B座"),
    (851, 763, 48, 57, 14, "dorm", "嘉园C座"),
    (1025, 463, 73, 64, 16, "teach", "电气工程楼"),
]

PALETTE = {
    "teach": ("#aac2d7", "#6e8ca6", "#91abc1"),
    "dorm": ("#e0ac9b", "#a57871", "#c38d7e"),
    "sport": ("#b0bed1", "#7789a2", "#94a7bc"),
    "public": ("#d1cbbe", "#a29d8c", "#b9b2a2"),
}

# Centerlines digitized in the same image frame as the building anchors.
# Keep paths outside building blocks and preserve actual changes of direction.
CAMPUS_PATHS = [
    "M532 240 544 288 563 347 577 429", "M568 275 725 246 849 220 973 190 1120 154 1267 122", "~M949 239 970 325",
    "~M850 242 889 232 M850 242 876 349", "~M963 330 1325 240",

    "~M230 507 309 491 397 475 507 448 577 429 650 412 734 392 824 369 864 352 911 342 963 330",
    "~M403 561 610 510 651 501 706 489 790 470 842 458 886 449 963 435 997 430 1123 391 1340 337",
    "M540 611 618 591", "~M414 524 518 498 M430 589 531 564 M439 627 541 602 M452 677 553 652", "M727 536 741 532 815 514 883 497",
    "M407 744 485 722 562 710", "~M562 710 653 687", "M357 625 437 605", "~M635.19 663 689 650 725 641 808 620 869 605 1023.16 566.5", "M1026 612 H1088 V595 H1221",
    "~M527 803 582 789.9 662 770.8 722 756.5 867 721.8 1003 689.3",
    "M402 474 412 518 426 560 437 605 453 659 468 722",
    "M498 453 510 502 523 555 540 611 556 662 562 710",
    "~M577 429 635.19 663 662 770.8",
    "~M562 710 582 789.9",
    
    "~M548 653 641 630",
    "~M776 382 798 468",
    "~M733 792 722 756.5 689 650",
    "M686 390 700 498 717 538 735 613 743 636",
    "M846 359 854 415 865 473 883 551 901 621 926 703", "~M883 551 1013 519", "~M935 574 968 566", "~M961 531.8 968 566 982 642.6", "~M921 659 982 642.6 1022 632",
    "~M963 435 994 430 1004 489 1011 514 1017 539 1023.16 566.5 1030 597 1016 649 1003 682",
    "M1168 387 1184 441 1203 507 1215 567 1221 595",
    "~M1190 474 1101 496 1124 587", "~M730 581 768 571 802 562 807 563 815 583 815 589 811 594 737 618 M768 571 777 603 M765 611 772 629 M790 600 797 623",
    "~M776 382 748 270 855 244", "~M430 467 400 337 447 325",
    "~M1041 902 1143.61 876.42 1138 850 1132.27 830.93",
    "~M1138 850 1179.02 1014.50 1221.78 1186.04 1246 1180",
    "M1138 850 1230 827", "M1238 864 1327 848", "M1282 1000 1349 985 1335 923 1327 848",
    "M1238 864 1253 937 1268 1011 1278 1069 1262 1145",
    "M1169 1017 1268 1001",
]

# IDs refer to the source centerline order. Keep the surveyed illustration as
# placement context and show a smaller set of corridors in the project preview.
HIDDEN_ROADS = {2,10,12,15,17,31,38,39,40,45,46,47}
EXTERIOR_REFERENCE_ROADS = {3,6}
MAIN_ROADS = {1,5,6,7,8,15,16,18,19,20,21,22,23,27,28,29,33,34,35,43,44,48,49}
CROSS_CAMPUS = ((733,792),(751,864),(754,876),(995,828),(1001,850),(1014,900),(1041,902))


def route_markup(points):
    coords = " ".join(f"{x},{y}" for x,y in points)
    return ('<g id="cross-campus-route"><title>唯一跨校区路线：主校区南门经上园村路至东校区小西门</title>'
            f'<polyline class="cross-campus-halo" points="{coords}"/>'
            f'<polyline class="cross-campus-line" points="{coords}"/></g>')


def label(x, y, value, kind="place"):
    return f'<text class="{kind}" x="{x}" y="{y}">{escape(value)}</text>'


OSM_OUTLINES = {
    "9号教学楼": [(0,22),(83,0),(97,55),(79,60),(70,24),(21,37),(27,62),(58,53),(62,68),(13,82)],
    "嘉园A座": [(764.9,853.6),(795.7,846.7),(780.7,779.8),(749.9,786.7)],
    "嘉园B座": [(809.4,862.5),(876.2,837.1),(866.6,811.8),(799.7,837.2)],
    "嘉园C座": [(854.4,771),(876,817.5),(898.2,807.3),(876.6,760.8)],
    "逸夫楼": [(1010.8,433.6),(1017.5,464.6),(1153.2,435.2),(1146.5,404.2)],
    "电气工程楼": [(1025.2,499.1),(1030.1,526.2),(1097.4,514),(1086,450.9),
                 (1067.3,454.3),(1073.8,490.3)],
    "机械与电子控制工程学院": [(1109.4,519.4),(1115.5,547.3),(1192.9,530.4),
                           (1186.7,502.5),(1160.5,508),(1164,487.7),
                           (1140.2,485.6),(1116.9,497.5),(1131.2,514.4)],
    "机械试验馆": [(1030.2,540.3),(1042,590),(1106.6,574.6),(1094.7,525)],
}


def corners(x, y, w, depth, name):
    if name in OSM_OUTLINES:
        outline = OSM_OUTLINES[name]
        left, top, right, bottom = Polygon(outline).bounds
        return [(round(x+w*(px-left)/(right-left), 2),
                 round(y+depth*(py-top)/(bottom-top), 2)) for px,py in outline]
    skew = round(depth * 0.32)
    return [(x, y), (x+w, y-8), (x+w+skew, y+depth-8), (x+skew, y+depth)]


def building_geometry(item):
    x, y, w, depth, height, _, name = item
    base = corners(x, y, w, depth, name)
    roof = [(px, py-height) for px, py in base]
    return Polygon(base), MultiPoint(base+roof).convex_hull


def path_subpaths(d):
    """Sample the absolute M/L/Q/Z commands used by the map artwork."""
    tokens = iter(re.findall(r"[A-Za-z]|-?\d+(?:\.\d+)?", d))
    command = None
    points = []
    for token in tokens:
        if token.isalpha():
            command = token
            if command == "Z":
                yield points
                points = []
            continue
        if command in ("H", "V"):
            px, py = points[-1]
            points.append((float(token), py) if command == "H" else (px, float(token)))
            continue
        x, y = float(token), float(next(tokens))
        if command == "M":
            if points:
                yield points
            points = [(x,y)]
            command = "L"
        elif command == "L":
            points.append((x,y))
        elif command == "Q":
            start_x,start_y = points[-1]
            end_x,end_y = float(next(tokens)),float(next(tokens))
            for step in range(1, 41):
                t = step/40
                u = 1-t
                points.append((u*u*start_x+2*u*t*x+t*t*end_x,
                               u*u*start_y+2*u*t*y+t*t*end_y))
        else:
            raise ValueError(f"Unsupported map path command: {command}")
    if points:
        yield points


ROAD_ANGLE = radians(14)


def to_road_axes(x, y):
    c,s = cos(ROAD_ANGLE),sin(ROAD_ANGLE)
    return x*c-y*s, x*s+y*c


def from_road_axes(u, v):
    c,s = cos(ROAD_ANGLE),sin(ROAD_ANGLE)
    return u*c+v*s, -u*s+v*c


def raw_centerlines(paths):
    for path in paths:
        if path.startswith("~"):
            yield from (tuple(points) for points in path_subpaths(path[1:]))
            continue
        for points in path_subpaths(path):
            coords = list(LineString([to_road_axes(*p) for p in points]).simplify(13).coords)
            result = [coords[0]]
            for u,v in coords[1:]:
                pu,pv = result[-1]
                du,dv = u-pu,v-pv
                if abs(du)>=abs(dv):
                    result.append((u,pv))
                    if abs(dv)>=14:
                        result.append((u,v))
                else:
                    result.append((pu,v))
                    if abs(du)>=14:
                        result.append((u,v))
            if len(set(result))>1:
                yield tuple(from_road_axes(*p) for p in result)


@lru_cache(maxsize=1)
def orthogonal_centerlines(paths):
    lines = list(raw_centerlines(paths))
    segments = [LineString(line) for line in lines]
    for index, line in enumerate(lines):
        points = list(line)
        for endpoint, neighbor in ((0,1),(-1,-2)):
            x,y = points[endpoint]
            px,py = points[neighbor]
            length = ((x-px)**2+(y-py)**2)**.5
            if length < 1e-9:
                continue
            dx,dy = (x-px)/length,(y-py)/length
            tip = LineString([(x,y),(x+13*dx,y+13*dy)])
            hits = []
            for other_index, other in enumerate(segments):
                if other_index == index:
                    continue
                touch = tip.intersection(other)
                if touch.geom_type == "Point" and not touch.is_empty:
                    hits.append((touch.distance(tip.boundary.geoms[0]),(touch.x,touch.y)))
            if hits:
                points[endpoint] = min(hits)[1]
        lines[index] = tuple(points)
    for index,line in enumerate(lines):
        points = list(line)
        for endpoint,neighbor in ((0,1),(-1,-2)):
            origin = Point(points[endpoint])
            others = [LineString(p) for i,p in enumerate(lines) if i != index]
            target = min(others,key=origin.distance)
            distance = origin.distance(target)
            if not 0.05 < distance <= 13:
                continue
            touch = target.interpolate(target.project(origin))
            u,v = to_road_axes(origin.x,origin.y)
            tu,tv = to_road_axes(touch.x,touch.y)
            pu,pv = to_road_axes(*points[neighbor])
            bend = from_road_axes(tu,v) if abs(u-pu)>abs(v-pv) else from_road_axes(u,tv)
            extension = [p for p in (bend,(touch.x,touch.y)) if Point(p).distance(origin)>1e-7]
            if endpoint == 0:
                points[0:0] = reversed(extension)
            else:
                points.extend(extension)
        lines[index] = tuple(points)
    return trim_reviewed_road_ends(trim_junction_tails(lines))


def trim_reviewed_road_ends(lines):
    """Trim the user-marked overruns at their actual centerline intersections."""
    roads = [LineString(points) for points in lines]
    for number,crossing,end in ((16,23,"last"),(11,21,"first"),(11,22,"last"),
                                (28,7,"first"),(30,29,"first"),(30,34,"last")):
        line = roads[number-1]
        intersection = line.intersection(roads[crossing-1])
        hits = list(intersection.geoms) if hasattr(intersection,"geoms") else [intersection]
        measures = [line.project(p) for p in hits if p.geom_type=="Point" and not p.is_empty]
        assert measures, (number,crossing)
        if end == "first":
            roads[number-1] = substring(line,max(d for d in measures if d < min(25,line.length/2)),line.length)
        else:
            roads[number-1] = substring(line,0,min(d for d in measures if d > line.length/2))
    return tuple(tuple(line.coords) for line in roads)


def simulation_centerlines():
    """Use campus-side portions only. Gate 6 opens onto background road."""
    for number,points in enumerate(orthogonal_centerlines(tuple(CAMPUS_PATHS)),1):
        if number in HIDDEN_ROADS or number in EXTERIOR_REFERENCE_ROADS:
            continue
        line = LineString(points)
        if number == 1:
            line = substring(line,line.project(Point(568,384)),line.length)
        yield number,tuple(line.coords)


def trim_junction_tails(lines):
    """End short overruns at their crossing while preserving the editable paths."""
    geometry = [LineString(points) for points in lines]
    trimmed = []
    for i,line in enumerate(geometry):
        start,end = 0.,line.length
        crossings = []
        for j,other in enumerate(geometry):
            if i == j:
                continue
            crossing = line.intersection(other)
            hits = crossing.geoms if hasattr(crossing,"geoms") else [crossing]
            crossings.extend(line.project(hit) for hit in hits
                             if hit.geom_type == "Point" and not hit.is_empty)
        for distance in crossings:
            if .05 < distance < 13:
                start = max(start,distance)
            if .05 < line.length-distance < 13:
                end = min(end,distance)
        if any(Point(line.coords[0]).distance(other)<1.5 for j,other in enumerate(geometry) if j!=i):
            start = 0.
        if any(Point(line.coords[-1]).distance(other)<1.5 for j,other in enumerate(geometry) if j!=i):
            end = line.length
        trimmed.append(tuple(substring(line,start,end).coords) if end-start>=15 else tuple(line.coords))
    return tuple(trimmed)


@lru_cache(maxsize=1)
def road_coverage(roads):
    return unary_union([LineString(points).buffer(5.5) for points in orthogonal_centerlines(roads)])


@lru_cache(maxsize=1)
def place_buildings(roads, public_roads):
    blocks = []
    items = []
    offsets = sorted(
        [(dx, dy) for dx in range(-30, 31, 3) for dy in range(-30, 31, 3)
         if dx*dx+dy*dy <= 30**2], key=lambda p: (p[0]**2+p[1]**2, abs(p[1]), p)
    )
    campus_roads = road_coverage(roads)
    road_surface = unary_union([campus_roads, *public_roads])
    clearance = road_surface.buffer(2)
    # Prefer larger/landmark footprints, then retain the nearest valid location.
    for index in sorted(range(len(BUILDINGS)), key=lambda i: -BUILDINGS[i][2]*BUILDINGS[i][3]):
        x, y, width, depth, height, category, name = BUILDINGS[index]
        best = None
        for factor in (1, .92, .84, .76, .68, .60, .52, .44):
            w, d, h = (max(5, round(v*factor)) for v in (width,depth,height))
            for dx, dy in offsets:
                score = dx*dx + dy*dy + 1400*(1-factor)**2
                if best and score >= best[0]:
                    continue
                item = (round(x+(width-w)/2)+dx, round(y+(depth-d)/2)+dy, w,d,h,category,name)
                ground, outline = building_geometry(item)
                if outline.intersects(clearance) or ground.distance(road_surface) > 34:
                    continue
                if any(outline.distance(other) < 2 for other in blocks):
                    continue
                best = score, item, ground, outline
        if best is None:
            raise ValueError(f"No valid footprint near source anchor: {name}, neighbors={[(i[6],i[:4]) for _,i,_,_ in items if abs(i[0]-x)<100 and abs(i[1]-y)<100]}")
        _, item, ground, outline = best
        items.append((index+1, item, ground, outline))
        blocks.append(outline)
    return sorted(items), road_surface


def polygon(coords, color, css=""):
    points = " ".join(f"{x},{y}" for x,y in coords)
    return f'<polygon class="{css}" fill="{color}" points="{points}"/>'


def building(index, item):
    x, y, w, depth, height, category, name = item
    roof_color, front, side = PALETTE[category]
    base = corners(x,y,w,depth,name)
    roof = [(px,py-height) for px,py in base]
    occupants = ' data-occupants="研究生院、软件学院、电气工程学院"' if name == "逸夫楼" else ""
    parts = [f'<g id="building-{index}" data-category="{category}" data-name="{escape(name, quote=True)}"{occupants}>'
             f'<title>{escape(name)}{"（研究生院、软件学院、电气工程学院）" if occupants else ""}</title>', polygon(base, front)]
    for i in range(len(base)):
        j = (i+1)%len(base)
        color = front if base[j][0]<base[i][0] else side
        parts.append(polygon([base[i],base[j],roof[j],roof[i]], color, "wall"))
    parts.extend([polygon(roof, roof_color, "roof"), "</g>"])
    return "".join(parts)


def building_label(item):
    x,y,w,depth,height,_,name = item
    if not name:
        return ""
    kind = "place small-label"
    return label(x+w/2+depth*.16,y+depth/2-height+1,name,kind)


def track(x, y, w, h, angle, name, color):
    return (
        f'<g data-name="{name}" transform="translate({x} {y}) rotate({angle})">'
        f'<rect x="{-w/2}" y="{-h/2}" width="{w}" height="{h}" rx="{min(w,h)/2}" fill="{color}"/>'
        + "".join(
            f'<rect x="{-w/2+i}" y="{-h/2+i}" width="{w-2*i}" height="{h-2*i}" '
            f'rx="{min(w,h)/2-i}" fill="none" stroke="#efe1cb"/>'
            for i in (4, 8)
        )
        + f'<rect x="{14-w/2}" y="{14-h/2}" width="{w-28}" height="{h-28}" rx="9" fill="#829e73" stroke="#e0e9cc"/>'
        + f'<circle r="9" fill="none" stroke="#e0e9cc"/>'
        + f'</g>{label(x,y+4,name)}'
    )


def court(corners, x, y, name):
    outline = Polygon(corners)
    center = outline.centroid
    inset = [(center.x+(px-center.x)*.92, center.y+(py-center.y)*.85)
             for px,py in corners]
    a,b,c,d = inset
    markings = []
    for ratio in (.25,.5,.75):
        start = (a[0]+(b[0]-a[0])*ratio,a[1]+(b[1]-a[1])*ratio)
        end = (d[0]+(c[0]-d[0])*ratio,d[1]+(c[1]-d[1])*ratio)
        markings.append(f'<line x1="{start[0]}" y1="{start[1]}" x2="{end[0]}" y2="{end[1]}" stroke="#f3e9d5"/>')
    return (f'<g data-name="{escape(name)}">{polygon(corners,"#af8075")}'
            f'{polygon(inset,"#9aaa79","court-lines")}{"".join(markings)}</g>'
            f'{label(x,y,name,"place small-label")}')


def gate(x,y,angle,name):
    return (f'<g data-name="{escape(name)}">'
            f'<g transform="translate({x} {y}) rotate({angle})" class="gate-structure">'
            '<path d="M-18 5V-6H18V5H13V-1H-13V5Z" fill="#a45f50" stroke="#735245"/>'
            '<path d="M-18 -6-15 -9H20L18 -6Z" fill="#dba08b" stroke="#735245"/>'
            '<path d="M18 -6 20 -9V3L18 5Z" fill="#784a42"/>'
            '</g>'+(label(x,y+19,name,"gate") if name else '')+'</g>')


TRACKS = [
    (344,362,102,167,-13,"主校区体育场","#8da9bc"),
    (1069,351,113,64,-14,"主校区第二体育场","#b87773"),
    (1197,901,71,98,-12,"东校区田径场","#b87773"),
]
COURTS = [
    ([(430,368),(549,344),(564,400),(443,430)],498,389,"综合体育馆南侧运动场"),
    ([(583,716),(632,705),(644,742),(591,754)],614,732,"2号宿舍楼北侧运动场"),
    ([(1178,974),(1245,957),(1252,982),(1185,999)],1211,980,"东校区球场"),
]
GATES = [(246.6,502.9,76,"西门"),(963,330,76,"东小门"),
         (1306,345,76,"东门"),(1041,902,76,"东校区小西门"),
         (1218,1174,-14,"东校区南门"),(568,384,-14,"")]


def check_map_geometry():
    roads = [LineString(p) for p in orthogonal_centerlines(tuple(CAMPUS_PATHS))]
    surface = road_coverage(tuple(CAMPUS_PATHS))
    areas = [(name,Polygon(points)) for points,_,_,name in COURTS]
    for x,y,w,h,angle,name,_ in TRACKS:
        outline = Polygon([(x-w/2,y-h/2),(x+w/2,y-h/2),(x+w/2,y+h/2),(x-w/2,y+h/2)])
        areas.append((name,rotate(outline,angle,origin=(x,y))))
    for name,area in areas:
        assert area.intersection(surface).area < .01, f"Road overlaps sports area: {name}"
    visible = [road for i,road in enumerate(roads,1) if i not in HIDDEN_ROADS]
    for a,b in ((4,5),(13,21),(13,22),(24,16),(24,20),(18,34),
                (32,30),(32,33),(33,29),(36,35),(36,19)):
        assert not {a,b} & HIDDEN_ROADS
        assert roads[a-1].distance(roads[b-1]) < .01, f"Road {a} does not meet {b}"
    for through,point in ((18,(689,650)),(20,(722,756.5))):
        assert point in roads[26].coords and point in roads[through-1].coords
    assert (635.19,663) in roads[22].coords and (635.19,663) in roads[17].coords
    assert (662,770.8) in roads[22].coords and (662,770.8) in roads[19].coords
    assert (1138,850) in roads[42].coords and (1138,850) in roads[43].coords
    assert min(road.distance(Point(CROSS_CAMPUS[0])) for road in visible) < 1.5
    assert min(road.distance(Point(CROSS_CAMPUS[-1])) for road in visible) < 1.5
    u0,v0 = to_road_axes(*CROSS_CAMPUS[0])
    u1,v1 = to_road_axes(*CROSS_CAMPUS[1])
    u2,_ = to_road_axes(*CROSS_CAMPUS[3])
    assert abs(u1-u0) < 3 and v1-v0 > 50 and u2-u1 > 200
    for x,y,_,name in [*GATES,(733,792,-14,"主校区南门")]:
        assert min(p.distance(Point(x,y)) for p in visible) < 1.5, f"Gate is off-road: {name}"
    for i,line in enumerate(roads):
        for tip in line.boundary.geoms:
            distance = min(tip.distance(other) for j,other in enumerate(roads) if i!=j)
            assert distance <= 5.5 or distance > 13, f"Near but unjoined road endpoint: {i+1}"
    print(f"Checked {len(areas)} sports areas, {len(GATES)+1} gates and {len(roads)} road paths.")


@lru_cache(maxsize=1)
def reviewed_road_lines():
    path = Path(__file__).with_name("road-graph-review.json")
    if not path.exists():
        return None
    graph = json.loads(path.read_text(encoding="utf-8"))
    if not graph.get("nonexistent_edges"):
        return None
    groups = {}
    for edge in graph["edges"]:
        if edge["area"] == "cross":
            continue
        assert edge["svg_roads"], edge["id"]
        number = min(edge["svg_roads"])
        groups.setdefault(number,[]).append(edge["polyline_svg"])
    return groups


def road_path_data(lines):
    return " ".join("M" + " ".join(f"{x:.2f},{y:.2f}" for x,y in points) for points in lines)


def render(show_small_labels=False):
    parts = ['''<svg xmlns="http://www.w3.org/2000/svg" width="4500" height="3163" viewBox="0 0 1800 1265" role="img" aria-labelledby="map-title">
<title id="map-title">北京交通大学主校区与东校区 2.5D 底图</title>
<style>
text{font-family:"Microsoft YaHei","Noto Sans CJK SC",sans-serif;text-anchor:middle;fill:#243a32;paint-order:stroke;stroke:#f2f4e5;stroke-linejoin:round;stroke-width:3px}
.place{font-size:13px}.district{font-size:24px;font-weight:bold}.street{font-size:19px;fill:#815b40}.gate{font-size:15px;font-weight:bold}.note{font-size:15px}
.small-label{display:none}.show-small .small-label{display:inline}.wall{stroke:#63766e;stroke-width:.6}.court-lines{stroke:#efe0c9;stroke-width:1.1}.roof{stroke:#63766e;stroke-width:.8}.campus-road{fill:none;stroke:#f5f0e1;stroke-width:7;stroke-linejoin:round;stroke-linecap:round}
.campus-road.main-road{stroke-width:11}.road-reference{stroke:#d2d5cf;stroke-width:9}
.cross-campus-halo,.cross-campus-line{fill:none;stroke-linecap:round;stroke-linejoin:round}
.cross-campus-halo{stroke:#faf8ee;stroke-width:14}.cross-campus-line{stroke:#007c76;stroke-width:8}
</style>
<rect width="1800" height="1265" fill="#dce8ce"/>
<g id="functional-areas">
 <path id="main-campus" fill="#bcd3aa" d="M162 294 547 224 557 267 1269 82 1328 376 1410 726 775 850 750 786 702 798 727 856 491 884 299 704 234 573 206 505Z"/>
 <path id="east-campus" fill="#bcd3aa" d="M1008 842 1421 764 1517 1201 1183 1181 1066 1124Z"/>
 <path id="housing-background" fill="#c8dbb9" d="M574 230 1194 68 1304 125 567 272Z"/>
 <path id="xueyuan-background" fill="#c8dbb9" d="M1323 105 1454 77 1474 203 1548 204 1550 311 1520 323 1545 428 1432 471 1383 350 1347 306Z"/>
 <path id="central-campus-green" fill="#a9c99a" d="M615 515 707 494 726 571 744 634 652 655Z"/>
 <g id="xuehuokeng"><ellipse cx="371" cy="503" rx="29" ry="18" fill="#91a783" stroke="#647968" stroke-width="3"/><path d="M344 505Q365 479 397 500M351 508Q371 488 390 503" fill="none" stroke="#d6d8b8" stroke-width="2"/></g>
 <g id="jixiuyuan"><path d="M543 615 619 596 630 629 551 648Z" fill="#9bb78b"/><path d="M557 637Q575 612 599 621L613 611" fill="none" stroke="#f0e8cf" stroke-width="4"/><path d="M561 623l6-8 7 6-5 5zM590 627l7-7 6 5-5 5z" fill="#858c7b"/></g>
 <g id="south-gate-east-grounds">
  <path id="south-gate-paved-strip" d="M700 666 852 628 879 713 723 754Z" fill="#dfe5dc"/>
  <path id="ninth-teaching-entrance" d="M780 734 811 725 803 700" fill="none" stroke="#becbc5" stroke-width="5"/>
 </g>
 <g id="south-grove"><path d="M647 680 677 670 690 683 706 737 702 749 671 758 658 748 642 694Z" fill="#95b385"/><path d="M655 689 676 746M667 685 691 741" stroke="#6e956b" stroke-width="6" stroke-dasharray="4 7" stroke-linecap="round"/></g>
 <g id="fanghuayuan"><path d="M865 454 991 429 1014 516 890 547Z" fill="#9fb98d"/><path d="M868 527Q895 495 923 504T942 530Q924 550 902 527T872 520" fill="none" stroke="#f4ecd9" stroke-width="3"/></g>
 <path id="minghu" fill="#9abfc8" d="M786 392Q826 382 850 413L851 449Q822 471 795 455Z"/>
</g>
<g id="public-roads" fill="#e3e4df" stroke="#b5b8af" stroke-width="2">
 <path id="gaoliangqiao" d="M110 0H158Q152 249 219 463Q268 645 491 884L467 928Q303 789 245 680Q115 438 110 0Z"/>
 <path id="jiaotong-university-road" d="M440 885Q517 883 727 856L702 798 750 786 775 850 1410 726 1800 635V677L1458 758 1008 843 755 891 489 928Z"/>
 <path id="shangyuancun" d="M985 846 1008 843 1066 1124 1041 1151Z"/>
 <path id="jiaoda-east-road" d="M1244 0H1290L1361 330 1424 479 1600 1265H1540L1458 901 1408 708 1337 402 1293 294Z"/>
 <path id="south-perimeter" d="M0 784Q240 895 433 881L486 910Q744 1144 1184 1180Q1478 1210 1800 1200V1241Q1474 1254 1176 1234Q712 1185 447 930Q215 921 0 832Z"/>
 <path id="gaoliangqiao-south-leg" d="M718 890 751 886 774 1074 738 1055Z"/>
</g>
<g id="campus-roads">''']
    for i,points in enumerate(orthogonal_centerlines(tuple(CAMPUS_PATHS)),1):
        if i in HIDDEN_ROADS:
            continue
        d = "M" + " ".join(f"{x:.2f},{y:.2f}" for x,y in points)
        classes = "campus-road main-road" if i in MAIN_ROADS else "campus-road"
        if i in EXTERIOR_REFERENCE_ROADS:
            classes = "campus-road road-reference"
        elif i==1:
            line = LineString(points)
            outside = substring(line,0,line.project(Point(568,384)))
            inside = substring(line,line.project(Point(568,384)),line.length)
            outside_d = " ".join(f"{x:.2f},{y:.2f}" for x,y in outside.coords)
            d = "M" + " ".join(f"{x:.2f},{y:.2f}" for x,y in inside.coords)
            parts.append(f'<path class="campus-road road-reference" d="M{outside_d}"/>')
        reviewed = reviewed_road_lines()
        if reviewed is not None and i not in EXTERIOR_REFERENCE_ROADS:
            if i not in reviewed:
                continue
            d = road_path_data(reviewed[i])
        parts.append(f'<path id="campus-road-{i}" class="{classes}" d="{d}"/>')
    reviewed = reviewed_road_lines()
    if reviewed and 50 in reviewed:
        parts.append(f'<path id="campus-road-50" class="campus-road main-road" d="{road_path_data(reviewed[50])}"/>')
    parts.append(route_markup(CROSS_CAMPUS))
    parts.append('</g><g id="sports-grounds">')
    parts.extend(track(*item) for item in TRACKS)
    parts.extend(court(*item) for item in COURTS)
    parts.append('</g><g id="building-layer">')
    header = parts[0].split('<g id="campus-roads">')[0] + "</svg>"
    if show_small_labels:
        parts[0] = parts[0].replace("<svg ", '<svg class="show-small" ', 1)
    root = ElementTree.fromstring(header)
    public = root.find("{*}g[@id='public-roads']")
    public_shapes = []
    for node in public:
        for subpath in path_subpaths(node.get("d")):
            area = Polygon(subpath).buffer(0)
            public_shapes.append(area.buffer(1))
    placed, road_surface = place_buildings(tuple(CAMPUS_PATHS), tuple(public_shapes))
    assert all(a.distance(b)>=2 for (_,_,_,a),(_,_,_,b) in combinations(placed,2))
    assert all(outline.distance(road_surface)>=2 and ground.distance(road_surface)<=34
               for _,_,ground,outline in placed)
    crossing = LineString(CROSS_CAMPUS)
    assert all(crossing.buffer(4).intersection(outline).area < .01 for _,_,_,outline in placed)
    print(f"Checked {len(placed)} buildings against roads and {len(placed)*(len(placed)-1)//2} building pairs.")
    parts += [building(i, item) for i,item,_,_ in placed]
    parts += ['</g><g id="building-labels">']
    parts += [building_label(item) for _,item,_,_ in placed]
    parts += ['</g><g id="gates">']
    for item in GATES:
        parts.append(gate(*item))
    parts.append('<g data-name="主校区南门" transform="translate(733 792) rotate(-14)">'
                 '<path d="M-24 8V-1Q-24-22 0-24Q24-22 24-1V8H18V0Q18-14 0-15Q-18-14-18 0V8Z" fill="#ae6058" stroke="#743e39" stroke-width="2"/>'
                 '<path d="M-23-7Q0-30 23-7" fill="none" stroke="#e6a49a" stroke-width="2"/>'
                 '</g>')
    parts.append('<g id="century-clock" transform="translate(780 609)"><title>世纪钟</title><circle r="5" fill="#c0a078" stroke="#786346"/><path d="M0 -3V0L2 1" stroke="#604b36" fill="none"/></g><g id="south-gate-emblem" transform="translate(700 631)"><title>校徽装饰</title>'
                 '<circle r="12" fill="#ede8d7" stroke="#a78e66" stroke-width="2"/>'
                 '<circle r="8" fill="#8d4540"/><path d="M-4 2H4M-3-1L0-4 3-1M0-4V4" fill="none" stroke="#fff3d8"/></g>')
    parts += ['</g><g id="map-labels">']
    for x,y,name,kind in [
        (403,120,"北京交通大学 · 双校区 2.5D 底图","district"),
        (789,179,"家属区","district"),(1458,178,"学苑公寓","district"),
        (1217,722,"主校区","district"),(1360,820,"东校区","district"),
        (1084,801,"交通大学路","street"),(1465,533,"交大东路","street"),
        (361,776,"高粱桥斜街","street"),(1030,988,"上园村路","street"),
        (733,821,"主校区南门","gate"),
        (372,507,"学活坑","place"),(585,623,"积秀园","place"),(674,570,"劳动花园","place"),
        (786,603,"世纪钟","place small-label"),(673,718,"南门小树林","place"),(931,488,"芳华园","place"),(821,434,"明湖","place"),(1452,1015,"北","district"),
        (381,1115,"青绿色线 · 唯一跨校区路线（走法已确认，长度待核验）","note"),
        (381,1139,"依据校方手绘图及 © OpenStreetMap contributors 概化。","note"),
    ]:
        parts.append(label(x,y,name,kind))
    parts.append('<path d="M1460 1068 1451 1031m-5 12 5-12 10 8" fill="none" stroke="#34584b" stroke-width="3"/></g></svg>')
    return "\n".join(parts) + "\n"


def render_road_numbers():
    """Render the visible SVG road IDs in the same viewBox as the base map."""
    parts = ['<svg xmlns="http://www.w3.org/2000/svg" width="4500" height="3163" viewBox="0 0 1800 1265">']
    labels = []
    for number,points in enumerate(orthogonal_centerlines(tuple(CAMPUS_PATHS)),1):
        if number in HIDDEN_ROADS:
            continue
        reviewed = reviewed_road_lines()
        if reviewed is not None and number not in EXTERIOR_REFERENCE_ROADS:
            if number not in reviewed:
                continue
            line = max((LineString(s) for s in reviewed[number]),key=lambda p:p.length)
        else:
            line = LineString(points)
        color = {1:"#b85013",2:"#b85013",43:"#8b327d",44:"#8b327d"}.get(number,"#273e34")
        if number in {1,2,43,44}:
            coords = " ".join(f"{x:.2f},{y:.2f}" for x,y in points)
            parts.append(f'<polyline points="{coords}" fill="none" stroke="{color}" '
                         'stroke-width="6" stroke-linejoin="round" stroke-linecap="round"/>')
        marker = line.interpolate(.5,normalized=True)
        labels.append(f'<g id="road-number-{number}" transform="translate({marker.x:.2f} {marker.y:.2f})">'
                      f'<rect x="-13" y="-10" width="26" height="20" rx="6" fill="{color}" stroke="#fff" stroke-width="1.5"/>'
                      f'<text y="5" text-anchor="middle" font-family="sans-serif" font-size="13" '
                      f'font-weight="700" fill="white">{number}</text></g>')
    reviewed = reviewed_road_lines()
    if reviewed and 50 in reviewed:
        marker = LineString(reviewed[50][0]).interpolate(.5,normalized=True)
        labels.append(f'<g id="road-number-50" transform="translate({marker.x:.2f} {marker.y:.2f})">'
                      '<rect x="-13" y="-10" width="26" height="20" rx="6" fill="#273e34" stroke="#fff"/>'
                      '<text y="5" text-anchor="middle" font-family="sans-serif" font-size="13" '
                      'font-weight="700" fill="white">50</text></g>')
    return "\n".join([*parts,*labels,"</svg>"]) + "\n"


if __name__ == "__main__":
    check_map_geometry()
    Path(__file__).with_name("campus-map.svg").write_text(render(), encoding="utf-8")
    Path(__file__).with_name("campus-map-labels.svg").write_text(render(True), encoding="utf-8")
    Path(__file__).with_name("campus-road-numbers.svg").write_text(render_road_numbers(), encoding="utf-8")
