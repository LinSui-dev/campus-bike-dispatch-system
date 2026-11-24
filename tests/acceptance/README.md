# 正式业务验收入口

E在此新增test_*.py，使用@pytest.mark.acceptance标注；本目录当前没有已实现的业务验收测试。以docs/13-验收矩阵.md为依据，真实模块、临时数据库、fixture与正式数据分组，不依赖Mock冒充完整集成。

正式命令：`.venv\Scripts\python.exe -m pytest tests/acceptance -m acceptance`。无测试时pytest退出码5，必须视为“尚未建立验收”，不得通过添加占位断言或使用空测试绕过。scripts/check.ps1 -Acceptance会在常规门禁之后执行本命令，E补齐验收后才可通过。

A/B/D修正各自业务，C修正前端，E修改本目录并验收；单元测试通过不能替代本层。

正式业务自动测试通过后，还需E填写docs/integration/results/acceptance.json中的24项真实自动/人工证据；正式脚本随后调用scripts/check_acceptance.py，材料不齐仍失败。当前仅有pending模板，未创建最终报告。
