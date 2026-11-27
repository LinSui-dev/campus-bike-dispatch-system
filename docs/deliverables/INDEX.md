# 课程交付索引（INDEX）

## 基本信息

| 项 | 值 |
|---|---|
| 项目名称 | 校园共享单车智能调度与可视化仿真系统 |
| 组号 | （待确认） |
| 成员 | A～F（真实姓名待确认） |
| 指导教师 | （待确认） |
| 方案 | 方案B（软件仿真/平台原型） |
| 契约版本 | 1.1.0 |
| 交付日期 | 2026-11-27 |

## 交付文件清单

| 文件 | 说明 | 状态 |
|---|---|---|
| `source/论文.docx` | 论文可编辑源（32页） | ready |
| `source/答辩PPT.pptx` | 答辩PPT可编辑源（23页） | ready |
| `final/论文.docx` / `final/论文.pdf` | 论文核验版与渲染 | ready |
| `final/答辩PPT.pptx` / `final/答辩PPT.pdf` | PPT核验版与渲染 | ready |
| `source/figures/*.png` | 实验图表（真实数据生成） | ready |
| `source/课程检查表.md` | 课程要求自检 | ready |
| `source/来源索引.md` | 素材与证据来源 | ready |
| `source/运行说明.md` | 安装与运行说明 | ready |
| `tools/*.py` | 论文/PPT/图表生成脚本 | ready |

## 验证记录

| 项 | 命令/工具 | 结果 |
|---|---|---|
| 论文字数/页数 | Word COM ComputeStatistics | 32 页，12123 字符 |
| 摘要字数 | 程序计数 | 199 字（≤200） |
| PPT 页数 | PowerPoint COM Slides.Count | 23 页 |
| 图表来源 | `batch-120-result.json` 生成 | 真实数据 |
| 事实核对 | 引用 `docs/integration/results/*` | 与E结果一致 |

## 实际贡献依据

| 成员 | 实际贡献 | 依据 |
|---|---|---|
| A | 后端引擎、运行管理、持久化、REST/WS、67项测试 | `docs/handoffs/A/后端与仿真交接.md` |
| B | 预测fluid-v2、三策略、批量统计、494项测试 | `docs/handoffs/B/dispatch-experiments.md` |
| C | 前端五页面、地图交互、客户端、Mock、浏览器套件 | `docs/handoffs/C/frontend.md` |
| D | 底图、路网、14站、八场景、路网服务、21项测试 | `docs/handoffs/D/network-map.md` |
| E | 契约、真实集成、7项验收、120组实验、五页面证据 | `docs/handoffs/E/E-integration.md` |
| F | 论文、答辩PPT、运行说明、来源索引、课程检查表 | 本目录 |

## 待确认项（不虚构）

- 组号、成员姓名、院系、指导教师。
- 团队评分与贡献比例（满分100评分表已建结构，分值留空）。

## 真实性声明

- 论文/PPT引用的实验结果全部来自E已核验的 `docs/integration/results/experiments-120.md` 与原始JSON。
- 需求率为课程合成参数，非实测调查；部分道路边长经比例估算；均已在论文中如实说明。
- 未预填实验结论、测试通过数或贡献评分。
