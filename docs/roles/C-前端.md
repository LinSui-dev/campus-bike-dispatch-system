# 成员C任务书 前端

你是成员C的智能体。先读README、AGENTS、00、10、11和自己的任务书，再读04、07、08、09、13、contracts。仅P0，无扩展或时间计划。使用独立分支与可写目录。

## 范围与禁止事项

frontend全部，包括package-lock、配置、src/types、src/mocks。不得改后端或公共Schema。

只改自己拥有的范围，契约疑问新增docs/integration/requests/C-主题.md交E，不直接改别人代码。可在docs/handoffs/C/写自己的报告。公共定义以contracts、业务设计与13为准。

## 从开工到交接的步骤

下列是本模块内部执行路径，不要求其他成员按顺序等待。可以穿插测试，但每步交付必须可核验。

|步骤|工作|具体动作|该步产物|
|---|---|---|---|
|1|建立客户端与Mock|从1.1.0 Schema建立TS类型、REST错误封装、请求ID、Pinia和导航；实现显式Mock模式。Mock包含idle/running/paused/completed/失败与断线状态。|后端未实现时五页面可独立操作，醒目标识虚拟联调。|
|2|地图和站点|Leaflet四层、坐标转换、列表联动、选址拖动和CRUD；发送StationCreate/Patch，接受后端标准化响应。|道路默认隐藏、标记状态文字、拖动与错误回退。|
|3|配置与控制|场景/OD/时段/Config表单和校验，开始暂停继续停止倍速重置；busy禁结构编辑，reset三选项。|不自动开始，取消reset不发请求，重试沿用request_id。|
|4|总览与调度|指标/趋势/校区库存、供需、任务表和道路路线；运输进度跟sim_time，暂停动画不前进。|none空任务、无数据/零分母null、库存不由UI修改。|
|5|实验与历史|批量组合预览、进度、失败项、历史详情、策略均值/标准差/有效n；不做导出。|四场景三策略五种子组合可配置，历史与当前分开。|
|6|恢复与真实API|按07恢复runtime/WS/State.context，断线seq去旧与轮询；Mock关闭后接真实A/D，不能失败时偷偷回退Mock。|刷新恢复场景种子倍速；页面切换不停后端。|
|7|验收交接|执行构建和C的逐项人工验收，标注使用Mock或真实API；交E复验并给F截图。|每个页面入口、步骤、预期与截图进入handoff。|

## 验收与命令

AC-C01～AC-C04主责，配合AC-A01、AC-D03；对应FR01～FR04、FR06、FR09、FR10。

以下命令在本人的项目根目录执行，依赖安装见README/11；服务运行以Ctrl+C停止，数据库必须本目录独立或测试临时目录。

```powershell
npm --prefix frontend ci
npm --prefix frontend run build
npm --prefix frontend run dev
```

构建成功只是必要条件，C的五页面和恢复/异常人工AC必须逐项记录。正式AC禁Mock，只有Mock阶段通过的项标为模块通过、系统待验收。

每个AC填写输入、操作、预期、实际与证据，失败和未执行如实记录；不以Mock或类型构建通过代替真实系统验收。按范围分批交接允许，但不能省略剩余P0。

## 必须交出的handoff

给E页面路径、Mock开关及状态切换方式、真实API配置、刷新断线复现、浏览器与截图；给F五页面与地图真实画面及单位说明。

复制docs/handoffs/TEMPLATE.md到自己的目录。先draft，自测达到本次AC后ready；E复验填accepted或returned。退回只修自己范围，更新同一报告并再次交接；新代码不得沿用旧验收结论。给F的材料来自真实实现与执行结果。
