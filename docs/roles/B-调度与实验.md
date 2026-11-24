# 成员B任务书 调度与实验

你是成员B的智能体。先读README、AGENTS、00、10、11和自己的任务书，再读02、05、06、07、09、13、contracts。仅P0，无扩展或时间计划。使用独立分支与可写目录。

## 范围与禁止事项

backend/app/dispatch、experiments；backend/tests/owner_b。不得直接改Engine、DB、requirements或公共契约。

只改自己拥有的范围，契约疑问新增docs/integration/requests/B-主题.md交E，不直接改别人代码。可在docs/handoffs/B/写自己的报告。公共定义以contracts、业务设计与13为准。

## 从开工到交接的步骤

下列是本模块内部执行路径，不要求其他成员按顺序等待。可以穿插测试，但每步交付必须可核验。

|步骤|工作|具体动作|该步产物|
|---|---|---|---|
|1|搭建纯函数测试环境|从examples读取State/Params，构建NetworkStub和回调替身；所有函数不得读DB、墙钟或隐藏事件列表。|可独立调用estimate、plan、run_batch的测试。|
|2|实现期望预测|按06分别累计潜在需求和实际可借出，处理已知骑行、等待、运输与预留；避免重算当前桶与重复在途。|空站仍有潜在需求、实际借出受限、无未来泄漏测试。|
|3|实现供需|统一半数向上取整、T/E/supply/demand，验证容量、零窗口及不可达。|Schema合规SupplyDemand与边界样例。|
|4|实现三策略|none空计划；贪心稳定排序；最小费用流先最大量再最小整数成本，稳定插图并输出排序。|最大量、预算和整数费用对穷举样例一致。|
|5|实现批量和统计|组合按输入顺序、重复拒绝、逐项回调，单失败继续，null排除和样本标准差；run_once由A注入。|可验证组合和失败项的独立实验Runner，不写DB。|
|6|接入真实依赖|交A公开入口与构造；E集成后调用真实NetworkService/run_once，检查每次重建状态、需求共用规则和运输成本。|真实闭环检查，模型近似和算法局限明确。|
|7|交接|按模板记录全部入口、计算测试、运行组合、局限、版本与给F的公式素材。|向A/E交ready；尚无正式实验不写优胜结果。|

## 验收与命令

AC-B01～AC-B04主责，配合AC-A04和AC-E03；对应FR07、FR08、FR10。

以下命令在本人的项目根目录执行，依赖安装见README/11；服务运行以Ctrl+C停止，数据库必须本目录独立或测试临时目录。

```powershell
.\.venv\Scripts\python.exe -m pytest backend/tests/owner_b
```

纯计算不改输入，不访问未来事件或DB；B的AC通过。小样例穷举证明优化口径，不能只用自写算法输出验证自身。

每个AC填写输入、操作、预期、实际与证据，失败和未执行如实记录；不以Mock或类型构建通过代替真实系统验收。按范围分批交接允许，但不能省略剩余P0。

## 必须交出的handoff

给A estimate/plan/Runner最小调用与异常约定；给E穷举基准、回调替身、批量失败和统计证据；给F预测近似、目标公式与整数成本说明。

复制docs/handoffs/TEMPLATE.md到自己的目录。先draft，自测达到本次AC后ready；E复验填accepted或returned。退回只修自己范围，更新同一报告并再次交接；新代码不得沿用旧验收结论。给F的材料来自真实实现与执行结果。

## 完成后提交到远程分支

你的固定交付分支为`feat/b-dispatch`，对应https://github.com/LinSui-dev/campus-bike-dispatch-system/tree/feat/b-dispatch。开工按11从origin/main创建同名本地分支；已经存在则切换并继续，不重复创建、不在main开发。

完成本次范围后：执行上面的自测与AC → 只暂存本人文件并提交代码 → 同步main并复验 → 填写docs/handoffs/B/报告、记录被测代码SHA并提交报告 → 推送本人分支 → 核对远程SHA → 将分支链接、远程HEAD、被测SHA、报告路径和实际结果交E。完整提交/冲突/核验步骤见11，不跳过handoff或把本地提交当作远程交接。

```powershell
if ((git branch --show-current) -ne 'feat/b-dispatch') { throw 'Switch to your assigned role branch first.' }
git status --short
# 确认本次代码、证据和报告已提交后再推送
git push -u origin feat/b-dispatch
if ($LASTEXITCODE -ne 0) { throw 'Push failed; do not report success.' }
git rev-parse HEAD
git ls-remote origin refs/heads/feat/b-dispatch
# 对照本地和远程SHA必须一致；完整自动核验片段见11
```

用户已授权向本人的该分支推送成果，无需完成后再次询问个人分支推送许可。不得把个人交付直接推main、强推或覆盖其他人的分支。退回修复继续提交到同一分支，更新报告后重新交接。draft备份可推送但不能宣称ready；main集成仍由E按验收流程执行。
