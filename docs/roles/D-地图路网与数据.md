# 成员D任务书 地图路网与数据

你是成员D的智能体。先读README、AGENTS、00、10、11和自己的任务书，再读03、04、05、07、09、13及data/README、contracts。仅P0，无扩展或时间计划。使用独立分支与可写目录。

## 范围与禁止事项

backend/app/network、backend/tests/owner_d、data全部。不得修改A的API或B的优化。

只改自己拥有的范围，契约疑问新增docs/integration/requests/D-主题.md交E，不直接改别人代码。可在docs/handoffs/D/写自己的报告。公共定义以contracts、业务设计与13为准。

## 从开工到交接的步骤

下列是本模块内部执行路径，不要求其他成员按顺序等待。可以穿插测试，但每步交付必须可核验。

|步骤|工作|具体动作|该步产物|
|---|---|---|---|
|1|资料与小图分离|保留fixtures虚拟标识，收集手绘校园原图和来源；先用小图开发，正式素材没有时如实标缺。|数据清单、来源状态和测试图。|
|2|路网加载校验|校验节点边ID、端点、正长、折线、坐标和连接；NetworkService仅接JSON与站点，不读DB。|非法数据拒绝、无向图和缓存。|
|3|站点投影和拆边|StationCreate投影输出Station；同边按offset/id拆分、端点复用、同位置零距离、更新排除旧接入点。|明确容差、越界/不可达错误和输入不变测试。|
|4|路径与距离|Dijkstra按米权重、按方向返回完整折线；保留原始边ID，重建后缓存失效。|同校/跨校/反向/不可达与多站测试。|
|5|正式底图与数据|按data/README组织校园底图、路网、12站、四场景OD、默认Config和metadata。记录测距依据、授权状态、合成率假设。|campus完整文件，无AI/夹具冒充实测。|
|6|真实接入|交A构造与错误映射、交B route、交C图像和坐标；E验证唯一跨校区链、站点可达与数据profile。|正式数据核验报告及真实集成结果。|
|7|交接|分别说明路网代码和正式素材是否完成；可先交代码，正式数据仍待验收。|向A/B/C/E交ready范围，给F来源与地图说明。|

## 验收与命令

AC-D01～AC-D03主责，配合AC-A01、AC-C03；对应FR01～FR03和路网支撑FR05/FR09。

以下命令在本人的项目根目录执行，依赖安装见README/11；服务运行以Ctrl+C停止，数据库必须本目录独立或测试临时目录。

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/owner_d
python scripts/check_baseline.py
```

路径/投影AC通过后可交代码；正式素材齐全并通过D03才可宣称校园数据完成。现有baseline只检查fixture，不自动证明campus有效。

每个AC填写输入、操作、预期、实际与证据，失败和未执行如实记录；不以Mock或类型构建通过代替真实系统验收。按范围分批交接允许，但不能省略剩余P0。

## 必须交出的handoff

给A输入输出与错误例、给B距离折线、给Cmetadata/底图/坐标；给E两种profile验证命令、长度与来源；给F地图和合成数据说明。

复制docs/handoffs/TEMPLATE.md到自己的目录。先draft，自测达到本次AC后ready；E复验填accepted或returned。退回只修自己范围，更新同一报告并再次交接；新代码不得沿用旧验收结论。给F的材料来自真实实现与执行结果。
