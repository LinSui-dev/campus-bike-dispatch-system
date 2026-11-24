# 成员A任务书 后端与仿真

你是成员A的智能体。先读README、AGENTS、00、10、11和自己的任务书，再读02、03、04、05、07、09、13、contracts。仅P0，无扩展或时间计划。使用独立分支与可写目录。

## 范围与禁止事项

backend/app/api、models、services、engine、main.py、app/__init__.py；backend运行配置和两份requirements；backend/tests/owner_a。具体例外以10为准。

只改自己拥有的范围，契约疑问新增docs/integration/requests/A-主题.md交E，不直接改别人代码。可在docs/handoffs/A/写自己的报告。公共定义以contracts、业务设计与13为准。

## 从开工到交接的步骤

下列是本模块内部执行路径，不要求其他成员按顺序等待。可以穿插测试，但每步交付必须可核验。

|步骤|工作|具体动作|该步产物|
|---|---|---|---|
|1|准备与依赖注入|确认1.1.0契约，建立本模块单元目录；用NetworkStub和DispatchStub注入，不调用D/B尚未实现的占位入口。|可独立创建Engine测试实例的工厂、显式小图和快照构造。|
|2|配置与持久化|实现应用工厂、配置校验、幂等默认导入、SQLAlchemy表和事务；测试使用临时DB。StationCreate/Patch按07交D标准化，独立阶段注入标准化替身。|站点/场景/OD/Config CRUD、冻结限制与引用错误测试。|
|3|确定性引擎|按05实现生成器、cursor、借车、到达、改道等待和指标；每阶段守恒，终点只处理到达。|固定种子请求与无调度闭环、边界和守恒证据。|
|4|调度执行与控制|接收计划后整批重校验、扣减预留、任务到货和幂等；实现pause/resume/stop/reset/speed及命令日志。|库存预留闭环、重置保存/舍弃、保存失败重试。|
|5|单槽与Web接口|运行管理器串行命令/step，交互与批量互斥；实现REST/WS、seq、State.context和刷新恢复。|全部07路由、统一错误、活动元信息；未完成仍明确501。|
|6|提供批量执行端口|实现run_once(RunSpec)→RunOutcome，独立重建并执行保存；由B控制组合，A管理全局槽、进度和持久化。|可注入ExperimentRunner的真实回调，不让B接触DB。|
|7|真实联调与交接|E集成D/B后以真实服务替换替身，复验API与保存；将模块范围、命令和素材写handoff。|向E交ready报告；未就绪的跨模块AC明确pending，不冒充系统通过。|

## 验收与命令

AC-A01～AC-A08（主责），配合AC-C02、AC-E01～AC-E03；对应FR02～FR06、FR09～FR11。

以下命令在本人的项目根目录执行，依赖安装见README/11；服务运行以Ctrl+C停止，数据库必须本目录独立或测试临时目录。

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/owner_a
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --port 8000
```

模块测试无失败，覆盖A的各AC；真实API和保存必须由E验收。命令首次无测试退出5表示尚未完成，不可填通过。

每个AC填写输入、操作、预期、实际与证据，失败和未执行如实记录；不以Mock或类型构建通过代替真实系统验收。按范围分批交接允许，但不能省略剩余P0。

## 必须交出的handoff

向B提供run_once使用例，向C提供OpenAPI和刷新/错误示例；向E提供临时DB初始化、服务停止方式、替身切换点、事务与守恒证据；给F引擎和架构说明。

复制docs/handoffs/TEMPLATE.md到自己的目录。先draft，自测达到本次AC后ready；E复验填accepted或returned。退回只修自己范围，更新同一报告并再次交接；新代码不得沿用旧验收结论。给F的材料来自真实实现与执行结果。
