# -*- coding: utf-8 -*-
"""生成论文 docx（按附件2论文版面示例的字体与版式，≥30页）。

正文内容来自仓库已核验的设计文档与 E 的真实实验结果，
不虚构结果、贡献或引用。作者/组号/评分未确认处明确标注。
"""
import json
from pathlib import Path

from docx import Document
from docx.shared import Pt, Cm
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "docs/deliverables/source/figures"
UI = ROOT / "docs/integration/results/evidence/ui"
RESULT = ROOT / "docs/integration/results/evidence/experiments/batch-120-result.json"
ACJSON = ROOT / "docs/integration/results/acceptance.json"
STATIONS = ROOT / "data/campus/default_stations.json"
SCENARIOS = ROOT / "data/campus/scenarios.json"
MAP_PNG = ROOT / "data/campus/campus_map.png"
OUT = ROOT / "docs/deliverables/source/论文.docx"

F_TITLE = "华文中宋"
F_AUTHOR = "楷体"
F_BODY = "宋体"
F_HEAD = "黑体"
F_LATIN = "Times New Roman"

DOC = Document()


def _set_font(run, ascii_font, east, size, bold=False):
    run.font.name = ascii_font
    run.font.size = Pt(size)
    run.font.bold = bold
    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.find(qn("w:rFonts"))
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), ascii_font)
    rfonts.set(qn("w:hAnsi"), ascii_font)
    rfonts.set(qn("w:eastAsia"), east)


def _spacing(p, before=0, after=0, line=1.25):
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = line


def title(text):
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _spacing(p, 0, 6, 1.0)
    _set_font(p.add_run(text), F_LATIN, F_TITLE, 16, bold=True)


def author_line(text):
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _spacing(p, 0, 0, 1.0)
    _set_font(p.add_run(text), F_LATIN, F_AUTHOR, 12)


def unit_line(text):
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _spacing(p, 0, 12, 1.0)
    _set_font(p.add_run(text), F_LATIN, F_BODY, 12)


def h1(text):
    p = DOC.add_paragraph()
    _spacing(p, 15, 15, 1.0)
    _set_font(p.add_run(text), F_LATIN, F_HEAD, 15, bold=True)


def h2(text):
    p = DOC.add_paragraph()
    _spacing(p, 7, 7, 1.0)
    _set_font(p.add_run(text), F_LATIN, F_HEAD, 14, bold=True)


def h3(text):
    p = DOC.add_paragraph()
    _spacing(p, 0, 0, 1.25)
    _set_font(p.add_run(text), F_LATIN, F_HEAD, 12, bold=True)


def para(text, indent=True):
    p = DOC.add_paragraph()
    _spacing(p, 0, 0, 1.25)
    if indent:
        p.paragraph_format.first_line_indent = Pt(24)
    _set_font(p.add_run(text), F_LATIN, F_BODY, 12)


def bullet(text):
    p = DOC.add_paragraph()
    _spacing(p, 0, 0, 1.25)
    p.paragraph_format.left_indent = Pt(24)
    _set_font(p.add_run("• " + text), F_LATIN, F_BODY, 12)


def abstract_label_and_body(label, body):
    p = DOC.add_paragraph()
    _spacing(p, 6, 0, 1.25)
    _set_font(p.add_run(label), F_LATIN, F_HEAD, 10.5, bold=True)
    _set_font(p.add_run(body), F_LATIN, F_AUTHOR, 10.5)


def caption(text):
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _spacing(p, 3, 6, 1.0)
    _set_font(p.add_run(text), F_LATIN, F_BODY, 10.5)


def figure(path, cap, width_cm=14.5):
    if not Path(path).exists():
        para(f"[图缺失：{Path(path).name}]", indent=False)
        return
    p = DOC.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _spacing(p, 6, 0, 1.0)
    p.add_run().add_picture(str(path), width=Cm(width_cm))
    caption(cap)


def table(headers, rows, font_size=10.5):
    t = DOC.add_table(rows=1, cols=len(headers))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    hdr = t.rows[0].cells
    for i, h in enumerate(headers):
        hdr[i].text = ""
        _set_font(hdr[i].paragraphs[0].add_run(h), F_LATIN, F_HEAD, font_size, bold=True)
        hdr[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    for row in rows:
        cells = t.add_row().cells
        for i, v in enumerate(row):
            cells[i].text = ""
            _set_font(cells[i].paragraphs[0].add_run(str(v)), F_LATIN, F_BODY, font_size)
            cells[i].paragraphs[0].alignment = WD_ALIGN_PARAGRAPH.CENTER
    return t


def code_block(text):
    for line in text.splitlines():
        p = DOC.add_paragraph()
        _spacing(p, 0, 0, 1.0)
        p.paragraph_format.left_indent = Pt(12)
        _set_font(p.add_run(line), "Consolas", F_LATIN, 9.5)


# ------------------------------------------------------------------ 数据
SCENARIO_CN = {
    "morning": "早课", "morning-dismissal": "上午下课", "lunch": "午餐",
    "afternoon-class": "午课", "afternoon-dismissal": "下午下课",
    "dinner": "晚餐", "evening-class": "晚课", "evening": "返寝",
}
SCENARIO_ORDER = list(SCENARIO_CN.keys())
ALGO_CN = {"none": "无调度", "greedy": "贪心", "min_cost_flow": "最小费用流"}
ALGO_ORDER = ["none", "greedy", "min_cost_flow"]

result = json.loads(RESULT.read_text(encoding="utf-8"))
agg = {(a["scenario_id"], a["algorithm"]): a["metrics"] for a in result["aggregates"]}
stations = json.loads(STATIONS.read_text(encoding="utf-8"))
scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
acjson = json.loads(ACJSON.read_text(encoding="utf-8"))


def hhmm(minute):
    return f"{minute // 60:02d}:{minute % 60:02d}"


# ------------------------------------------------------------------ 封面
title("校园共享单车智能调度与可视化仿真系统的设计与实现")
author_line("（作者姓名待确认）")
unit_line("（北京交通大学 · 院系待确认）")

abstract_label_and_body(
    "摘  要：",
    "针对高校共享单车在上下课高峰的供需时空失衡问题，本文设计并实现了一个面向主校区与东校区的校园共享单车智能调度与可视化仿真系统。系统基于双校区道路网络构建离散事件仿真引擎与库存约束需求预测模型，实现无调度、贪心、最小费用流三种调度策略，并提供五页面交互与可视化。基于八个场景、三种策略、五个种子的120组对照实验表明，调度策略显著提升借车成功率。系统采用合成需求数据，作为仿真教学与算法比较的原型。"
)
abstract_label_and_body(
    "关键词：",
    "共享单车；智能调度；离散事件仿真；最小费用流；需求预测；数据可视化"
)

# ------------------------------------------------------------------ 一、绪论
h1("一、绪论")
h2("（一）研究背景与意义")
para("共享单车作为解决城市“最后一公里”出行的重要手段，凭借无桩化、低成本与灵活性，在高校校园中得到了广泛应用。北京交通大学主校区与东校区之间，教学区、宿舍区与食堂的空间分布带来明显的潮汐式出行特征：上课时段出行需求由宿舍区涌向教学区，下课与就餐时段又沿相反方向回流，导致共享单车在时间和空间上高度不均衡——部分站点在高峰期长期缺车、部分站点则长期满溢，车辆利用率与用户体验同时下降。")
para("传统的人工调度依靠运营人员经验判断与线下搬运，成本高、响应慢，难以应对高峰期快速变化的供需波动。通过软件仿真对调度策略进行事前评估，能够在相同的需求环境下低成本地比较不同调度算法，为运营决策提供量化依据。因此，本项目选择“软件仿真或平台原型”方案（方案B），构建一个校园共享单车智能调度与可视化仿真系统，在不接入真实运营商、不涉及真实定位与支付的前提下，完成路网建模、需求生成、车辆借还、调度优化与结果可视化。")
para("本系统的意义在于：其一，为校园共享单车调度提供一个可复现、可交互、可对照的仿真平台原型；其二，通过最小费用流等精确方法为启发式算法提供可验证的基准；其三，以真实地图与合成需求相结合的半仿真方式，在课程实验尺度内演示智能调度系统的完整技术链路。")
h2("（二）国内外研究现状")
h3("1. 共享单车再平衡问题")
para("共享单车再平衡（Bike Rebalancing）是共享出行运营的核心问题之一，其目标是在满足用户借还需求的前提下，通过车辆搬运将车辆在站点间重新分配，以最小化缺车、满溢与运输成本。根据需求是否随时间演化，可将问题分为静态再平衡与动态再平衡两类：静态再平衡假设规划期内的需求已知且不变，通常建模为带容量约束的车辆路径问题或运输问题；动态再平衡则考虑需求的随机性与时间演化，模型更为复杂。")
h3("2. 求解方法")
para("在求解方法上，精确方法以整数规划与最小费用流为代表，通过构建供给—需求网络并求最小费用最大流，可获得整数费用模型下的最优解；启发式方法则包括贪心、局部搜索与元启发式等，计算效率高但通常不保证最优。现有研究多面向城市级规模与真实运营商数据，模型复杂、对数据质量要求高，难以直接复用于课程教学与小规模校园场景。")
h3("3. 本文定位")
para("与上述研究相比，本文针对校园这一小规模、强潮汐、路网明确的场景，构建一个可复现、可交互、可对照的仿真原型。重点在于以最小费用流为基准验证调度策略的有效性，并以穷举算法交叉验证最小费用流的正确性，同时如实区分合成数据与真实运营的边界，避免以仿真结果冒充真实运营结论。")
h2("（三）本文主要工作")
bullet("建立了双校区（主校区11站、东校区3站，共14站）的2.5D底图与加权无向道路网络，唯一跨校区连接为主校区南门—上园村路—东校区小西门，实现站点投影、路径计算与缓存重建。")
bullet("实现了固定种子、稳定排序、按步推进的离散事件仿真引擎，覆盖请求生成、借车、骑行、还车、满站改道与等待、整批运输与库存守恒等核心业务。")
bullet("设计并实现了库存约束的流体期望需求预测模型（fluid-v2），在不读取未来真实请求的前提下估算站点供需，并以需求水位曲线识别“先借后还”型站点。")
bullet("实现无调度、贪心、最小费用流三种调度策略，统一约束与执行口径，并以独立穷举算法验证最小费用流的最优性。")
bullet("完成了五页面的Web前端与REST/WebSocket实时可视化，支持运行控制、站点管理、手动调度与实验分析。")
bullet("在八个场景、三种策略、五个种子的120组对照实验上完成验证，并如实记录合成数据假设与模型局限。")
h2("（四）本文组织结构")
para("本文后续章节安排如下：第二章进行需求分析，界定场景、功能与非功能需求；第三章描述系统总体架构与运行管理机制；第四章阐述地图路网、仿真引擎、需求预测、调度策略、数据库与接口等关键设计；第五章说明技术选型理由；第六章介绍实现方式与测试结果；第七章给出120组对照实验及其分析；第八章总结全文并展望后续工作。")

# ------------------------------------------------------------------ 二、需求分析
h1("二、需求分析")
h2("（一）场景与范围")
para("系统面向课程实验操作者，运行于中文浅色桌面浏览器，无需登录。仅主校区、东校区以及两者之间的指定连接线参与模拟，家属区、学苑公寓等区域仅作为底图背景。默认配置为14个运营站点（主校区11个、东校区3个），总容量565辆、初始库存290辆，站点数量可编辑。")
para("本系统为软件仿真原型，不接入真实共享单车运营商，不涉及真实定位、支付、开锁与权限。需求率采用课程合成参数，不代表实测调查结果。地图底图以北交大招生办公室2025年报考指南第18页为参考，参考OpenStreetMap公开地物与道路，并按用户圈注调整，建筑外形与道路宽度经过概化。")
h2("（二）功能需求")
para("系统功能需求编号为FR01～FR11，逐项定义如下表所示。")
table(
    ["编号", "功能", "说明", "主要责任"],
    [
        ["FR01", "双校区底图与路网", "2.5D底图拖动缩放、道路层开关、指定跨校区线", "D/C"],
        ["FR02", "停车点CRUD与拖动选址", "容量库存合法、投影接入、删除关联确认", "A/C/D"],
        ["FR03", "预设与自定义场景", "OD、时段倍率可编辑保存", "A/C/D"],
        ["FR04", "运行控制", "开始、暂停、继续、结束、重置、倍速、步长、种子", "A/C"],
        ["FR05", "借还业务", "空站失败、满站改道或等待、守恒", "A"],
        ["FR06", "运营监测", "库存、缺车、满载、车辆状态、双校区统计", "A/C"],
        ["FR07", "需求估算（方案A）", "库存约束期望预测、无未来泄漏", "B"],
        ["FR08", "三策略", "无调度、贪心、最小费用流统一约束", "B"],
        ["FR09", "手动调度与执行", "运输、容量预留、路线和进度", "A/B/C"],
        ["FR10", "实验分析", "批量对照、历史、指标图表", "A/B/C"],
        ["FR11", "持久化", "配置、不可变快照、逐步指标、任务", "A"],
    ],
)
h2("（三）业务流程")
h3("1. 运行控制流程")
para("系统初始处于空闲状态，用户进入页面后仅加载配置，不自动开始运行。用户选择场景、设置参数与种子后点击开始，系统创建交互运行并占用运行槽，随后可按墙钟倍速推进仿真；运行期间可暂停、继续、调整倍速或停止。重置时弹出三种选择：保存并重置、舍弃并重置、取消，取消不发送任何请求。异常退出不创建不完整的历史记录。")
h3("2. 借还与调度流程")
para("用户借车在空站立即失败并计入失败数；有车时扣减库存、产生骑行，按道路距离与速度计算到达时间。到达满站时按道路距离选择最近的可达空位站改道，无候选则进入等待并在后续步重试。手动或预设调度触发时，系统估算站点供需、生成运输任务并预留容量，运输到期后释放预留并入库。")
h3("3. 实验分析流程")
para("实验分析以场景、策略、种子为维度批量生成运行组合，每组独立重建引擎与随机源并单独保存；运行结束后按场景与策略汇总均值、样本标准差与有效样本数，并通过图表对比各策略效果。")
h3("4. 关键业务规则")
para("系统若干关键业务规则如表6所示，这些规则决定了仿真的正确性与可复现性。")
table(
    ["规则", "约束"],
    [
        ["空站借车", "立即失败，不等待、不跨站，计入失败数"],
        ["满站还车", "按道路距离选择最近可达空位站改道，无候选进入等待"],
        ["车辆守恒", "总车数 = 库存 + 骑行 + 等待 + 运输"],
        ["容量约束", "stock≥0 且 stock+reserved≤capacity"],
        ["单实验槽", "同一时刻只有一个交互或批量实验，冲突返回409"],
        ["结构冻结", "非idle状态禁止站点/场景/配置的结构增删改"],
        ["命令幂等", "相同request_id返回原结果，不同payload返回409"],
        ["异常不写历史", "异常退出不创建不完整的运行记录"],
    ],
)
caption("表1 关键业务规则")
h2("（四）非功能需求")
para("系统要求相同配置、种子、版本和命令序列下结果可复现，仿真每阶段车辆守恒，本地可运行，业务可测试。运行采用单实验槽，同一时刻只能有一个交互或批量实验；非idle状态禁止结构配置的增删改。状态推送目标为每墙钟秒一次，由联调测试成员测量。合成需求不得声称真实运营。")
h2("（五）明确排除")
para("本系统仅完成P0功能，不做P1的定时自动调度界面与导出，不做P2的历史修正与阈值触发；不实现真实定位、支付、开锁、权限、车队车辆路径规划、完整骑行回放与异常恢复等真实运营能力。")

# ------------------------------------------------------------------ 三、总体架构
h1("三、系统总体架构")
h2("（一）架构总览")
para("系统采用前后端分离架构。前端为Vue3单页应用，经REST接口发送命令、经WebSocket接收完整状态；后端FastAPI负责参数校验与路由，运行管理器独占仿真引擎；调度为纯计算模块；NetworkX服务提供距离与路线；SQLite保存配置与被明确保存的运行结果。仿真引擎不依赖HTTP与ORM，仅接收JSON兼容的数据对象。")
para("架构上强调“单一推进者”原则：只有运行管理器能够推进引擎的步进，API命令与引擎步进进入同一把锁/队列；前端只读取状态、不直接修改库存；调度模块只输出计划、不直接扣减库存。这一设计保证了并发下的状态一致性与可复现性。")
figure(MAP_PNG, "图1 双校区2.5D底图与道路网络", width_cm=14.5)
h2("（二）模块划分")
para("后端按职责划分为引擎、路网、调度、实验、服务与接口六个模块，各模块职责与实现位置如表2所示。")
table(
    ["模块", "职责", "关键实现"],
    [
        ["engine", "离散事件仿真、借还/运输、不变量", "simulation.py / generator.py"],
        ["network", "路网投影、路径计算、可达性", "service.py"],
        ["dispatch", "需求预测、供需、三策略", "forecast / supply_demand / strategies"],
        ["experiments", "批量组合与统计汇总", "runner.py / stats.py"],
        ["services", "校验、事务、运行管理、后台工作者", "validation / store / runtime"],
        ["api", "REST/WebSocket 路由与统一错误", "main.py / api/"],
    ],
)
caption("表2 后端模块划分")
h2("（三）运行管理与单运行槽")
para("全局运行模式为 idle / interactive / batch 三种。创建交互或批量运行会原子占用运行槽，暂停仍占槽，批量组合之间仍占槽，冲突返回409 BUSY。非idle状态下禁止结构配置的增删改。系统单进程单worker部署，禁止使用多个uvicorn worker绕过进程内锁。")
para("交互运行由后台工作者按墙钟倍速推进同步步进；批量运行由实验协调器逐项调用运行回调，每组重建引擎、网络与随机源并单独保存。CPU执行不持续阻塞API事件循环。")
h2("（四）版本与可复现性")
para("运行快照保存契约版本、引擎版本、生成器版本、路网版本、Python版本、完整路网/站点/OD/参数、种子及控制命令。倍速仅影响墙钟推进，耗时与创建时间不参与复现比较。请求在时间段内按固定种子随机分布，墙钟不决定仿真结果；固定生成器版本与Python版本保证同版本下结果一致。")

# ------------------------------------------------------------------ 四、关键设计
h1("四、关键设计")
h2("（一）地图与道路网络")
para("路网采用NetworkX加权无向图建模，边长以米为单位且大于0，不自环，端点存在，折线首尾等于节点坐标。站点通过道路边与偏移（road_offset）接入路网，偏移为沿折线累计长度的比例[0,1]，实际米长按该比例分摊。新增或拖动站点时，服务选择最近可骑行道路并投影，返回标准化站点；图外或超出容差（默认40像素）的坐标被拒绝。")
para("唯一跨校区连接为主校区南门出门向南、再向东经上园村路至东校区小西门，全长469米，双向通行。表3给出正式站点的清单与库存配置。")
table(
    ["站点", "名称", "校区", "容量", "初始库存"],
    [[s["id"], s["name"], "主校区" if s["campus"] == "main" else "东校区", s["capacity"], s["initial_stock"]] for s in stations],
)
caption("表3 正式站点清单（14站，总容量565，初始290）")
h2("（二）离散事件仿真引擎")
para("引擎默认参数为：时长120分钟、步长60秒、骑行速度12 km/h、运输速度10 km/h、倍速60、种子42。参数在运行创建时冻结，运行期间仅允许调整墙钟倍速，不得修改物理参数。")
h3("1. 请求生成")
para("请求生成采用标准库random.Random(seed)的独立随机源，不使用全局随机源。OD按(起点, 终点)排序，时间半开区间按步边界与倍率边界分割，未配置倍率的区间默认为1。在每个常率区间内使用指数到达间隔的泊松过程抽样，采样公式为 t += -log1p(-rng.random())/(rate_per_min×multiplier/60)，到区间末停止，零率不抽样。生成的事件保存time_sec=floor(t)，并按(time_sec, id)稳定排序。")
para("事件、骑行与任务ID分别使用req-/ride-/task-前缀与12位补零序号，保证字符串排序与生成次序一致；计数在每次新运行从1开始，跨运行由run_id区分。请求到达=执行时刻+max(step, ceil(distance/speed/step)×step)，零距离也至少延迟一步。")
h3("2. 步进与处理顺序")
para("初始时刻now=0，每步处理当前now后推进一个边界。每步处理顺序为：到期运输→到期骑行→此前等待→本步借车→预设调度触发→采样。新产生的等待车辆本步不重复尝试；库存时间积分使用前一处理后状态覆盖到当前边界。内部cursor指向下一个待处理边界，公开状态sim_time是刚处理的边界，不提前显示cursor。完成最后边界后step幂等返回终态。")
h3("3. 借还与运输规则")
para("借车在空站立即失败，不等待也不改站；否则扣减1辆。首次到达仅记一次首次还车尝试。可用容量=capacity−stock−reserved_inbound；有位归还，无位按(道路距离, id)选择最近的可达空位站改道并增加实际改道路段距离，无候选进入等待并在后续步重试。骑行改道不预留位置，可能再次改道；等待不计骑行利用率。")
para("调度执行前聚合校验所有源库存与目的预留，整批原子接受或拒绝。扣源、加目的预留，任务并行，运输到期释放预留并入库且幂等。未到货结束不凭空归还。手动命令在最近已发布边界执行并记录命令序号。")
h3("4. 守恒不变量")
para("引擎在每个阶段校验守恒不变量：总车数=库存+骑行+等待+运输；stock≥0且stock+reserved≤capacity；预留等于未到货任务量；每请求恰好计一次。这些不变量构成了仿真正确性的核心保证，也是验收测试的重点，杜绝了“为了通过而伪造整套非法运行”的情况。")
h2("（三）库存约束的需求预测（fluid-v2）")
para("预测从当前快照出发，以步为单位推演30分钟（截断到场景终点）的窗口，复制当前浮点期望库存、预留、已知骑行、等待与运输，逐步按引擎顺序推演。OD借车量按 rate_per_min 与倍率的积分计算，同一站点多条OD按潜在需求比例分享库存。分别累计潜在借车量B（不论有无车）、受库存限制的预计借出量served，以及窗口内实际归还R；只有served产生未来骑行，因此空站不会被误判为低需求。")
para("在docs/06原始公式的基础上，fluid-v2额外记录每站“需求水位曲线”的最低点，以识别“先借后还”型站点在窗口中途的缺车。例如宿舍10辆、前10分钟借20辆、第25分钟还20辆时，原公式因只看窗口总量而误判可调出5辆，实际第5分钟已空站。fluid-v2的安全库存与目标库存计算为：")
code_block(
    "S_i = max(safety_stock, Q95(Poisson(B)) - B)\n"
    "T   = clip(floor(E + S_i - min_level + 0.5), 0, capacity)\n"
    "E   = stock + reserved_inbound\n"
    "supply  = min(stock, max(0, E - T))\n"
    "demand  = min(capacity - stock - reserved_inbound, max(0, T - E))"
)
para("该模型为确定性流体期望近似，不是随机过程的精确期望，需求波动仅通过泊松安全余量近似；模型不预测之后的调度，也不读取未来真实请求，且目标只防缺车、未同时约束满站，这些局限在实验部分如实说明。")
h2("（四）调度策略")
para("系统实现三种策略并统一执行口径，调度只输出计划、不直接扣减库存，由引擎重新校验后原子发车。")
h3("1. 无调度基准")
para("无调度（none）不产生任何运输任务，仅用于提供对照基准；但none同样估算供需与目标偏差，以保证各策略具有同口径的可比指标。")
h3("2. 贪心策略")
para("贪心按(距离, 源id, 目的id)升序排序候选对，逐对分配min(剩余供给, 剩余需求, 剩余预算)，不可达组合跳过。贪心在固定顺序下可复现，但不保证全局最优：在不连通图或存在不可达组合时可能无法达到最大流。")
h3("3. 最小费用流")
para("最小费用流将问题建模为网络流：超级源连接各源汇总点（容量为预算），源汇总点连接供给站（容量为各站supply），供给站连接需求站（容量不限，费用为floor(distance+0.5)整数米），需求站连接汇点（容量为各站demand）。先以maximum_flow_value求最大调度量F，再令超级源需求−F、汇点需求+F、其余节点需求为0，以network_simplex求最小费用。F=0时返回空计划。")
para("最小费用流的最优性针对整数费用模型，报告成本使用原始米数；稳定节点与边插入顺序、固定NetworkX版本、计划按(源, 目的)排序保证并列最优时可复现。模块测试以独立穷举算法为基准验证了最小费用流的最优性，并构造了贪心非最优的反例（两供两需时贪心1100辆·米、最小费用流400辆·米；某对不可达时贪心只调1辆、最小费用流调2辆）。")
h2("（五）数据库与持久化")
para("持久化使用SQLite与SQLAlchemy，启用外键。数据表包括站点、场景、OD需求、仿真配置、运行、指标、调度任务与批次，其结构与关键字段如表4所示。")
table(
    ["表", "关键字段"],
    [
        ["stations", "id, name, campus, zone, x, y, capacity, initial_stock, road_edge_id, road_offset, active"],
        ["scenarios", "id, name, start_minute, duration_min, description, is_preset"],
        ["od_demands", "id, scenario_id, origin_id, destination_id, rate_per_min, periods_json"],
        ["simulation_configs", "id, name, scenario_id, params_json, seed, algorithm"],
        ["simulation_runs", "id, batch_id, config_snapshot_json, algorithm, seed, status, summary_json, commands_json"],
        ["simulation_metrics", "id, run_id, sim_time_sec, metrics_json, station_states_json"],
        ["dispatch_tasks", "id, run_id, source_id, destination_id, quantity, distance_m, route_json, depart_sec, arrival_sec, status"],
        ["batches", "id, request_json, created_at, ended_at, status, items_json, aggregates_json"],
    ],
)
caption("表4 数据库表结构")
para("运行、指标、任务、命令在一次事务中保存；历史状态只保留completed与stopped，异常不新增不完整的运行记录。历史快照保存完整路网、站点、OD、参数与版本，不以当前站点外键破坏旧历史；删除站点时若未确认清理关联OD则返回409。")
h2("（六）接口设计")
para("接口前缀为/api/v1，返回统一错误体{code, message, details}。静态与配置接口覆盖站点、场景、配置的CRUD；运行接口提供创建运行、控制、状态查询、供需查询、手动调度、任务与历史查询、批次启动与查询。主要接口如表5所示。")
table(
    ["方法 路径", "说明"],
    [
        ["GET /health", "健康检查，返回 stage=implemented"],
        ["GET /runtime", "当前运行槽模式与run_id/batch_id"],
        ["GET /map /roads /stations", "底图、路网与站点资源"],
        ["POST /stations", "新增站点（不传道路派生字段）"],
        ["PATCH /stations/{id}", "拖动选址（仅x/y，服务端投影）"],
        ["DELETE /stations/{id}", "删除站点（关联OD需确认）"],
        ["GET/POST/PATCH/DELETE /scenarios", "场景CRUD与OD倍率管理"],
        ["GET/POST/PATCH/DELETE /configs", "仿真配置管理"],
        ["POST /runs", "创建交互运行（占用运行槽）"],
        ["POST /runs/{id}/control", "暂停/继续/停止/倍速/重置"],
        ["GET /runs/{id}/state", "当前运行状态快照"],
        ["GET /runs/{id}/supply-demand", "站点供需估算"],
        ["POST /runs/{id}/dispatch", "手动调度（request_id幂等）"],
        ["GET /runs/{id}/tasks", "运输任务列表"],
        ["GET /runs /runs/{id}/metrics", "历史与逐步指标查询"],
        ["POST /batches", "批量实验启动（202）"],
        ["GET /batches/{id}", "批量进度与聚合结果"],
        ["WS /ws/runs/{id}", "按seq合并推送运行状态"],
    ],
)
caption("表5 主要接口清单")
para("WebSocket端点在运行期间每秒合并推送一次完整状态，序号seq按运行单调递增，前端按序号合并以支持断线恢复；断线时可降级为每秒GET状态轮询。")

# ------------------------------------------------------------------ 五、技术选型理由
h1("五、技术选型理由")
h2("（一）前端选型")
para("选用Vue 3组合式API与TypeScript，以获得响应式数据绑定与静态类型检查，便于管理运行状态、站点、配置与历史等多类共享状态。Element Plus提供成熟的中文后台组件，降低表单、表格、弹窗的开发成本。Pinia用于集中管理runtime、config与history三类状态。")
para("地图采用Leaflet的CRS.Simple非地理坐标系，直接以图像像素坐标为底图，天然适配自绘2.5D校园底图，避免引入地理坐标与投影复杂度；地图仅在组件边界进行图像坐标与Leaflet坐标的转换。图表采用ECharts，支持均值、标准差、有效样本数等多维度实验指标的交互展示。")
para("相对于基于Canvas或WebGL的自研地图，Leaflet在本项目的小规模、单底图、折线图层场景下开发成本更低；相对于D3等底层库，ECharts对中文图表、坐标轴与图例的默认支持更完整。")
h2("（二）后端选型")
para("后端选用FastAPI，借助其自动OpenAPI文档与异步支持，将统一错误体、请求校验与路由快速落地；Uvicorn作为ASGI服务器支持WebSocket。持久化选用SQLite与SQLAlchemy，满足课程原型对零运维、单文件、事务一致性的需求，并通过外键与单事务保证历史快照的完整性。")
para("路网与算法选用NetworkX，其内置的加权最短路径与网络单纯形最小费用流实现，显著降低图算法开发成本，并保证与穷举基准可对照验证。仿真引擎刻意不依赖HTTP与ORM，保证其确定性、可测试性与可移植性。")
para("总体而言，技术选型以“课程尺度内快速可靠地落地可复现原型”为目标，在工程效率与算法严谨性之间取得平衡，而非追求生产级高并发能力。")
h2("（三）选型对比")
para("关键技术的取舍如表6所示，选择依据权衡了课程场景下的开发效率、可验证性与可维护性。")
table(
    ["决策点", "选择", "对比与理由"],
    [
        ["地图坐标系", "Leaflet CRS.Simple", "自绘底图无需地理投影，直接使用像素坐标，降低投影复杂度"],
        ["后端框架", "FastAPI", "自动OpenAPI与异步支持，统一错误体易于落地"],
        ["持久化", "SQLite", "零运维、单文件、事务一致，满足课程原型规模"],
        ["图算法", "NetworkX", "内置最短路径与最小费用流，可与穷举基准对照验证"],
        ["状态推送", "WebSocket + seq", "每秒合并推送，断线可降级为GET轮询，保证一致性"],
    ],
)
caption("表6 关键技术选型对比")

# ------------------------------------------------------------------ 六、实现与测试
h1("六、实现与测试")
h2("（一）开发协作方式")
para("项目采用六人并行开发：A负责后端与引擎，B负责调度与实验，C负责前端，D负责地图路网数据，E负责联调测试与集成，F负责文档与课程材料。以contracts目录中的v1公共契约（1.1.0）为机器可读约定，包含JSON Schema与Python端口签名；各成员在独立分支开发，经E串行集成与复验，最终合并至main分支。")
h2("（二）测试策略")
para("测试分为三层：常规门禁运行契约、单元与集成基线并构建前端；骨架诊断显式运行占位检查；正式验收在非空业务测试通过后核对24项验收证据。模块级测试可使用显式替身，但系统级验收必须使用真实引擎、真实调度、真实路网与临时数据库，并关闭前端Mock。")
para("关键设计原则包括：不得删除断言或跳过失败来通过检查；测试替身仅用于模块自测、不得导入生产代码；空测试集视为未验收；固定种子与稳定排序保证测试可复现。")
h2("（三）前端五页面")
para("前端实现运营总览、停车点管理、仿真控制、智能调度、实验分析五个页面，每个页面均有独立入口与完整功能清单，如表7所示。")
table(
    ["页面", "路径", "主要功能"],
    [
        ["运营总览", "/#/overview", "借还指标与趋势、双校区库存预警、车辆状态、站点地图与详情"],
        ["停车点管理", "/#/stations", "校区筛选、列表与地图联动、站点CRUD、拖动选址、关联OD删除确认"],
        ["仿真控制", "/#/control", "场景CRUD、OD与倍率时段、配置CRUD、开始/暂停/继续/倍速/停止/重置"],
        ["智能调度", "/#/dispatch", "策略参数、站点供需、手动触发、运输任务状态与进度、地图路线"],
        ["实验分析", "/#/experiments", "组合预览、批次进度、失败子项、策略均值/标准差/有效n、历史详情"],
    ],
)
caption("表7 前端五页面功能清单")
figure(UI / "01-overview-campus.png", "图2 运营总览页面", width_cm=14.5)
figure(UI / "02-stations-campus-map.png", "图3 停车点管理与地图联动", width_cm=14.5)
figure(UI / "03-control-config.png", "图4 仿真控制与配置页面", width_cm=14.5)
figure(UI / "04-control-paused.png", "图5 运行控制（暂停状态）", width_cm=14.5)
figure(UI / "05-dispatch-real.png", "图6 智能调度与任务路线", width_cm=14.5)
figure(UI / "07-experiments-history.png", "图7 实验分析与历史记录", width_cm=14.5)
h2("（四）测试结果汇总")
para("集成后的自动化与验收结果如表8所示。全部为真实集成环境下的实际结果，未使用Mock。")
table(
    ["检查项", "范围", "结果"],
    [
        ["单元与集成", "backend/tests + tests/integration", "614 passed / 0 failed"],
        ["前端构建", "npm run build", "通过"],
        ["业务验收", "tests/acceptance -m acceptance", "7 passed"],
        ["前端浏览器套件", "npm test (Edge + Playwright)", "6/6 passed"],
        ["A 模块测试", "owner_a", "67 passed"],
        ["B 模块测试", "owner_b", "494 passed"],
        ["D 模块测试", "owner_d", "21 passed"],
        ["正式实验", "8场景×3策略×5种子", "120/120 成功"],
    ],
)
caption("表8 测试与验收结果汇总")
h2("（五）验收矩阵")
para("系统按24项验收项（AC-A01～AC-E03、AC-F01/F02）逐项验收，其中22项通过、2项（AC-F01/F02 论文与PPT）由本文档交付，具体状态如表9所示。")
ac_rows = []
for it in acjson["items"]:
    st = {"passed": "通过", "pending": "待定", "failed": "失败"}.get(it["status"], it["status"])
    ac_rows.append([it["id"], st])
# 24项分两列展示以节省空间
half = (len(ac_rows) + 1) // 2
col_a = ac_rows[:half]
col_b = ac_rows[half:]
headers = ["验收项", "状态", "验收项", "状态"]
rows = []
for i in range(half):
    a = col_a[i]
    b = col_b[i] if i < len(col_b) else ["", ""]
    rows.append([a[0], a[1], b[0], b[1]])
table(headers, rows)
caption("表9 24项验收状态（AC-F01/F02 待本文档交付）")

# ------------------------------------------------------------------ 七、实验与分析
h1("七、实验与分析")
h2("（一）实验设置")
para("正式实验采用八个独立场景，其名称、时间窗口与时长如表10所示，需求率均为课程合成参数。三种策略为无调度、贪心、最小费用流，五个随机种子为42～46。相同场景与种子使用相同的初始库存、OD与请求生成规则。统一120分钟仿真时长、60秒步长、每900秒触发一次调度。完整批次为8×3×5=120组，每组有效样本数n=5。")
scn_rows = []
for s in scenarios:
    start = s["start_minute"]
    end = start + s["duration_min"]
    scn_rows.append([SCENARIO_CN.get(s["id"], s["id"]), s["name"], hhmm(start), hhmm(end), s["duration_min"]])
table(["场景ID", "名称", "开始", "结束", "时长(分)"], scn_rows)
caption("表10 八个正式实验场景")
para("统计口径上，按(场景, 策略)汇总五个种子的均值与样本标准差；无样本或单样本的标准差记为null，不以0代替。实验程序的成功指运行正常完成并保存历史，不预设任何策略的效果阈值。")
h2("（二）实验结果")
para("120组实验全部成功完成、0失败，120个run_id唯一。各场景借车成功率、调度量与调度成本如表11所示。")
rows = []
for s in SCENARIO_ORDER:
    for a in ALGO_ORDER:
        m = agg[(s, a)]
        rows.append([
            SCENARIO_CN[s], ALGO_CN[a],
            f"{m['borrow_success_rate']['mean']:.3f} ± {m['borrow_success_rate']['stddev']:.3f}",
            f"{m['dispatch_quantity']['mean']:.1f} ± {m['dispatch_quantity']['stddev']:.1f}",
            f"{m['dispatch_cost_bike_m']['mean']:.0f} ± {m['dispatch_cost_bike_m']['stddev']:.0f}",
        ])
table(["场景", "策略", "借车成功率", "调度量(辆)", "调度成本(辆·米)"], rows)
caption("表11 120组对照实验结果（均值 ± 样本标准差，n=5）")
figure(FIG / "fig_borrow_success_rate.png", "图8 各场景借车成功率对比")
figure(FIG / "fig_dispatch_quantity.png", "图9 各场景调度量对比")
figure(FIG / "fig_dispatch_cost.png", "图10 各场景调度成本对比")
h2("（三）结果分析")
para("从实验结果可以观察到三点。第一，无调度策略下各场景借车成功率介于40.7%～99.5%之间，早课、晚课等高峰场景明显偏低，说明潮汐需求下自然分布无法满足借车需求。第二，贪心与最小费用流将绝大多数场景的借车成功率提升至100%，且需要付出正的非零调度量与调度成本，验证了主动调度的必要性。第三，贪心与最小费用流在多数场景给出相同的调度量与成本，仅晚课场景的最小费用流成本略低（21901对22051辆·米）。")
para("贪心与最小费用流高度重合，与校园路网规模较小、候选站距离分布以及单次调度上限50辆有关；模块测试已给出贪心非全局最优的反例，因此本实验结果不代表最小费用流在普遍意义上更优，不能据此宣称某一策略整体占优。")
para("进一步考察缺车与满载时长可知，调度显著压缩了缺车时间：早课场景无调度时缺车时长约166站·分钟，晚课约202站·分钟，午课约132站·分钟，而采用贪心或最小费用流后均降至0；与此同时，调度将车辆集中到需求站，使部分场景满载时长上升（如晚课由72站·分钟升至8～9站·分钟，午课由79站·分钟降至28站·分钟，晚餐由96站·分钟基本持平）。目标偏差指标各策略采用同口径估算，用于衡量实际库存与目标库存的偏离程度，在调度前后由约241站·辆降至220站·辆。上述结果与“调度以一定运输成本换取借车成功率提升、同时可能加剧局部满载”的预期一致。")
h2("（四）局限与真实性说明")
bullet("需求率为课程合成参数，非实测调查结果；场景时间窗口来自用户设定。")
bullet("路网部分边长来自在线中心线量算与底图比例估算，仅道路50（100米）与跨校区链（469米）由用户确认；留一检验平均位置误差主校区约6.3米、东校区约17.5米。")
bullet("统一120分钟时长使短场景（如早课30分钟）存在较长无需求尾段，时间加权指标受此影响，仅保证策略间横向可比。")
bullet("预测模型为流体期望近似，只防缺车、未同时约束满站；需求波动仅以泊松安全余量近似。")
bullet("运行环境为Python 3.13.5，与基线3.12存在环境偏差，锁依赖在3.13下安装运行正常。")

# ------------------------------------------------------------------ 八、总结与展望
h1("八、总结与展望")
h2("（一）总结")
para("本文设计并实现了一个校园共享单车智能调度与可视化仿真系统，完成了双校区路网建模、离散事件仿真引擎、库存约束需求预测、三种调度策略、五页面Web前端与实时可视化，并在八个场景、三种策略、五个种子的120组对照实验上验证了系统的正确性与策略效果。系统严格区分合成数据与真实运营，具备可复现性、守恒正确性与可验收性。")
para("在方法层面，本文的贡献主要体现在：以最小费用流与穷举算法双重验证保证了调度最优性；以fluid-v2需求水位曲线改进了对“先借后还”潮汐站点的供需估算；以固定种子与稳定排序保证了实验的严格可复现。")
h2("（二）展望")
para("后续工作可从以下方面展开：一是引入真实校园骑行调查数据，替代课程合成需求率；二是将预测模型由流体期望近似扩展为随机过程的更精确期望，并同时约束缺车与满站；三是在更大规模路网与预算上比较更多元启发式与精确算法；四是补充批量的定时自动调度与历史修正等P1/P2能力。")
para("需要强调的是，本文所构建的系统是面向课程实验的仿真原型，其需求数据、部分道路边长与运营假设均与真实运营存在差距。将本文的方法与结论迁移到真实运营场景时，必须接入经过实测核验的需求调查数据与完整的道路测距依据，并对满站上限、骑行限制、通行方向等现实约束进行补充建模，方可形成对真实运营有参考价值的结论。")

# ------------------------------------------------------------------ 参考文献
h1("参考文献")
for ref in [
    "[1] 交通运输部等十部门. 关于鼓励和规范互联网租赁自行车发展的指导意见[Z]. 2017.",
    "[2] Ahuja R K, Magnanti T L, Orlin J B. Network Flows: Theory, Algorithms, and Applications[M]. Englewood Cliffs: Prentice Hall, 1993.",
    "[3] Raviv T, Tzur M, Forma I A. Static repositioning in a bike-sharing system: models and solution approaches[J]. EURO Journal on Transportation and Logistics, 2013, 2(3): 187-229.",
    "[4] Schuijbroek J, Hampshire R C, van Hoeve W-J. Inventory rebalancing and vehicle routing in bike sharing systems[J]. European Journal of Operational Research, 2017, 257(3): 992-1004.",
    "[5] Contardo C, Morency C, Rousseau L-M. Balancing a dynamic public bike-sharing system[R]. Montreal: CIRRELT, 2012.",
    "[6] Hagberg A A, Schult D A, Swart P J. Exploring network structure, dynamics, and function using NetworkX[C]//Proceedings of the 7th Python in Science Conference (SciPy 2008). 2008: 11-15.",
    "[7] Tiangolo S. FastAPI Documentation[EB/OL]. https://fastapi.tiangolo.com/.",
    "[8] Vue.js 官方文档[EB/OL]. https://cn.vuejs.org/.",
    "[9] OpenStreetMap contributors. OpenStreetMap[EB/OL]. https://www.openstreetmap.org/copyright.",
    "[10] Leaflet 官方文档[EB/OL]. https://leafletjs.com/.",
]:
    p = DOC.add_paragraph()
    _spacing(p, 0, 0, 1.25)
    _set_font(p.add_run(ref), F_LATIN, F_BODY, 10.5)

# ------------------------------------------------------------------ 附录
h1("附录A 运行说明")
para("本系统为本地可运行原型。安装与启动依赖Python 3.12+与Node 20+，具体步骤如下：", indent=False)
code_block(
    "python -m venv .venv\n"
    ".\\\\.venv\\\\Scripts\\\\python.exe -m pip install -r backend/requirements-lock.txt\n"
    ".\\\\.venv\\\\Scripts\\\\python.exe -m uvicorn app.main:app --app-dir backend --port 8000"
)
code_block(
    "cd frontend\n"
    "npm ci\n"
    "npm run dev"
)
para("页面访问 http://localhost:5173，API文档访问 http://localhost:8000/docs。默认数据profile为fixture，正式校园数据使用环境变量 DATA_PROFILE=campus 并指定独立的 DATABASE_URL。检查命令为 scripts/check.ps1（常规）与 scripts/check.ps1 -Acceptance（正式验收）。", indent=False)

h1("附录B 指标口径")
table(
    ["指标", "口径"],
    [
        ["borrow_success_rate", "借车成功 / 借车请求，零分母为null"],
        ["first_return_success_rate", "首次归还成功 / 首次归还尝试，零分母为null"],
        ["shortage_station_min", "各站库存为0的持续时间总和（站·分钟）"],
        ["full_station_min", "各站可用容量为0的持续时间总和（站·分钟）"],
        ["extra_ride_distance_m", "实际改道路段新增距离总和"],
        ["utilization", "骑行车辆时间积分 /（总车数×实际已模拟时长）"],
        ["dispatch_quantity", "已发车量"],
        ["dispatch_cost_bike_m", "已发车量×原始米距离"],
        ["target_deviation", "Σ|stock+reserved_inbound−目标库存|"],
        ["unfinished_riding/waiting/transporting", "终点未完成车辆数"],
    ],
)
caption("表12 指标字段口径")

h1("附录C 贡献说明")
para("本系统由六名成员并行开发完成，成员以A～F代称，各自真实姓名与组号待团队确认后填入。各成员实际贡献范围如下，评分表（满分100）由团队确认后填写，本文不预填团队分数。", indent=False)
table(
    ["成员", "职责", "实际贡献范围"],
    [
        ["A", "后端与仿真", "离散仿真引擎、运行管理、持久化、REST/WebSocket、67项模块测试"],
        ["B", "调度与实验", "需求预测(fluid-v2)、供需、三策略、批量与统计、494项模块测试"],
        ["C", "前端", "五页面、地图交互、REST/WS客户端、显式Mock、浏览器套件"],
        ["D", "地图路网数据", "底图与路网、14站、八组场景、路网服务、21项模块测试"],
        ["E", "联调测试与集成", "契约维护、真实集成、7项验收、120组实验、五页面真实证据"],
        ["F", "文档与课程交付", "论文、答辩PPT、运行说明、来源索引与交付索引"],
    ],
)
caption("表13 成员分工与实际贡献（评分待确认）")

h1("附录D 核心接口签名")
para("本系统模块间通过contracts/python_interfaces.py中的Python端口协议协作，协议只依赖标准库、不含业务实现，核心签名如下：", indent=False)
code_block(
    "class NetworkPort(Protocol):\n"
    "    def validate_station(self, candidate: DTO) -> DTO: ...\n"
    "    def route(self, source_id: str, destination_id: str) -> DTO: ...\n"
    "\n"
    "class DispatchPort(Protocol):\n"
    "    def estimate(self, snapshot: DTO, scenario: DTO, params: DTO,\n"
    "                 network: NetworkPort) -> DTO: ...\n"
    "    def plan(self, algorithm: str, supply_demand: DTO,\n"
    "             network: NetworkPort, max_dispatch: int) -> list[DTO]: ...\n"
    "\n"
    "class EnginePort(Protocol):\n"
    "    def step(self) -> DTO: ...\n"
    "    def snapshot(self) -> DTO: ...\n"
    "    def dispatch(self, request_id: str) -> DTO: ...\n"
    "\n"
    "class ExperimentPort(Protocol):\n"
    "    def run_batch(self, request: DTO, run_once: RunOnce,\n"
    "                  on_progress: OnProgress) -> DTO: ..."
)
para("该协议保证引擎不依赖HTTP或ORM、算法不读取未来实际事件、调度不直接修改库存，是系统可复现性与模块可替换性的基础。", indent=False)

h1("附录E 场景需求明细")
para("八个正式实验场景的合成需求描述与OD数量如表14所示，需求率均为课程合成参数。", indent=False)
scn_od = []
for s in scenarios:
    scn_od.append([SCENARIO_CN.get(s["id"], s["id"]), s["name"], s["description"], len(s["od_demands"])])
table(["场景", "名称", "需求描述", "OD数"], scn_od)
caption("表14 八个场景的合成需求明细")

h1("附录F 真实验收证据")
para("系统级验收在关闭前端Mock、接入真实campus后端的环境下由浏览器驱动完成。图11～图14给出重置、刷新恢复与站点拖动的部分真实证据截图。", indent=False)
figure(UI / "c01-reset-modal.png", "图11 重置三选项弹窗（保存/舍弃/取消）", width_cm=13.0)
figure(UI / "c02-recovery-after-refresh.png", "图12 刷新后的运行状态恢复", width_cm=13.0)
figure(UI / "c03-campus-roads.png", "图13 真实底图与道路图层", width_cm=13.0)
figure(UI / "c03-station-drag.png", "图14 站点拖动与服务端投影", width_cm=13.0)

DOC.save(OUT)
print("saved", OUT)
