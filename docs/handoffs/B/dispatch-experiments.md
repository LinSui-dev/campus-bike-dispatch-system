# 成员B 调度与实验模块交接报告

## 1 身份与范围

- 成员、模块：B，调度与实验（预测、供需、三策略、批量与统计）
- 状态：ready（模块级自测通过；E复验后填写accepted/returned）
- 分支、代码提交SHA、基于的公共基线SHA：`feat/b-dispatch`；被测代码提交 `0ce2887`（fluid-v2；首版 fluid-v1 为 `30be90c`）；基于公共基线 `398d384`（origin/main，合入后无冲突）
- **重要：供需目标公式已偏离docs/06（fluid-v1→fluid-v2），见第2.1节。**
- 远程仓库与本人交付分支链接：https://github.com/LinSui-dev/campus-bike-dispatch-system/tree/feat/b-dispatch
- 推送核验：推送后核对本地HEAD与`git ls-remote origin refs/heads/feat/b-dispatch`一致；最终HEAD在交接消息中提供
- 对应FR、T、AC编号：FR07、FR08、FR10；T07、T08、T12；AC-B01～AC-B04（配合AC-A04、AC-E03）
- 本次交接范围：`DispatchService.estimate`、`DispatchService.plan`、`ExperimentRunner.run_batch`全部P0功能及模块测试。
- 明确未包含：真实引擎`run_once`接入、真实NetworkService闭环、60组正式实验（依赖A/D/E，见第5、6节）。

## 2 成果与入口

- 修改文件列表（均在B所有范围内）：
  - `backend/app/dispatch/service.py`（实现estimate/plan入口）
  - `backend/app/dispatch/forecast.py`（新增，流体预测）
  - `backend/app/dispatch/supply_demand.py`（新增，T/E/supply/demand）
  - `backend/app/dispatch/strategies.py`（新增，none/greedy/min_cost_flow）
  - `backend/app/experiments/runner.py`（实现run_batch）
  - `backend/app/experiments/stats.py`（新增，均值、样本标准差、null排除）
  - `backend/tests/owner_b/`：`helpers.py`、`test_supply_demand.py`、`test_strategies.py`、`test_forecast.py`、`test_runner.py`
  - `docs/handoffs/B/dispatch-experiments.md`（本报告）
- 公开导入路径与签名（与contracts/python_interfaces.py一致，无改动）：

```python
from app.dispatch import DispatchService
from app.experiments import ExperimentRunner

DispatchService().estimate(snapshot: State, scenario: Scenario, params: Params, network: NetworkPort) -> SupplyDemand
DispatchService().plan(algorithm: "none"|"greedy"|"min_cost_flow", supply_demand: SupplyDemand,
                       network: NetworkPort, max_dispatch: int) -> list[DispatchPlanItem]
ExperimentRunner().run_batch(request: BatchRequest, run_once: Callable[[RunSpec], RunOutcome],
                             on_progress: Callable[[BatchResult], None]) -> BatchResult
```

- 输入输出DTO和contract_version：1.1.0；SupplyDemand、DispatchPlanItem、RunSpec、BatchResult均经schema.json校验（见测试）。`estimator_version`为`fluid-v2`。
- 给A的最小调用示例：

```python
svc = DispatchService()
sd = svc.estimate(engine_snapshot, scenario, run_params, network_service)   # 调度时刻、本步借车之后
plan = svc.plan(state["algorithm"], sd, network_service, run_params["max_dispatch"])
# plan 每项 {source_id, destination_id, quantity, distance_m, route}；A 负责原子校验与执行
result = ExperimentRunner().run_batch(batch_request, run_once, publish_progress)
```

- 异常约定（给A映射HTTP错误）：
  - `plan`：未知algorithm或`max_dispatch<0`抛`ValueError`；路网`UNREACHABLE`的组合跳过；其他`NetworkError`原样抛出。
  - `estimate`：OD起终点不可达时抛`NetworkError("UNREACHABLE")`；B/R/served为负或served>B（内部不应出现）抛`ValueError`。
  - `run_batch`：请求不合法（场景/算法/种子为空或重复、未知算法、调度时刻重复、未按step对齐或不在[0,duration)）抛`BatchRequestError`（`ValueError`子类，`code="INVALID_BATCH"`，含`details`），此时不调用run_once也不发进度。`run_once`抛出的任何`Exception`或返回缺少run_id/summary，都记为该项failed并继续。
- 依赖：仅标准库与已锁定的`networkx==3.4.2`，无新增依赖；不读DB、HTTP、墙钟或随机数。

### 2.1 与docs/06的差异：fluid-v2目标库存（成员B决定直接替换v1）

**为什么改。** docs/06的v1目标`T = clip(floor(max(0, B−R+S)+0.5), 0, capacity)`只看窗口内借还的总量，不看先后顺序；docs/06自身也注明“不保证窗口每时刻无缺车”。早晚高峰典型的“先借后还”站点会被误判。反例（已写成测试`test_borrow_first_return_later_is_short`）：宿舍10辆，前10分钟20人借车，第25分钟20辆还回。v1得T=20−20+5=5<10，判为可调出5辆，但第5分钟即空站；v2判为缺18辆。

**改了什么。**

1. 预测（`forecast.py`）额外记录每站“需求水位曲线”的最低点`min_level`：
   - 起点 = `stock + reserved_inbound + 该站等待还车的车辆数`；
   - 每步 + 计划到达该站的骑行（已知在途、新骑行首次到达；**不含**满站改道转来的车），− 该站潜在借车量B（不受库存限制，可为负）；
   - 运输到货不再加（预留已计入起点，与E一致）；等待车重试成功不再加（已计入起点）。
   - B、served、R的计算口径与v1完全相同，未改。
2. 每站安全库存（`supply_demand.py`）：`S_i = max(safety_stock, Q95(Poisson(B)) − B)`。Q95为泊松分布95%分位数。参数`safety_stock`保留为下限；设为0即纯泊松余量。示例：B=9→S=5；B=20→S=8；B=0→取下限。
3. 目标库存：`T = clip(floor(E + S_i − min_level + 0.5), 0, capacity)`，含义是“让窗口内最低点仍留有S_i辆，现在需要的有效库存”。
4. `E`、`supply=min(stock, max(0,E−T))`、`demand=min(capacity−stock−reserved, max(0,T−E))`不变。

**不变的东西。** 所有函数签名、DTO字段与Schema、`plan`和三种策略、批量与统计均未改；A、C、D无需改代码。`SupplyDemand.estimator_version`由`fluid-v1`改为`fluid-v2`，便于区分。

**行为差异。**
- 只进不出的站：v1常给出T=0（可调出全部库存），v2保留S_i，调出量更保守。
- 先借后还的站：v2能识别窗口中段缺车。
- 在D的campus审阅包t=0快照上：早课18号宿舍楼v1判缺6辆、v2判缺10辆；其余三场景两者均无缺车站。

**需要他人跟进。** docs/06“供需”一节与`contracts/examples/supply_demand.json`中的`fluid-v1`需由E/F按本节更新；B未修改他人文件。若E不同意替换，可回退到提交`30be90c`的`supply_demand.py`/`forecast.py`。

## 3 安装与复现

```powershell
# 工作目录：仓库根目录（干净clone后 git switch feat/b-dispatch）
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe -m pytest backend/tests/owner_b          # B模块测试
.\.venv\Scripts\python.exe -m pytest backend/tests tests/integration # 常规全量
.\.venv\Scripts\python.exe scripts/check_baseline.py
```

本机实际执行环境为macOS、Python 3.15.0、networkx 3.4.2，命令等价为`.venv/bin/python -m pytest ...`。无服务启动、无数据库。

## 4 验收证据

|AC/T编号|输入及前置条件|操作或命令|预期结果|实际结果|证据路径|
|---|---|---|---|---|---|
|AC-B01/T07|空站且OD率>0；已知在途骑行；运输任务；等待车辆；满站；倍率；窗口截断；先借后还|`pytest backend/tests/owner_b/test_forecast.py`|空站B>0、served=0且不产生还车；在途一次入队；运输入库不计R；窗口外到达不计；输入不变、两次结果相同；水位最低点正确且不含改道车|通过（21项）|`test_forecast.py`：`test_empty_station_keeps_potential_demand`、`test_known_rides_counted_once_and_window_cutoff`、`test_transport_adds_stock_but_not_return`、`test_borrow_first_return_later_is_short`、`test_min_level_tracks_lowest_point`、`test_deterministic_and_does_not_mutate_inputs`等|
|AC-B02/T07/T12|fluid-v2口径：泊松分位数查表；S_i下限；T的半数、负最低点、超过capacity、已有reserved样例|`pytest backend/tests/owner_b/test_supply_demand.py`|T非负半数向上取整并clip；supply≤stock，demand≤可用容量；served≤B；同站不同时有supply和demand|通过（33项，手算基准表；泊松分位数另用直接求和CDF核对）|`test_supply_demand.py`|
|AC-B03/T08|200组随机小图（1～3源、1～3汇、约20%不可达、非整数米与并列距离、预算0/1/2/3/5/50）；预算0、无供需、全不可达、并列最优|`pytest backend/tests/owner_b/test_strategies.py`|min_cost_flow的(调度量,整数米费用)等于独立穷举最优；预算不超；报告原始米；none空；贪心可行、可复现且不优于最优|通过（417项）；200组中贪心有4组调度量更少、3组同量但费用更高，证明对照有效|`test_strategies.py`：`test_min_cost_flow_matches_brute_force`、`test_greedy_is_not_globally_optimal`、`test_greedy_can_move_fewer_bikes`|
|AC-B04/T12|2场景×3算法×2种子=12项，run_once替身指定1项抛错；null与单样本统计|`pytest backend/tests/owner_b/test_runner.py`|每项恰好执行一次、顺序稳定；失败项error且run_id=null；后续继续；finished=12；partial_failed；每项重建RunSpec；null排除，n<2标准差null|通过（23项）；另验证默认4×3×5=60组合与12组汇总|`test_runner.py`：`test_twelve_items_one_failure_continues`、`test_each_spec_is_rebuilt_and_schema_valid`、`test_null_excluded_not_treated_as_zero`|

- 测试总数、通过、失败、未执行：owner_b 494项，494通过，0失败；常规全量`backend/tests tests/integration` 526通过；`check_baseline.py` OK；scaffold显式运行2通过。
- 使用的Mock/替身：`tests.support.doubles.NetworkStub`（显式给出路线）、测试内`FakeRunOnce`（记录RunSpec、指定组合抛错）。生产代码未导入任何替身。
- 尚未接入的真实依赖：A的引擎与`run_once`；E集成环境中的真实NetworkService。
- 补充（非验收证据）：在D分支`origin/feat/d-map`的`data/campus/profile-review`审阅包（14站、290辆）上，用D的NetworkService对t=0初始快照试算estimate与两种策略，全部正常返回，单次预测约1ms、规划<1ms。该数据为draft，未作为验收依据。
- 以上均为模块级检查，不等于P0系统通过。

## 5 依赖与集成

- 需要接收者提供：A提供`run_once(RunSpec)->RunOutcome`与在调度时刻调用estimate/plan；D提供`NetworkService.route`。
- 契约提案：无字段或签名改动。供需计算口径改为fluid-v2（第2.1节），需E确认并由E/F同步docs/06与示例；其他待确认事项见第6节，尚未提交requests文件。
- Mock切换真实依赖：生产代码只依赖端口协议，A直接传入真实`NetworkService`实例与`run_once`即可，无需修改B代码。
- 合并与复验顺序：B不依赖A/D代码即可合并；真实闭环需A合入后由E执行AC-A04、AC-E03。
- DB/数据变化：无。

## 6 限制与未完成项

|问题|复现|影响|责任人|下一步|
|---|---|---|---|---|
|供需口径偏离docs/06（fluid-v2）|第2.1节|docs/06与`contracts/examples/supply_demand.json`仍写v1；读文档的人会与实现不一致|E/F|E确认后更新docs/06“供需”一节与示例；不同意则回退`30be90c`|
|v2未考虑满站上限|需求水位只看最低点；调入车辆可能使窗口后段超容量引发改道|缺车与满站冲突时优先避免缺车|B|正式实验若满站时长明显上升再评估|
|泊松余量只考虑借车波动|`safety_buffer`只用B，不含还车波动；服务水平固定95%|余量可能偏小或偏大|B|论文中说明；可做服务水平敏感性分析|
|未与真实引擎闭环|A尚未推送引擎|预测规则与引擎实现一致性未经实测|A/E|A合入后E用真实run_once复验AC-A04/E03|
|满站等待车重试时是否也改道，docs未明确|`forecast.py` `_try_return`|B实现为重试时与到达相同：原站无位则按(distance,id)改道，无候选继续等待；若引擎只在原站重试则预测略有偏差|A/B|按A实际实现对齐|
|骑行到达取整的浮点处理|`travel_steps_sec`用`round(秒/step, 9)`后ceil|若引擎直接ceil，恰好整步的距离可能相差一步|A/B|联调时核对同一距离两边结果|
|贪心输出顺序|`strategies.to_plan_items`|B按(source_id,destination_id)排序，与min_cost_flow一致；docs只要求min_cost_flow排序|E|确认后如需改为分配顺序，仅改一行|
|批量组合嵌套顺序与默认错误码|`runner.py`|B按场景→算法→种子；异常无code时用`RUN_FAILED`|E|确认|
|OD不可达时estimate报错|`test_unreachable_od_raises`|正常数据不会出现；若出现则该次调度失败而非静默忽略|D/E|正式数据保证所有OD可达|
|校园draft数据需求偏低|D审阅包四场景120分钟期望借车约47～145次，对290辆车，t=0仅早课1站缺车（v1、v2均如此）|三策略实验差异可能不明显|D/B|与D讨论提高高峰OD率或降低初始车辆后再跑正式实验|
|60组正式实验|需真实引擎|论文实验结果暂无|E/B|集成后执行，B提供汇总与图表|

## 7 给F的文档素材

- **预测模型（库存约束流体期望推演）**：从当前快照出发，以step为单位推演horizon窗口（默认30分钟，截断到场景终点）。每步按引擎顺序处理：运输到达→骑行到达→此前等待重试→本步借车。OD借车量按`rate_per_min×∫倍率dt/60`积分；同一起点多条OD按潜在需求比例分享库存。分别累计潜在借车B（不论有无车）、受库存限制的预计借出served、窗口内实际归还R。只有served产生未来骑行，因而空站不会被误判为低需求。满站按(道路距离,id)改道，车辆可按小数拆分，无空位则等待。运输到货影响库存与预留但不计R。
- **需求水位曲线（fluid-v2）**：推演时同时记录每站“若想借的人都能借到”的库存走势：起点为当前有效库存加等待车辆，每步加上计划到达的骑行、减去潜在借车。曲线最低点为负即表示窗口内会缺车。
- **局限**：这是确定性流体期望近似，不是随机过程的精确期望，需求波动只通过泊松安全余量近似；不预测之后的调度；不读取未来真实请求；目标只防缺车，未同时约束满站。
- **供需公式（fluid-v2）**：`S_i=max(safety_stock, Q95(Poisson(B))−B)`；`T=clip(floor(E+S_i−min_level+0.5),0,capacity)`；`E=stock+reserved_inbound`；`supply=min(stock,max(0,E−T))`；`demand=min(capacity−stock−reserved_inbound,max(0,T−E))`；safety_stock默认5。
- **改进动机与对比（可作为论文创新点）**：docs/06原公式`T=B−R+S`只看窗口总量，对“先借后还”的站会误判（宿舍10辆、前10分钟借20、第25分钟还20：原公式判可调出5辆，实际第5分钟空站；新公式判缺18辆）。泊松余量让需求大的站多留车、需求小的站少留车。真实效果需正式实验中v1/v2对比验证，目前没有该实验结果，不得引用为结论。
- **最小费用流模型**：节点为超级源、源汇总点、供给站、需求站、汇点；边容量依次为预算max_dispatch、各站supply、不限、各站demand；供给→需求边费用为`floor(distance_m+0.5)`整数米。先用`maximum_flow_value`求最大调度量F，再令超级源需求−F、汇点+F，用`network_simplex`求最小费用。最优性针对整数费用模型，报告成本用原始米数。
- **贪心**：按(距离,源id,目的id)升序逐对分配min(剩余供给,剩余需求,剩余预算)。两个反例可直接用于论文：①两供两需，贪心1100辆·米，最小费用流400辆·米；②某对不可达时贪心只调1辆，最小费用流调2辆（`test_strategies.py`）。
- **统计口径**：每(场景,策略)组每指标输出mean、样本标准差（n−1）和有效n；失败项和null值不计入，n<2时标准差为null。
- 真实截图/图表：尚无正式实验结果，不得引用。
- 实际贡献：B模块全部代码与测试由成员B完成（AI辅助编写，成员B审阅），无团队评分内容。

## 8 E接收结论

- 复验基线/提交与实际命令：提交 `7186c686c7085318faa08ba09993b0b582facbdd`；合并后在 `integrate/abcd-20261127` 执行 `pytest backend/tests/owner_b`、`pytest tests/acceptance -m acceptance`、campus 120 组正式批次。
- 通过/失败项、证据路径：B 模块 494 项通过；真实 campus 批量 120/120 成功，聚合均值/样本标准差/有效 n 正常，调度量与非零成本真实产生（[experiments-120.md](../../integration/results/experiments-120.md)）。`test_default_sixty_combinations` 因 E 按 8 场景/120 组更新 `contracts/examples/batch_request.json` 而失效。
- 结论：accepted（1 项示例组合数断言经用户授权由 E 更新为 120 后复验通过；算法与统计未改）。
- 退回负责人、修复要求、复验结果：无退回。E 仅将 `test_default_sixty_combinations` 更新为按公共示例计算 120 组/24 聚合组（已重命名为 `test_default_formal_combinations`），原因见 `docs/integration/results/integration-20261127.md` 第 3 节。
- docs/integration/results中的综合记录路径：`docs/integration/results/integration-20261127.md`、`docs/integration/results/experiments-120.md`。
