# 成员E任务书 联调测试与基建

你是成员E的智能体。先读README、AGENTS、00、10、11和自己的任务书，再读全部文档与contracts，重点09～13、contracts。仅P0，无扩展或时间计划。使用独立分支与可写目录。

## 范围与禁止事项

contracts、scripts、根tests、.github、AGENTS、.gitignore、pytest.ini等根配置、docs/integration/results。可填写各handoff第8节，不改其他正文或业务实现。

只改自己拥有的范围，契约疑问新增docs/integration/requests/E-主题.md交E，不直接改别人代码。可在docs/handoffs/E/写自己的报告。公共定义以contracts、业务设计与13为准。

## 从开工到交接的步骤

下列是本模块内部执行路径，不要求其他成员按顺序等待。可以穿插测试，但每步交付必须可核验。

|步骤|工作|具体动作|该步产物|
|---|---|---|---|
|1|建立共享基线|按11确认忽略规则、初始化Git与基线，团队给地址后建远端；帮助各人独立clone/worktree和依赖。|共享SHA、分支工作目录和可执行检查入口；不规定业务成员先后。|
|2|维护契约与样例|验证1.1.0 Schema、字段语义、端口、站点写入和恢复上下文；受理提案，协调机器契约和F文档同步。|契约/示例检查与兼容结论。|
|3|建立真实验收框架|按13在tests/acceptance增加实际测试，标acceptance；与A建立应用工厂、临时DB、fixture profile、独立生命周期。|不污染真实DB，验收空集失败；骨架测试独立。|
|4|并行收件与集成|检查ready交接的范围、所有权、SHA和模块测试；在干净集成目录串行合并，执行相关AC，退回失败给所有者。|各报告第8节和integration/results实际证据。|
|5|系统和人工验收|使用真实A/B/D与C，关闭Mock，检查五页面、刷新断线、单槽、保存/舍弃/异常、正式地图。|真实端到端与人工清单，不用baseline代替。|
|6|执行正式实验|先小组合再60组，核对版本请求与初始条件、失败项和统计；不预设胜负。|可查询历史、图表、有效n和真实实验记录。|
|7|课程交付核对|核对F的论文PPT、来源、版本、页码讲述人与贡献依据，汇总全部P0状态。|系统最终报告和给F的证据，不越界代修业务。|

## 验收与命令

AC-E01～AC-E03主责；复验A/B/C/D全部AC，配合AC-F01/F02。

以下命令在本人的项目根目录执行，依赖安装见README/11；服务运行以Ctrl+C停止，数据库必须本目录独立或测试临时目录。

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1
.\.venv\Scripts\python.exe -m pytest tests/scaffold -m scaffold
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/check.ps1 -Acceptance
```

当前只有基建，正式命令无业务测试时应退出非零；补齐后必须无失败，AC的人工证据也齐全，不能添加占位断言凑通过。

最终按docs/integration/results/acceptance-template.json填写acceptance.json：实际被测完整SHA、1.1.0或当时有效契约版本、24项真实状态/复验者/结果/证据路径。先测代码提交，再单独提交报告即可，不伪造自引用SHA。人工项未完成时保持pending，不能宣称系统通过。

每个AC填写输入、操作、预期、实际与证据，失败和未执行如实记录；不以Mock或类型构建通过代替真实系统验收。按范围分批交接允许，但不能省略剩余P0。

## 必须交出的handoff

向团队交基线、契约结论、实际合并SHA、AC与FR覆盖、失败退回和复验；向F交真实实验/截图/环境与局限，自己交E目录报告。

复制docs/handoffs/TEMPLATE.md到自己的目录。先draft，自测达到本次AC后ready；E复验填accepted或returned。退回只修自己范围，更新同一报告并再次交接；新代码不得沿用旧验收结论。给F的材料来自真实实现与执行结果。
