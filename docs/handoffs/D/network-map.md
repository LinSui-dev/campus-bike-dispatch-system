# 成员 D 地图、路网与数据交接

## 1 身份与范围

**状态为 draft。** 路网服务已通过 D 模块自测，可供 A、B 接入。校园底图、站点与需求场景已生成审阅包。正式校园数据导入、真实接口联调和 AC-D03 复验待完成。

| 项目 | 交接信息 |
| --- | --- |
| 负责人 | 成员 D |
| 需求与任务 | FR01～FR03，FR05、FR09 的路径支撑，T09、T15 |
| 验收项 | AC-D01～AC-D03，详见第 4 节 |
| 公共基线 | `398d384` |
| 交付分支 | [feat/d-map](https://github.com/LinSui-dev/campus-bike-dispatch-system/tree/feat/d-map) |
| 已核对的远程提交 | `4daa751f724870995e342bff6f385b585807330d`，含八组场景和对应模块自测 |

正式实验采用用户确认的全部八组场景。沿用三种策略、五个种子时，完整批次为 120 次。公共实验批次和验收口径待 E 同步。

## 2 成果与入口

| 成果 | 文件与使用方式 |
| --- | --- |
| 路网服务 | [service.py](../../../backend/app/network/service.py)，从 `app.network` 导入 `NetworkService` |
| 可编辑底图与站点 | [地图预览](../../../data/campus/map-preview.html)，可切换全图和跨区局部，查看站点、道路编号与边长口径。生成脚本与 SVG 在 [地图目录](../../../data/campus/) |
| 校园审阅包 | [数据与来源](../../../data/campus/profile-review/sources.md)，含 PNG、路网、14 站、八组 OD 数据和默认配置 |
| 场景审阅 | [时窗与起终站](../../../data/campus/scenario-review.html)，含双向跨区通学和图书馆接入。需求率为合成参数 |
| 路径审阅 | [校内与跨区样例](../../../data/campus/route-check-review.html)，展示服务返回的距离及折线 |

服务使用契约 1.1.0 与 NetworkX 3.4.2。构造方法 `NetworkService(network, stations)` 接收 `RoadNetwork` 与 `Station` 列表。

- A 在保存前调用 `validate_station(candidate)`，输入 `StationCreate`，得到标准化 `Station`。接口按契约映射 `INVALID_STATION` 和 `UNREACHABLE`。保存后用更新后的数据重建服务。
- B 调用 `route(source_id, destination_id)` 获得 `Route`，包含米制距离和有序像素折线。
- C 可从审阅包读取底图、尺寸与同画布坐标。开发对接可使用 `data/fixtures`，正式 `DATA_PROFILE=campus` 待启用。

在仓库根目录运行以下 Python 示例，使用四站 fixture 调用服务。

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

从仓库根目录执行。原自测环境使用 Python 3.12.9。以下命令无需启动服务或连接数据库。

```powershell
git switch feat/d-map
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest backend/tests/owner_d -q
.\.venv\Scripts\python.exe scripts/check_baseline.py
```

如需重新生成审阅页，在同一目录执行以下命令。

```powershell
.\.venv\Scripts\python.exe data/campus/build_profile_review.py
.\.venv\Scripts\python.exe data/campus/build_route_check_review.py
```

## 4 验收证据

| 项目 | 输入与操作 | 预期 | 实际与证据 |
| --- | --- | --- | --- |
| AC-D01 / T09 模块自测 | 合成折线、同边多站、端点共点、反向、跨区、断开与重建，运行第 3 节 pytest | 距离权重和折线顺序正确，断开时报错，重建使用新权重 | 通过。[路网用例](../../../backend/tests/owner_d/test_network_service.py) |
| AC-D02 / T09 模块自测 | 合法投影、超容差、图外、同 ID 替换、孤岛，运行同一命令 | 返回标准化站点并保留原输入，错误类型符合契约 | 通过，A 的真实 API 联调待执行。[路网用例](../../../backend/tests/owner_d/test_network_service.py) |
| AC-D03 准备 | 用校园审阅包运行同一命令 | PNG 与 DTO 引用正确，14 站共 91 对及反向可达，跨区经过指定校门，八组时窗和 OD 符合配置 | 通过。[审阅包用例](../../../backend/tests/owner_d/test_campus_review_profile.py) |
| 常规基线 | 运行 `scripts/check_baseline.py` | fixture 引用、连通性、工程结构及旧基线的 60 个组合通过 | 输出 `Baseline OK`，退出码 0 |
| AC-D03 / T15 正式验收 | 导入正式校园数据后由 E 执行 `scripts/check.ps1 -Acceptance` | 底图、站点、路网、OD 及数据来源可核验，跨区仅经指定链路 | 未执行，正式 profile 待生成 |

D 模块最新结果为 **21 项通过、0 项失败**。场景生成命令实际输出 `Draft generated: 14 stations, 8 scenarios.`。模块用例使用合成小图、项目 fixture 与校园审阅包，无生产 Mock 开关。真实 API、C 页面路径接入及 E 集成复验待执行。

补充证据如下。

- fixture 调用中，s1 与 s4 双向均为 800.0 米，四个折线点顺序互逆。s2 从 (350,207) 投影至 (350,200)，关联 e1，偏移 1.0。
- 校园审阅包中，主校区 M10 → M13 为 266.43 米，东校区 E01 → E04 为 297.14 米，M08 与 E01 双向均为 829.47 米。跨区距离包含 469 米校外段与两端校内路段。路线图层已在 Edge 检查。 [路径证据](../../../data/campus/route-check-review.html)
- 曾用 Edge 检查 109 条绘图边，确认道路 50 对应的 E157 显示 100 米和来源。 [边长口径](../../../data/campus/road-length-review.json)

## 5 依赖与集成

1. A、B 按契约 1.1.0 接入路网服务，C 按同画布坐标接入底图。各方可先使用 fixture。
2. E 协调默认站点分布、边长证据和八组实验口径，D 据确认结果生成正式校园数据。B 核对各场景时长和调度触发。A、C 核对不同场景时长的加载和展示。
3. 正式数据就绪后，E 在独立环境复验站点保存、地图路线及 AC-D03。本次数据交付无需数据库迁移。

| 待同步事项 | 对应记录 |
| --- | --- |
| 默认站点数量及校区分布 | [D 默认站点校区分布提案](../../integration/requests/D-默认站点校区分布.md) |
| 正式实验采用八组及对应时长 | [D 八组需求场景变更提案](../../integration/requests/D-八组需求场景.md) |

## 6 限制与未完成项

| 事项 | 当前情况与影响 | 负责人及下一步 |
| --- | --- | --- |
| 站点数量 | 审阅包经用户确认共 14 站，主校区 11 站、东校区 3 站，总容量 565 辆、初始 290 辆。AC-D03 基线是 12 站，主校区 8 站、东校区 4 站 | E 协调验收口径，D 据此生成正式默认站点和 OD |
| 边长与底图来源 | 道路 50 的 100 米和跨区链的 469 米总长已确认。跨区分段按底图比例分摊，其余边长含在线中心线量算及底图比例估算 | D 提供来源，E 确认证据标准及需要复测的段落 |
| 八组正式实验 | 审阅包已生成八组，公共基线检查仍使用原 60 个组合 | E 协调公共实现和验收更新，B 核对运行时长与统计口径 |
| 正式导入与验收 | 正式校园 profile、真实 API 和 C 路径接入待验证 | D 生成正式数据，A、C 完成对接，E 复验 |

## 7 给 F 的文档素材

- D 的实际贡献包括绘制可编辑底图、整理候选路网和站点、实现路网服务与模块用例、编制八组需求场景。跨区链经主校区南门、上园村路和东校区小西门。 [路网与来源说明](../../../data/campus/road-graph-review.md)
- 地理参考包括校方手绘资料、OpenStreetMap 和用户圈注。需求率为课程合成参数，正式底图许可状态与米制长度仍需核验。 [审阅包来源](../../../data/campus/profile-review/sources.md)
- 路径审阅页使用校园审阅包和真实路网服务输出，可作功能示例。正式场景实验截图、种子与运行结果待集成后补充。 [路径审阅页](../../../data/campus/route-check-review.html)

## 8 E 接收结论

复验提交、命令、结果、证据路径及 accepted / returned 结论由 E 复验后填写。
