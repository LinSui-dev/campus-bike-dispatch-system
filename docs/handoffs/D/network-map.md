# 成员 D 地图路网与数据交接

## 1 身份与范围

- 成员 D，地图路网与数据。状态 draft。首批路网服务已通过本地自测，可供 A/B 接入并由 E 复验。校园数据仍为审阅包。
- 分支 feat/d-map。公共基线 398d384。地图与候选数据 639db8f，路网服务及测试草稿 58cbae1，校园审阅包和专用测试 49edca5。首次被测 SHA 为 6ff3f70e4af7cc46a889ca40ff961865bc5f8b5b，首次路径全对复验 SHA 为 bb175f94ddeaf37ed53b51ced1062ac7590d656f，推送前被测代码 SHA 为 1e2f6ded7542c97e0154d3ad0f534e60822a4528。
- 预定交付仓库 https://github.com/LinSui-dev/campus-bike-dispatch-system/tree/feat/d-map 。推送核对以交接消息给出的远程 HEAD 为准。
- FR01、FR02、FR03，以及 FR05、FR09 的路径支撑。T09、T15，AC-D01～AC-D03。
- 首批接入范围为 `app.network.NetworkService` 与 D 模块自测。接收方 A/B 可先用现有 fixture 或各自的契约数据接入。E 可按本报告复现模块结果。
- 地图及 14 站数据审阅包位于 `data/campus/profile-review`，状态为 draft。正式 campus profile、真实 API 联调和 AC-D03 留在后续批次。

## 2 成果与入口

- 地图脚本、可编辑 SVG、前端预览及候选图和站点记录位于 data/campus。站点校区分布提案位于 docs/integration/requests/D-默认站点校区分布.md。
- 路网代码为 backend/app/network/service.py。模块用例为 backend/tests/owner_d/test_network_service.py，审阅包用例为 backend/tests/owner_d/test_campus_review_profile.py。公开入口 app.network.NetworkService。
- 契约 1.1.0。构造接收 RoadNetwork 与 Station 数组。validate_station 接收 StationCreate 并返回 Station。route 返回 Route。
- A 在站点保存前把合并后的 StationCreate 交给 `validate_station`，按公共端口映射 INVALID_STATION、UNREACHABLE。保存成功后用新路网和站点创建新实例。B 调用 `route` 获取米制距离及有序像素折线，返回数据可独立读取。
- 下例使用公开的四站 fixture。在仓库根目录启动 Python 后添加 backend 到模块搜索路径。
- fixture 用于开发。campus 正式数据待整理。服务依赖现有锁文件中的 NetworkX 3.4.2。

```python
import json
import sys
from pathlib import Path

sys.path.insert(0, "backend")
from app.network import NetworkService

fixture = Path("data/fixtures")
network = json.loads((fixture / "road_network.json").read_text(encoding="utf-8"))
stations = json.loads((fixture / "default_stations.json").read_text(encoding="utf-8"))
service = NetworkService(network, stations)
print(service.route("s1", "s4"))
print(service.route("s4", "s1"))
candidate = {key: value for key, value in stations[1].items()
             if key not in {"road_edge_id", "road_offset"}}
candidate["y"] = 207
print(service.validate_station(candidate))
```

## 3 安装与复现

以下命令从 D 独立工作目录根目录运行。模块测试不启动服务，不写数据库。

    python -m venv .venv
    .\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
    .\.venv\Scripts\python.exe -m pytest backend/tests/owner_d
    .\.venv\Scripts\python.exe -m pytest backend/tests/owner_d/test_campus_review_profile.py
    python scripts/check_baseline.py

## 4 验收证据

|项目|输入与操作|预期|实际|
|---|---|---|---|
|AC-D01 / T09|合成折线、同边多站、端点共点、反向、跨区、断开及重建。运行 owner_d 测试|米制权重正确、折线有序、不可达报错、重建使用新权重|本地模块自测通过|
|AC-D02 / T09|合法投影、超容差、图外、同 ID 替换和断开孤岛。运行 owner_d 测试|输出标准化 Station，原数据不变，相应错误明确|本地模块自测通过，A API 联调待执行|
|AC-D03 准备|审阅包 PNG、DTO、14 站库存、4 场景 OD、唯一跨区链及跨区往返。运行 test_campus_review_profile.py|数据引用自洽、跨区经指定门链|4 项审阅包自测通过，正式 AC-D03 待执行|
|AC-D03 / T15|使用正式 campus 数据核验路网、底图、站点、OD 和唯一跨区路线|全部引用合法，各校区连通，跨区仅经确认链路，数据来源可追溯|未执行，正式 profile 未生成|

2026-11-26 本地使用 Python 3.12.9 和锁定依赖。首次 pytest 因独立虚拟环境未安装 pytest 而无法开始，随后执行 requirements-lock.txt 安装成功。首次基线检查因三个 D Python 文件含 UTF-8 BOM，语法扫描报 U+FEFF。已在 6ff3f70 修正编码。复跑命令：

    .\.venv\Scripts\python.exe -m pytest backend/tests/owner_d -v
    .\.venv\Scripts\python.exe scripts/check_baseline.py

实际结果为 20 项通过、0 项失败（17 项合成小图模块用例、3 项审阅包用例），基线检查退出码 0、输出 Baseline OK。基线检查覆盖 fixture 和工程结构。真实 API、正式 AC-D03 与 E 复验未执行。

补做 fixture 调用自测。在独立 PowerShell 环境将 `PYTHONPATH` 设为 `.;backend`，用 `.\.venv\Scripts\python.exe -` 执行第 2 节调用与断言。实际结果为 s1 → s4 及反向均为 800.0 米，四个折线点顺序互逆。站点 s2 的输入 (350,207) 投影为 (350,200)，道路 e1，偏移 1.0。命令退出码 0。

### 当前审阅包的补充路径证据

运行 .\.venv\Scripts\python.exe data/campus/build_route_check_review.py 生成 data/campus/route-check-review.html。该页展示真实 NetworkService 输出与候选底图。M10 → M13 为 266.43 米，E01 → E04 为 297.14 米。M08 → E01 及反向均为 829.47 米，包含两侧校内接入和 469 米跨区链。距离取自审阅包，无现场实测结论。Edge 首屏已渲染并检查路线图层。

在 bb175f94ddeaf37ed53b51ced1062ac7590d656f 上执行 .\.venv\Scripts\python.exe -m pytest backend/tests/owner_d -q，21 项通过，共 0.58 秒。新增用例遍历 14 站的 91 对组合及其反向，核对距离、折线及起终点。随后运行 .\.venv\Scripts\python.exe scripts/check_baseline.py，退出码 0，输出 Baseline OK。A 的真实站点 API 联调、C 的真实地图路径接入和正式 AC-D03 仍待执行。


推送前已同步检查 origin/main，远程公共基线仍为 398d384。运行 .\.venv\Scripts\python.exe -m pytest backend/tests/owner_d -q，共 21 项通过、0 失败。运行 .\.venv\Scripts\python.exe scripts/check_baseline.py，退出码 0。边长口径图层用 Edge 检查了 109 条绘图边，以及 E157 显示 100 米和用户确认来源。这些证据用于本地模块和审阅包，不替代正式 AC-D03。


## 5 依赖与集成

- A 对接 NetworkService 构造、标准化站点输出及错误映射。B 使用 route 取得米制距离和图像折线。C 使用底图与坐标。E 在独立环境执行后续复验。
- 站点口径差异待 E 协调。设计及 AC-D03 要求 12 站、主校区 8、东校区 4。用户确认的审阅包是 14 站、主校区 11、东校区 3，容量总计 565 辆，初始 290 辆。站点分布提案维持待协调。公共契约、验收矩阵均沿用基线版本。
- D 等待最终名单后生成正式默认站点和对应 OD。E 决定默认数据验收口径，并协调 A/B/C 检查是否固定站点总数或校区数量。F 使用最终数据版本更新课程材料。路网服务按输入站点列表构建，不依赖上述两种数量。
- 边长来源分别记录于 `road-length-review.json`。道路 50 采用用户确认的 100 米。跨区链总长 469 米已确认，各分段按底图比例分摊。其余路段含在线中心线量算和底图比例估算。E 需确认适用的证据标准及需要复测的路段。
- 数据路线为候选审阅 JSON → 经核验的边长和默认运营参数 → 正式 campus profile。DB 无本次迁移。

## 6 限制与未完成项

|问题|影响|下一步|
|---|---|---|
|正式验收和真实 API 尚未运行|本地自测结果仅覆盖 D 模块和审阅包|等待 E 协调后进行真实接入与正式验收|
|候选地图和边长尚未转入正式 campus profile|无法进行真实路径与数据验收|道路 50 和跨区总长已确认；核验剩余边长及来源，协调 14 站及 11＋3 分布|
|逐站容量、初始库存已确认，四场景已编制为合成草稿|默认 profile 不可导入|站点已按 profile-inputs.json 写入审阅包，正式导入前由 E 核对口径及合成假设|

## 7 给 F 的文档素材

- 编辑底图与站点预览位于 data/campus/map-preview.html。路网细节、来源和估算限制见 road-graph-review.md 与 road-length-review.json。
- 地理参考包含校方手绘资料、OpenStreetMap 与用户圈注。正式文件的授权状态和米制长度仍需核验。图面与候选数据无仿真实验结论。
- D 绘制底图、整理候选图和站点、实现路网服务及模块用例。暂无正式运行截图、种子或贡献评分。

## 8 E 接收结论

复验提交、命令、结果、证据路径及 accepted / returned 结论由 E 复验后填写。
