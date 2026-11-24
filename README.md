# 校园共享单车智能调度与可视化仿真系统

北京交通大学主校区与东校区共享单车课程项目，以软件仿真和平台原型比较无调度、贪心、最小费用流，不接真实运营商。

## 当前状态

已提供六人并行开发文档、v1公共契约、虚拟测试数据、后端与前端启动骨架、验证脚本和CI。**业务功能尚未实现，正式校园地图和调查数据尚未提交。** 骨架数据不是仿真结果。

分发契约为1.1.0。完整步骤见个人任务书；逐项完成标准见[验收矩阵](docs/13-验收矩阵.md)，交接按[handoff模板](docs/handoffs/TEMPLATE.md)。文件归属以10中的唯一表为准。

先读[开发入口](docs/00-开发入口.md)、[六人分工](docs/10-团队分工与开发计划.md)及自己的[任务书](docs/roles)。仅P0，不做扩展和时间计划。

共享仓库：[LinSui-dev/campus-bike-dispatch-system](https://github.com/LinSui-dev/campus-bike-dispatch-system)。各成员分别clone，再建立自己的工作分支，不共享可写目录：

```powershell
git clone https://github.com/LinSui-dev/campus-bike-dispatch-system.git
cd campus-bike-dispatch-system
# 将A示例分支替换为自己的角色分支，见docs/11
git switch -c feat/a-engine
```

## 目录

`backend/app` 后端与独立引擎；`frontend` Vue；`contracts` 公共契约与Mock；`data/fixtures` 虚拟夹具；`data/campus` 正式数据；`tests/integration` 公共测试；`scripts` 检查；`docs/roles` 六份智能体任务书。

## 启动（PowerShell，根目录）

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r backend/requirements-lock.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir backend --reload --port 8000
```

另开终端：

```powershell
cd frontend
npm ci
npm run dev
```

页面 http://localhost:5173 ，API文档 http://localhost:8000/docs 。Vite代理/api、/assets、/ws到8000。当前只有健康检查、开发元信息、虚拟地图资源API，其余明确501。

## 检查

```powershell
python scripts/check_baseline.py
.\.venv\Scripts\python.exe -m pytest backend/tests tests/integration
npm --prefix frontend run build
```

基线检查不是P0验收，业务验收见09。共享基线由本次授权提交建立；成员直接从上述远端获取，E继续维护契约、测试与串行集成。禁止多人在相同可写目录开发。

当前补齐后的检查结果及限制见[补齐复核验证](docs/integration/results/补齐复核验证.md)，初始过程保留于[基线验证记录](docs/integration/results/基线验证.md)。

常规门禁运行`scripts/check.ps1`，只证明开发基建与当前测试通过；骨架诊断单独运行`.venv\Scripts\python.exe -m pytest tests/scaffold -m scaffold`，不要求业务实现后继续返回501。正式门禁为`scripts/check.ps1 -Acceptance`，业务测试为空或最终AC证据不齐时必须失败，不能据常规绿灯宣称P0完成。
