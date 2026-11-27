# E · 集成口径与契约协调结论（2026-11-27）

本文件记录 E 对本期提案与偏差的协调结论，作为 F 更新设计文档、A/B/C/D 后续复验的依据。

## 1 正式数据与实验口径

| 事项 | 结论 | 依据与说明 |
|---|---|---|
| 默认站点 | **采纳 14 站：主校区 11、东校区 3**；总容量 565、初始 290 | 用户确认；D 审阅包通过 A 的 Schema 与跨字段校验；E 已提升到 `data/campus/` |
| 需求场景 | **采纳 8 组**：morning、morning-dismissal、lunch、afternoon-class、afternoon-dismissal、dinner、evening-class、evening | D 审阅包；用户确认；`contracts/examples/batch_request.json` 已同步 |
| 实验规模 | **8 场景 × 3 策略 × 5 种子（42～46）= 120 组** | 取代原 4 场景 × 3 × 5 = 60 组；矩阵与 docs/04、09、13 由 F 同步 |
| 运行时长 | 统一 **120 分钟**、60 秒步长、每 900 秒触发调度；场景需求窗口按 D 数据生效 | 沿用 docs/06 的统一批次参数；短场景窗口外为空闲段，横向可比 |
| 契约字段 | 不变；无版本升级，仍为 1.1.0 | Station/Scenario/BatchRequest 字段未改，仅默认数据与示例内容变化 |

## 2 预测口径

- **接受 B 的 `fluid-v2`**：目标库存含窗口内需求水位最低点与泊松安全库存。
- `contracts/examples/supply_demand.json` 的 `estimator_version` 已改为 `fluid-v2`。
- docs/06“供需”一节与论文中的公式说明由 F 按 B 交接报告第 2.1 节同步；不保留 `fluid-v1` 作为默认。

## 3 批量汇总保存失败

- **本轮不新增批次控制路由**。维持：GET 只读、POST 幂等；汇总事务失败时返回 500、内存保留进度与已提交子运行，重启后按 batch_id 恢复为只读 `interrupted`，不自动续跑。
- 该分支限定为明确限制，由 F 在文档中说明；不阻塞 P0。若后续课程验收要求可重试入口，再按 A 提案新增 `POST /batches/{id}/control` 并升级契约。

## 4 文档同步清单（F）

- docs/04：12 站（主 8/东 4）→ 14 站（主 11/东 3）。
- docs/09：60 组 → 120 组；8 场景列表。
- docs/13：AC-D03 四场景 → 八场景；AC-E03 与最终完成判定的 60 → 120。
- docs/06：fluid-v2 目标库存公式；批量时长与触发口径。
- 论文与 PPT：使用 `docs/integration/results/experiments-120.md` 的真实结果与限制，不预设策略胜负。
