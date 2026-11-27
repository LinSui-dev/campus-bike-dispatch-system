# 成员 C 前端交接报告

## 1 身份与范围

- 成员 C，负责 P0 五页面、地图交互、REST/WS 客户端和显式 Mock。
- 状态为 **ready（前端模块）**。E 接收结论见第 8 节。
- 本地分支 `feat/c-frontend`。被测代码 `cd54b64c3114d604ca6b1ce4ca86bd074f79acbb`，公共基线 `398d38435ca508450c0de866a0c3537169a26851`。推送核验以交接消息的分支 HEAD 为准。
- [远程交付分支](https://github.com/LinSui-dev/campus-bike-dispatch-system/tree/feat/c-frontend)
- 覆盖 FR01～FR04、FR06、FR09、FR10，主责 AC-C01～AC-C04、T13、T14，配合 AC-A01、AC-A06、AC-D03、T09、T10、T12。真实 A/B/D 后端、正式校园地图与完整系统验收由 E 复验。

## 2 成果与入口

| 页面 | 路径 | 交付功能 |
|---|---|---|
| 运营总览 | `/#/overview`（默认） | 借还指标和趋势、双校区库存及预警、车辆状态、站点地图与详情 |
| 停车点管理 | `/#/stations` | 校区筛选、列表与地图联动、地图选址、站点 CRUD、标准化拖动与关联 OD 删除确认 |
| 仿真控制 | `/#/control` | 场景新建、复制、编辑及删除，OD 和倍率时段，配置 CRUD，全局开始、暂停、继续、倍速、停止、重置 |
| 智能调度 | `/#/dispatch` | 策略参数、站点供需、手动触发、运输任务状态和进度、地图路线 |
| 实验分析 | `/#/experiments` | 组合预览、批次进度、失败子项、策略均值和样本标准差及有效 n，独立历史和保存时的站点及任务 |

改动清单可用 `git diff --name-only 398d384 cd54b64 -- frontend` 核对。功能入口为 [App.vue](../../../frontend/src/App.vue)，具体页面在 [src/pages](../../../frontend/src/pages)。接口和错误封装在 [api.ts](../../../frontend/src/api.ts)、[transport.ts](../../../frontend/src/transport.ts)、[types.ts](../../../frontend/src/types.ts)，数据存储在 [src/stores](../../../frontend/src/stores)，复用控件在 [src/components](../../../frontend/src/components)。页面样式、依赖锁、入口与代理配置均位于 `frontend`。替身在 [src/mocks](../../../frontend/src/mocks)，自测入口是 [frontend.spec.ts](../../../frontend/tests/frontend.spec.ts)。

客户端采用 1.1.0。新增站点发 `StationCreate`，拖动发送 `StationPatch` 的 `x/y`，页面以服务端完整 `Station` 响应刷新。运行读取 `GET /api/v1/runtime` 后，活动运行连接 `/ws/runs/{id}` 缓冲并读取 `GET /api/v1/runs/{id}/state`。批量读取 `GET /api/v1/batches/{id}`。例如从前端根路径进入，静态请求经 Vite 代理，`Invoke-RestMethod http://127.0.0.1:5173/api/v1/runtime` 可检查当前运行槽。

## 3 安装与复现

从干净 clone 的仓库根目录执行。实测 Windows、Node 24.15.0 / npm 11.12.1、Python 3.11.9、Microsoft Edge 158.0.4370.33、Playwright 1.58.2。项目分发基线为 Node 20、Python 3.12。依赖锁为 `frontend/package-lock.json` 和 `backend/requirements-lock.txt`。前端使用 Vue 3.5.46、Pinia 2.3.1、Leaflet 1.9.4、ECharts 5.6.0、Element Plus 2.9.0。

```powershell
git switch feat/c-frontend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
npm --prefix frontend ci
$env:VITE_USE_MOCK='false'
npm --prefix frontend run build

# 浏览器模块与 HTTP 冒烟。使用已安装 Edge，使用 Chromium 时可省略渠道变量并先安装 Chromium。
$env:Path=(Join-Path (Get-Location) '.venv/Scripts')+';'+$env:Path
$env:C_TEST_CHROME_CHANNEL='msedge'
$env:PLAYWRIGHT_JSON_OUTPUT_FILE=Join-Path (Get-Location) 'artifacts/c-browser-results.json'
npm --prefix frontend test -- --reporter=list,json

# 常规与正式门禁分别执行。
$env:PYTHONUTF8='1'
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Acceptance

# 独立手工使用夹具，访问 http://127.0.0.1:5173，Ctrl+C 停止。
$env:VITE_USE_MOCK='true'
npm --prefix frontend run dev
```

浏览器测试自动启动 Mock 前端 15173、真实模式前端 15174 和 fixture 后端 18015。测试后端被指定到本轮独立的 `artifacts/c-browser-<进程号>.db`，基线骨架未写数据库。截图输出到 `artifacts/c-browser`。Mock 数据在标签页 `sessionStorage`，刷新保留，独立浏览器上下文从空闲开始。点击顶栏「虚拟联调模式」可注入发送旧序号、断开/恢复连接、恢复时重置、请求超时、保存失败、批量首个子项失败。

真实模式在后端启动前设置 `DATA_PROFILE=fixture` 或待 E 复验时使用 `campus`，并将 `DATABASE_URL` 指到独立 SQLite 数据库，按 A 的部署方式启动。前端终端设置 `VITE_USE_MOCK=false` 和 `BACKEND_URL=http://127.0.0.1:8000` 后运行 `npm --prefix frontend run dev`。端口可用 `-- --port 5175` 单独指定。变更环境变量后重启 Vite，已构建的页面需重新构建。

## 4 验收证据

下列步骤用 Playwright 驱动 Edge 实际点击并断言。截图另外进行目视核对，真业务浏览器复验待 E。Mock 请求记录由替身记录，真实 HTTP 仅用于检查骨架返回和地图资源连通。

| AC/T | 输入、操作与预期 | 实际结果 | 证据 |
|---|---|---|---|
| AC-C01、T10/T14、配合 AC-A06 | 初次进总览应空闲且无 POST。预设不可删且可复制。场景用相同起终点、重叠时段及 61 秒步长验证拒绝，修正后新增、更新场景及 OD，配置另存、更新、重载和删除。以种子 43 双击开始并注入超时，重试沿用 ID。依次暂停、设 25×、继续、取消重置、保存重置、舍弃重置、停止。注入保存失败后运行槽仍占用，可重试。 | Mock 通过。首次加载无 POST，三项校验给出提示，配置重载为种子 43。双击只产生一次创建尝试，重试 ID 相同。取消没有请求。两次保存重置（第一次注入失败）传 `save:true`，舍弃传 `false`。停止保存失败后仍可重新停止保存，最终只见 2 条历史。 | [总览](evidence/01-overview-idle.png)、[配置](evidence/03-control-config.png)、[重置](evidence/reset-three-options.png)、[请求日志](evidence/ac-c01-requests.json) |
| AC-C02、T13/T14 | 午餐、种子 47，暂停设 27.5× 后刷新。检查 11:00 起点、冻结初始 60×、当前倍速和页面切换。改为 37.25×，注入旧 seq、断线再连、读取状态时重置为 404。 | Mock 通过。刷新恢复暂停态、场景、种子与参数，五页切换保持暂停。旧 seq 未覆盖 37.25×，断线出现提示并继续 GET state，重新连接后提示消失。模拟重置后重查 runtime 返回空闲，全程只有一次 POST runs。 | [刷新前](evidence/recovery-before-refresh.png)、[刷新后](evidence/recovery-after-refresh.png)、[轮询](evidence/recovery-polling.png)、[请求日志](evidence/ac-c02-requests.json) |
| AC-C03、T09/T14、配合 AC-A01 与 AC-D03 | fixture 地图切图层、缩放平移、列表筛校区、地图选址。创建坐标 (175, 210)、容量 5，测容量 0、库存 10、库存 0/5。拖现有站约 20/10 显示像素后检验投影，再拖离道路。用贪心暂停发车并注入超时、重试、继续。两次复核关联删除选择。 | Mock 通过。道路默认隐藏，显隐后显示三段。创建不传道路字段并回到 y=200，空满均有文字。拖动 PATCH 仅有 x/y，投影至 y=200，拒绝后位置回退。调度两次提交同 ID，只有一项运输，点位和时钟在暂停后不变，继续后沿路线前进。确认删除使用 `clear_related_od=true`。真实 A/D 投影和校园地图待复验。 | [地图](evidence/02-stations-roads.png)、[暂停调度](evidence/04-dispatch-paused.png)、[请求日志](evidence/ac-c03-requests.json) |
| AC-C04、T12/T14 | 初始零请求、无调度、空历史，检查 4×3×5 预览。用早课×无调度/贪心×种子 42/43，触发 0/900 秒，注入首项失败，运行中刷新。查看对照图及子运行历史，关闭 Mock 后再访问公共基线后端。 | Mock 通过。预览为 60 组，仅实际执行四项。非法时刻 1 秒被拒绝。刷新恢复批量，最后 4/4，3 个成功历史、1 个明确失败。借车成功率均值和样本标准差为 —、有效 n 为 0。调度量均值均为 0，样本标准差 / n 为 — / 1 和 0 / 2。真实模式实收 HTTP 501，页面明确显示未实现且无替身库存。五页面未开放扩展入口。 | [策略对照](evidence/05-experiments-comparison.png)、[保存历史](evidence/05-experiments-history.png)、[真实模式 501](evidence/real-scaffold-501.png)、[请求日志](evidence/ac-c04-requests.json) |

- `npm --prefix frontend ci` 退出 0。常规门禁退出 0，基础校验通过、公共基线 pytest 32/32、TypeScript 和生产构建通过。FastAPI 测试客户端报告一条 Starlette 弃用警告。
- 模块浏览器套件 6/6，失败 0、跳过 0。包含四项 AC 的 Mock 流程、一项真实 HTTP 骨架测试和一项坐标与折线插值检查。[本轮执行摘要](evidence/browser-summary.json)
- 正式门禁退出 1。常规步骤通过后，`tests/acceptance` 收集 0 条，脚本按 pytest 空集失败处理，业务 AC 没有进入正式复验。

## 5 依赖与集成

- 依赖 A 的 1.1.0 REST/WS 与持久化、B 的供需与批量、D 的校园底图/路网及 E 的真实集成环境。当前公共基线返回 `stage=scaffold`。无 C 契约提案，本分支使用已有契约字段。
- E 合入 C 后，用 fixture 与空测试库复验业务 API、WS、刷新/断线、冻结与保存，随后切换 D 正式数据复验地图和实验。私有数据库单独指定，本分支未引入数据库迁移。
- D 的独立分支已提交八场景校园审阅包，验收口径仍待 E 统一。页面直接读取接口返回的场景和 `is_preset`，组合总数按实际选择计算。本次 60 组预览来自基线四场景夹具。

## 6 限制与未完成项

| 问题 | 复现 | 影响 | 责任人 | 下一步 |
|---|---|---|---|---|
| 公共基线的站点、场景及运行等真实业务接口尚未开放 | Mock 关闭后连基线，检查 `GET /api/v1/stations` | 真实站点、运行控制、WS、批量及数据库行为待验收 | A/B/E，C 配合 | 接入并按 AC-C01～C04 复跑 |
| 校园数据与审阅包尚未接入公共基线 | 查看公共 `data/campus`，对照 D 的交接状态 | 配合 AC-D03 的真实地图与跨校区路线截图缺失 | D/E，C 配合 | 使用 E 确认的校区 profile 截图并核验 |
| 真实系统正式门禁无业务用例 | `scripts/check.ps1 -Acceptance`，pytest 收集 0 条 | 系统验收未通过 | E | 接入业务与证据后重跑 |

## 7 给 F 的文档素材

- 五页面浏览器实拍及恢复和异常证据见第 4 节。全部地图和运行画面都使用仓库自建 `fixture-v1`。总览取空闲；仿真控制示例种子 43；恢复示例午餐、种子 47；调度示例早课、种子 42、贪心；批量早课、种子 42/43。地图是 4 站的虚拟底图，停车点截图包含另行添加的自测站。借还计数和批量统计仅展示界面状态。
- 地图在 Leaflet 边界由图像坐标转换为 `[H-y,x]`。路线来自状态的道路折线，运输点按累计折线长度及 `sim_time_sec` 插值。距离为 m，物理速度 km/h，供需库存用辆，借还用辆次，调度成本用辆·米，零分母显示 —。
- C 的提交包含五页、客户端、状态恢复、地图、图表、显式 Mock 和自测证据。正式地图、模型成果、实验指标与贡献评分由对应成员提供。

## 8 E 接收结论

- 复验基线/提交与实际命令：待 E 填写。
- 通过/失败项与证据路径：待 E 填写。
- 结论：待 E 填写 accepted 或 returned。
- 退回负责人、修复要求、复验及综合记录路径：待 E 填写。
