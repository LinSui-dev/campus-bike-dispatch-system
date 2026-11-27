# 成员E 联调、测试与集成交接报告

## 1 身份与范围

- 成员、模块：E，公共契约、联调、验收框架、系统集成与正式实验。
- 状态：**draft**。E 范围已完成真实集成、7 项业务验收、120 组正式实验、五页面与 C01～C03 真实浏览器证据；常规门禁 614/614 与 E 验收 7/7 通过。仅 F 的论文/PPT 未交付（AC-F01/F02 pending），故未标 accepted。
- 分支、代码提交 SHA、基于的公共基线 SHA：交付分支 `test/e-integration`（基于 `398d384`）；集成工作分支 `integrate/abcd-20261127`，合并 A `bc98e7a5`、B `7186c686`、C `dc954a7e`、D `fcad17ac`。被测代码 SHA 以本分支最新提交为准（见第 8 节交接消息）。
- 远程仓库与本人交付分支链接：https://github.com/LinSui-dev/campus-bike-dispatch-system/tree/test/e-integration
- 推送核验：待推送后核对本地 HEAD 与 `git ls-remote origin refs/heads/test/e-integration`。
- 对应 FR、T、AC：全部 FR；T01～T15 的系统侧；AC-E01～AC-E03 主责，复验 A/B/C/D 全部 AC，配合 F01/F02。
- 本次交接范围：四分支集成、campus 正式 profile 提升、真实验收测试、120 组实验、五页面真实截图、验收状态记录。明确未包含：F 的论文/PPT；A/B/C 的旧测试与人工证据修复；docs/04/09/13 的 F 文档同步。

## 2 成果与入口

- 修改文件列表：
  - `tests/acceptance/{__init__,conftest,test_system}.py`：7 项真实系统验收（campus profile、站点投影、运行守恒、真实调度幂等、真实批量统计、单槽、路网/OD）。
  - `data/campus/{metadata,road_network,default_stations,scenarios,default_config}.json`、`campus_map.png`：由 D 审阅包提升的正式 profile（用户授权）。
  - `contracts/examples/batch_request.json`：场景改为 D 的 8 组（120 组合）；`contracts/examples/supply_demand.json`：`fluid-v2`。
  - `scripts/check_baseline.py`：组合数 60→120；`scripts/e2e_campus_ui.mjs`：真实五页面驱动与截图脚本。
  - `docs/integration/results/`：集成记录、120 组实验报告、验收日志与截图；`docs/handoffs/A/B/C/D` 第 8 节接收结论。
- 公开入口：`pytest tests/acceptance -m acceptance`；`node scripts/e2e_campus_ui.mjs`（需先启动 8010 后端与 15175 前端）；`DATA_PROFILE=campus`。
- DTO 与契约：1.1.0，未改字段/枚举/签名；示例数据与 estimator 版本同步。
- 数据 profile：`campus`（14 站，8 场景）与 `fixture`；环境变量 `DATA_PROFILE`、`DATABASE_URL`。
- 依赖：Python 锁文件新增 A 的 `websockets==16.1.1`；前端锁新增 C 的 `@playwright/test@1.58.2`。

## 3 安装与复现

```powershell
# 工作目录：仓库根目录；Python 3.13.5、Node 24.13.0
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
npm --prefix frontend ci
.\.venv\Scripts\python.exe scripts/check_baseline.py
.\.venv\Scripts\python.exe -m pytest backend/tests tests/integration
.\.venv\Scripts\python.exe -m pytest tests/acceptance -m acceptance

# campus 真实后端（临时库）
$env:DATA_PROFILE='campus'
$env:DATABASE_URL='sqlite:///' + (Join-Path $env:TEMP 'e-campus.db')
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --host 127.0.0.1 --port 8010

# 另一终端：真实前端（Mock 关闭）
$env:VITE_USE_MOCK='false'; $env:BACKEND_URL='http://127.0.0.1:8010'
npm --prefix frontend run dev -- --port 15175

# 第三终端：五页面驱动与截图
node scripts/e2e_campus_ui.mjs
```

120 组正式请求见 `docs/integration/results/evidence/experiments/batch-120-request.json`，用 `POST /api/v1/batches` 提交；结果见同目录 `batch-120-result.json`。停止服务用 Ctrl+C；测试库均为临时文件。

## 4 验收证据

|AC/T编号|输入及前置条件|操作或命令|预期结果|实际结果|证据路径|
|---|---|---|---|---|---|
|AC-E01|四分支真实合并|campus 基线、pytest、前端构建|可复现、交接可追踪|基线 OK、**614/614 通过**、构建通过；4 项旧断言经授权由 E 仅改断言|`docs/integration/results/evidence/acceptance/regular-gate.txt`|
|AC-E02|真实 A/B/D + C，Mock 关闭|五页面、交互运行、调度、批量|health implemented、无 501、守恒、五页一致|通过；9 步 0 错误；交互运行 290 辆守恒|`docs/integration/results/evidence/ui/`、`tests/acceptance/test_system.py`|
|AC-E03|8 场景×3 策略×5 种子|campus 批次 120 项|120 项终态、统计 n=5、可查历史|**120/120 成功、0 失败**|`experiments-120.md`、`evidence/experiments/`|
|AC-D03|正式 campus profile|加载、站点/场景/路线校验|14 站、8 场景、跨区链路|通过；266.43 / 297.14 / 829.47 米复验一致|`tests/acceptance/test_system.py`、`integration-20261127.md`|
|AC-A01/A02/A04/A07|真实后端|campus 验收测试|campus 投影、守恒、幂等调度、单槽|通过|`evidence/acceptance/pytest-acceptance.txt`|
|AC-C01～C04|真实前端|campus UI 脚本|五页面真实数据|五页/启动暂停/调度/120 条历史通过；C01 重置三选项、C02 刷新恢复与重置 404、C03 拖动 PATCH 仅 x/y 均通过|`evidence/ui/`|

- 测试总数：常规 **614/614 通过**；E 验收 **7/7 通过**；C 浏览器套件 6/6 通过。
- Mock/替身：E 验收与截图均未使用 Mock；仅 A/B/C/D 各自模块测试使用其声明的替身。
- 尚未接入：F 的论文/PPT（AC-F01/F02 pending）。
- 常规门禁退出 0；正式门禁在 acceptance.json 的 F 项仍 pending 时预期失败（如实记录，不伪造）。

## 5 依赖与集成

- 需要接收者：F 更新 docs/04、09、13 的 14 站/8 场景/120 组口径并交付论文 PPT；A/B/C 的旧断言与真实证据已由 E 按授权补齐并复验。
- 契约提案结论：
  - B `fluid-v2`：**接受**，示例已更新；docs/06 由 F 同步。
  - D 14 站/8 场景：**接受**，正式 profile 与示例已同步；docs/04/09/13 由 F 同步。
  - A 批量汇总保存失败重试：本轮**不新增契约**，维持“只读 interrupted、重新开展批次”的明确限制，待 F 记录；不阻塞 P0。
- Mock 切换：前端 `VITE_USE_MOCK=false` + `BACKEND_URL`；E 脚本已验证。
- 合并顺序：A → B → D → C → E；main 由 E 复验后快进/合并。
- DB：无迁移；campus 与 fixture 必须使用独立 `DATABASE_URL`。

## 6 限制与未完成项

|问题|复现|影响|责任人|下一步|
|---|---|---|---|---|
|4 项旧断言|已修复|无（614/614 通过）|E（用户授权）|记录于 integration-20261127 第 3 节|
|C01/C02/C03 真实证据|已补齐|无（C 项 accepted）|E|见 evidence/ui/c0*-*.png 与 c-real-acceptance.json|
|F 论文与 PPT 未交付|`docs/f-delivery` 不存在|F01/F02 无法验收|F|交付后 E 核对|
|Python 3.13 与基线 3.12|`python --version`|环境偏差|F/E|论文注明；如需严格复现另装 3.12|
|favicon.ico 404|浏览器控制台|装饰性|C|可选补图标|

## 7 给F的文档素材

- 系统真实证据：120 组实验表与限制（`experiments-120.md`）、五页面截图（`evidence/ui/`）、集成记录（`integration-20261127.md`）、验收测试日志。
- 关键限制：需求率为课程合成参数；统一 120 分钟时长、场景窗口外为空闲段；贪心与最小费用流多数重合，仅晚课成本有差异，不宣称优劣；部分边长由底图比例估算，跨区链路 469 米经用户确认。
- 版本：契约 1.1.0、引擎 a-engine-v1、预测 fluid-v2、路网 campus-review-v1、14 站/8 场景；种子 42～46。
- 贡献依据：以各分支 SHA、handoff 第 8 节与 E 证据为准，不自编团队评分。

## 8 E接收结论

- 本报告为 E 自身范围，状态 draft；A/B/C 结论见各自报告第 8 节，D 已 accepted。
- 复验命令与结果见第 3、4 节；综合记录 `docs/integration/results/integration-20261127.md`。
