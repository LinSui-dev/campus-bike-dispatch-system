# 集成与验收记录（2026-11-27）

## 1 集成分支与来源

- 集成分支：`integrate/abcd-20261127`（本地，未推送）
- 合并顺序：A → B → D → C，均为 `--no-ff`，无冲突
- 各分支实测 SHA：

| 成员 | 分支 | SHA | 交接状态 |
|---|---|---|---|
| A | `feat/a-engine` | `bc98e7a5e28b78cd86a5e76a29b0d1665b6d0860` | draft（模块级） |
| B | `feat/b-dispatch` | `7186c686c7085318faa08ba09993b0b582facbdd` | ready（模块级） |
| C | `feat/c-frontend` | `dc954a7e39160a2d4d9ae13b9c2c27ed5f57d838` | ready（前端 Mock） |
| D | `feat/d-map` | `fcad17aceda8fbb3209207d181da53ec161c76fb` | draft（审阅包） |
| E | `test/e-integration` | 见交接报告 | 本次范围 |

- 正式 campus 数据：经用户授权，由 E 将 D 审阅包中的 6 个文件提升到 `data/campus/`（`metadata.json`、`road_network.json`、`default_stations.json`、`scenarios.json`、`default_config.json`、`campus_map.png`），未改动字段或 Schema。`profile-review/` 原样保留。
- 实验与验收口径：按 D 的规格变更采用 **14 站（主 11 / 东 3）** 与 **8 场景 × 3 策略 × 5 种子 = 120 组**；`contracts/examples/batch_request.json` 已同步为 8 场景，`supply_demand.json` 的 `estimator_version` 同步为 `fluid-v2`。docs/04、09、13 的旧数字（12 站、4 场景、60 组）待 F 按本记录更新。

## 2 实际执行结果

环境：Windows 11，Python **3.13.5**（项目基线写 3.12；本机 `py -3.12` 损坏，锁依赖在 3.13 下安装与运行正常，属环境偏差），Node 24.13.0，npm 11.6.2，独立 `.venv` 与临时 SQLite 库。

| 检查 | 命令 | 结果 |
|---|---|---|
| 基线 | `python scripts/check_baseline.py` | `Baseline OK`，退出 0 |
| 后端/集成测试 | `python -m pytest backend/tests tests/integration` | **614 passed / 0 failed**（4 项旧断言经用户授权由 E 更新，见第 3 节） |
| 前端构建 | `npm --prefix frontend run build` | 退出 0 |
| E 业务验收 | `python -m pytest tests/acceptance -m acceptance` | **7 passed**，3.80 秒 |
| 真实后端（campus） | uvicorn `DATA_PROFILE=campus`，端口 8010 | health `implemented`；14 站 / 8 场景；地图 PNG 200 |
| 真实交互运行 | UI 启动→暂停；API 运行 30 分钟 | 完成，40/290 辆守恒（fixture）与 290 辆守恒（campus） |
| 真实调度 | 交互 `POST /runs/{id}/dispatch` | 生成运输任务，重复 `request_id` 不重复扣减 |
| 真实批量 | 1 场景 × 3 策略 × 2 种子 | 6/6 完成，统计 n=2、标准差非空，none 调度量为 0 |
| 正式实验 | 8 × 3 × 5 = 120 | **120/120 成功，0 失败**，见 [实验报告](experiments-120.md) |
| 真实前端五页面 | Vite Mock 关闭，接 campus 后端 | 9 步、0 错误；截图见 `evidence/ui/` |
| C 模块浏览器套件 | `npm --prefix frontend test`（Edge） | **6/6 通过**（Mock 场景 + 真实 HTTP 兼容检查），日志见 `evidence/acceptance/c-browser.txt` |

## 3 旧断言更新（用户授权 E 代为修改，仅改测试断言）

集成后 4 项测试仍断言“业务未实现”的骨架行为，真实 B/D/C 接入后必然失效。用户授权 E 只更新断言、不改业务逻辑，更新后常规门禁 **614/614 通过**：

| 原测试 | 原因 | 更新后 |
|---|---|---|
| `owner_a/test_api.py::test_default_production_ports_fail_explicitly_and_never_use_test_doubles` | 断言 `stage=scaffold` 与创建返回 501 | 改为断言 `implemented`、真实创建 201、停止后槽释放并保存 1 条历史 |
| `owner_a/test_api.py::test_campus_missing_data_does_not_fall_back_to_fixture` | 依赖正式 campus 数据缺席 | 用 `monkeypatch` 指向空数据根目录，仍验证不降级 fixture |
| `owner_a/test_runtime.py::test_unimplemented_runner_is_explicit_501_and_slot_released` | 断言批量 501 | 改为断言真实 runner 完成 4 项、保存 4 条历史、释放槽 |
| `owner_b/test_runner.py::test_default_sixty_combinations` | 断言公共示例为 60 组 | 改为按示例计算 120 组 / 24 个聚合组 |

A、B 的模块业务逻辑未改；复验日志见 `evidence/acceptance/regular-gate.txt`。该跨归属修改已在 A/B handoff 第 8 节注明。

## 3.1 C 的真实浏览器证据

`scripts/e2e_campus_acceptance.mjs` 在 Mock 关闭、campus 后端下实际点击并记录请求：

- C01：重置弹窗三选项；取消不发 control 请求；保存重置发送 `{action:"reset",save:true}`，舍弃发送 `save:false`。
- C02：种子 47、午餐、暂停并设 27.5×，刷新后状态/场景/种子/倍速恢复；切五页保持暂停；外部重置后 UI 通过 404 路径回到空闲。
- C03：真实底图与道路图层；拖动 M10 后 PATCH `/stations/M10` 仅含 `x/y`，服务端投影返回成功。
- 证据：`evidence/ui/c01-*.png`、`c02-*.png`、`c03-*.png`、`c-real-acceptance.json`，0 错误。

## 4 遗留与限制

- F 的 `docs/f-delivery` 分支不存在，论文/PPT 未交付，AC-F01、AC-F02 保持 pending；这是当前唯一未通过的 AC 组。
- 旧 seq 覆盖与“恢复时重置”在真实后端下没有等价的可注入开关，仍由 C 的 Mock 套件覆盖；真实模式已覆盖刷新恢复与外部重置 404 路径。
- 运行日志中仅 `favicon.ico` 404（前端未提供图标），不影响功能，记录为装饰性问题。
- Python 3.13 与基线 3.12 的偏差、合成需求率、底图比例估算边长等，由 F 在论文中如实说明。
- docs/04、09、13 仍写 12 站/4 场景/60 组，按 `docs/integration/requests/E-口径与契约协调结论.md` 由 F 同步。

## 5 证据索引

- 正式实验：[experiments-120.md](experiments-120.md)、`evidence/experiments/`
- 验收测试日志：`evidence/acceptance/pytest-acceptance.txt`
- 常规门禁日志：`evidence/acceptance/regular-gate.txt`
- 真实 UI：`evidence/ui/*.png`、`evidence/ui/ui-acceptance.json`
- 复现脚本：`scripts/e2e_campus_ui.mjs`
