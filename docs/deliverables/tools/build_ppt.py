# -*- coding: utf-8 -*-
"""生成答辩 PPT（每页标页码与讲述人，含贡献与评分表）。

讲述人以成员代称 A～F 标注，真实姓名待团队确认后替换；评分列留空待填。
"""
from pathlib import Path

from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[3]
FIG = ROOT / "docs/deliverables/source/figures"
UI = ROOT / "docs/integration/results/evidence/ui"
MAP = ROOT / "data/campus/campus_map.png"
OUT = ROOT / "docs/deliverables/source/答辩PPT.pptx"

FONT = "微软雅黑"
C_DARK = RGBColor(0x1F, 0x3B, 0x57)
C_ACCENT = RGBColor(0x2C, 0x6E, 0xB4)
C_GREY = RGBColor(0x66, 0x66, 0x66)
C_WHITE = RGBColor(0xFF, 0xFF, 0xFF)
C_LIGHT = RGBColor(0xF2, 0xF6, 0xFA)

prs = Presentation()
prs.slide_width = Inches(13.333)
prs.slide_height = Inches(7.5)
BLANK = prs.slide_layouts[6]


def _set_run(run, size, bold=False, color=C_DARK, name=FONT):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.name = name
    run.font.color.rgb = color
    rPr = run._r.get_or_add_rPr()
    for tag in ("a:latin", "a:ea", "a:cs"):
        e = rPr.find(qn(tag))
        if e is None:
            e = rPr.makeelement(qn(tag), {})
            rPr.append(e)
        e.set("typeface", name)


def add_textbox(slide, left, top, width, height):
    tb = slide.shapes.add_textbox(Inches(left), Inches(top), Inches(width), Inches(height))
    tf = tb.text_frame
    tf.word_wrap = True
    return tb, tf


def _footer(slide, idx, speaker):
    # 页码（右下）与讲述人（左下）
    tb, tf = add_textbox(slide, 10.9, 7.05, 2.2, 0.35)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.RIGHT
    _set_run(p.add_run(), 12)
    p.runs[0].text = str(idx)
    _set_run(p.runs[0], 12, color=C_GREY)
    tb2, tf2 = add_textbox(slide, 0.5, 7.05, 4.5, 0.35)
    p2 = tf2.paragraphs[0]
    _set_run(p2.add_run(), 12, color=C_GREY)
    p2.runs[0].text = f"讲述人：{speaker}"


def add_title_bar(slide, text):
    bar = slide.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(1.0))
    bar.fill.solid()
    bar.fill.fore_color.rgb = C_DARK
    bar.line.fill.background()
    tf = bar.text_frame
    tf.word_wrap = True
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.LEFT
    _set_run(p.add_run(), 26, bold=True, color=C_WHITE)
    p.runs[0].text = text
    tf.margin_left = Inches(0.5)
    tf.margin_top = Inches(0.12)


def content_slide(title, speaker, bullets, idx):
    slide = prs.slides.add_slide(BLANK)
    add_title_bar(slide, title)
    tb, tf = add_textbox(slide, 0.6, 1.25, 12.1, 5.6)
    for i, b in enumerate(bullets):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(10)
        p.level = 0
        _set_run(p.add_run(), 17)
        p.runs[0].text = ("• " + b) if b else ""
    _footer(slide, idx, speaker)
    return slide


def image_slide(title, speaker, path, caption, idx, width_in=7.5):
    slide = prs.slides.add_slide(BLANK)
    add_title_bar(slide, title)
    if Path(path).exists():
        pic = slide.shapes.add_picture(str(path), Inches((13.333 - width_in) / 2), Inches(1.4),
                                       width=Inches(width_in))
    tb, tf = add_textbox(slide, 1.0, 6.4, 11.3, 0.6)
    p = tf.paragraphs[0]
    p.alignment = PP_ALIGN.CENTER
    _set_run(p.add_run(), 14, color=C_GREY)
    p.runs[0].text = caption
    _footer(slide, idx, speaker)
    return slide


def table_slide(title, speaker, headers, rows, idx, col_widths=None):
    slide = prs.slides.add_slide(BLANK)
    add_title_bar(slide, title)
    n_rows = len(rows) + 1
    n_cols = len(headers)
    gt = slide.shapes.add_table(n_rows, n_cols, Inches(0.7), Inches(1.3),
                                Inches(11.9), Inches(0.5 * n_rows))
    table = gt.table
    for j, h in enumerate(headers):
        cell = table.cell(0, j)
        cell.text = h
        cell.fill.solid()
        cell.fill.fore_color.rgb = C_ACCENT
        for p in cell.text_frame.paragraphs:
            _set_run(p.runs[0] if p.runs else p.add_run(), 14, bold=True, color=C_WHITE)
    for i, row in enumerate(rows):
        for j, v in enumerate(row):
            cell = table.cell(i + 1, j)
            cell.text = str(v)
            cell.fill.solid()
            cell.fill.fore_color.rgb = C_LIGHT if i % 2 == 0 else C_WHITE
            for p in cell.text_frame.paragraphs:
                if p.runs:
                    _set_run(p.runs[0], 12)
    _footer(slide, idx, speaker)
    return slide


# ------------------------------------------------------------------ 幻灯片
# 1 封面
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg.fill.solid()
bg.fill.fore_color.rgb = C_DARK
bg.line.fill.background()
tb, tf = add_textbox(s, 1.0, 2.3, 11.3, 1.6)
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
_set_run(p.add_run(), 34, bold=True, color=C_WHITE)
p.runs[0].text = "校园共享单车智能调度与可视化仿真系统"
tb2, tf2 = add_textbox(s, 1.0, 4.1, 11.3, 1.0)
p2 = tf2.paragraphs[0]
p2.alignment = PP_ALIGN.CENTER
_set_run(p2.add_run(), 18, color=C_WHITE)
p2.runs[0].text = "组号：（待确认）   成员：A～F（姓名待确认）   指导教师：（待确认）"
tb3, tf3 = add_textbox(s, 1.0, 5.4, 11.3, 0.6)
p3 = tf3.paragraphs[0]
p3.alignment = PP_ALIGN.CENTER
_set_run(p3.add_run(), 14, color=C_WHITE)
p3.runs[0].text = "课程：智能交通专题 · 方案B（软件仿真/平台原型）"
_footer(s, 1, "全体")

# 2 目录
content_slide("目录", "A", [
    "01 项目背景与目标",
    "02 需求分析",
    "03 系统总体架构",
    "04 地图与道路网络",
    "05 离散事件仿真引擎",
    "06 需求预测与调度策略",
    "07 数据库与接口",
    "08 技术选型理由",
    "09 前端五页面",
    "10 测试与验收",
    "11 实验与分析",
    "12 局限、贡献与展望",
], 2)

# 3 背景
content_slide("01 项目背景与目标", "F", [
    "高校校园共享单车存在明显的潮汐式供需失衡：上课涌向教学区、下课/就餐反向回流。",
    "人工调度依赖经验、成本高、响应慢，难以应对高峰波动。",
    "目标：构建一个可复现、可交互、可对照的校园共享单车智能调度仿真原型（方案B）。",
    "范围：主校区与东校区，唯一跨校区连接（南门—上园村路—小西门），不接真实运营商。",
    "方法：路网建模 + 离散事件仿真 + 库存约束预测 + 三种调度策略 + 可视化前端。",
], 3)

# 4 需求
content_slide("02 需求分析", "A", [
    "功能需求 FR01～FR11：底图路网、站点CRUD、场景配置、运行控制、借还业务、运营监测、需求预测、三策略、手动调度、实验分析、持久化。",
    "关键业务规则：空站借车失败、满站改道/等待、车辆守恒、容量约束、单实验槽、结构冻结、命令幂等、异常不写历史。",
    "非功能：固定种子可复现、每阶段守恒、本地可运行、可测试。",
    "明确排除：P1/P2、真实定位/支付/开锁、车队VRP、完整回放。",
], 4)

# 5 架构
content_slide("03 系统总体架构", "A", [
    "前后端分离：Vue3 单页应用 ← REST 命令 / WebSocket 状态 → FastAPI 后端。",
    "单一推进者：运行管理器独占仿真引擎，API 命令与引擎步进同一锁/队列。",
    "纯计算模块：NetworkService 提供距离路线；DispatchService 输出调度计划，不直接改库存。",
    "持久化：SQLite + SQLAlchemy，历史快照独立于当前站点表。",
    "单运行槽：idle/interactive/batch，冲突返回 409 BUSY。",
], 5)
image_slide("03 系统总体架构 · 双校区底图", "D", MAP, "双校区 2.5D 底图与道路网络", 6, width_in=8.5)

# 6 地图
content_slide("04 地图与道路网络", "D", [
    "NetworkX 加权无向图，边长以米为单位，折线首尾等于节点坐标。",
    "站点通过 road_edge_id + road_offset 接入路网，偏移为折线累计长度比例。",
    "新增/拖动站点：选择最近可骑行道路投影，图外或超容差（40px）拒绝。",
    "唯一跨校区连接：主校区南门—上园村路—东校区小西门，全长 469 米。",
    "正式数据：14 站（主11/东3），总容量 565、初始 290。",
], 7)

# 7 引擎
content_slide("05 离散事件仿真引擎", "A", [
    "参数：120 分钟、步长 60 秒、骑行 12 km/h、运输 10 km/h、倍速 60、种子 42。",
    "请求生成：random.Random(seed) 独立随机源，指数间隔泊松过程，按 (time,id) 稳定排序。",
    "步进顺序：到期运输→到期骑行→此前等待→本步借车→预设调度→采样。",
    "守恒不变量：总车数=库存+骑行+等待+运输；stock+reserved≤capacity。",
    "固定生成器版本与 Python 版本保证同版本复现。",
], 8)

# 8 预测
content_slide("06 需求预测 fluid-v2", "B", [
    "库存约束流体期望推演：复制当前期望库存，按引擎顺序推演 30 分钟窗口。",
    "分别累计潜在借车 B、受库存限制的预计借出 served、窗口内实际归还 R。",
    "需求水位曲线识别“先借后还”站点中途缺车，避免窗口总量误判。",
    "S_i = max(safety_stock, Q95(Poisson(B))−B)；T = clip(floor(E+S_i−min_level+0.5), 0, capacity)。",
    "局限：流体期望近似、只防缺车未约束满站、不读取未来真实请求。",
], 9)

# 9 调度
content_slide("06 调度策略（三策略对照）", "B", [
    "无调度 none：不产生运输任务，作为对照基准。",
    "贪心：按(距离,源,目的)升序逐对分配，可复现但不保证全局最优。",
    "最小费用流：最大流 + 整数米费用最小，最优性经独立穷举算法交叉验证。",
    "统一执行：输出计划 → 引擎重新校验原子发车，调度不直接扣库存。",
], 10)

# 10 数据库与接口
content_slide("07 数据库与接口", "A", [
    "8 张表：stations / scenarios / od_demands / simulation_configs / simulation_runs / simulation_metrics / dispatch_tasks / batches。",
    "运行、指标、任务、命令一次事务保存；异常不写不完整历史。",
    "接口前缀 /api/v1，统一错误体 {code,message,details}。",
    "REST：站点/场景/配置 CRUD，运行控制、供需、手动调度、历史、批量。",
    "WebSocket：每秒合并推送完整状态，seq 单调递增，支持断线恢复。",
], 11)

# 11 技术选型
table_slide("08 技术选型理由", "A", ["决策点", "选择", "理由"], [
    ["地图", "Leaflet CRS.Simple", "自绘底图无需地理投影"],
    ["后端", "FastAPI", "自动 OpenAPI 与异步支持"],
    ["持久化", "SQLite", "零运维、事务一致"],
    ["图算法", "NetworkX", "内置最短路径与最小费用流"],
    ["状态推送", "WebSocket + seq", "每秒合并推送，可降级轮询"],
], 12)

# 12 前端
image_slide("09 前端五页面", "C", UI / "01-overview-campus.png", "运营总览 / 停车点管理 / 仿真控制 / 智能调度 / 实验分析", 13, width_in=9.5)
content_slide("09 前端五页面 · 功能清单", "C", [
    "运营总览：指标趋势、双校区库存预警、车辆状态。",
    "停车点管理：列表地图联动、CRUD、拖动选址、关联删除确认。",
    "仿真控制：场景/OD/配置管理与运行控制（含重置三选项）。",
    "智能调度：供需、手动触发、任务进度与路线。",
    "实验分析：组合预览、进度、失败子项、策略对照图表。",
], 14)

# 13 测试
table_slide("10 测试与验收", "E", ["检查项", "范围", "结果"], [
    ["单元与集成", "backend/tests + tests/integration", "614 passed"],
    ["业务验收", "tests/acceptance -m acceptance", "7 passed"],
    ["前端浏览器套件", "npm test (Edge + Playwright)", "6/6 passed"],
    ["正式实验", "8场景×3策略×5种子", "120/120 成功"],
    ["验收矩阵", "24 项 AC", "22 passed / 2 pending(F)"],
], 15)

# 14 实验设置
content_slide("11 实验设置", "B", [
    "八个场景：早课、上午下课、午餐、午课、下午下课、晚餐、晚课、返寝（合成需求）。",
    "三种策略 × 五个种子（42～46） = 120 组，每组有效 n=5。",
    "统一 120 分钟、60 秒步长、每 900 秒触发调度；同场景同种子相同初始条件。",
    "统计：均值 + 样本标准差 + 有效 n，null 不以 0 代替。",
], 16)

# 15 实验结果（图）
image_slide("11 实验结果 · 借车成功率", "E", FIG / "fig_borrow_success_rate.png",
            "各场景借车成功率（均值 ± 样本标准差，n=5）", 17, width_in=9.5)
image_slide("11 实验结果 · 调度量与成本", "E", FIG / "fig_dispatch_quantity.png",
            "各场景调度量（均值 ± 样本标准差，n=5）", 18, width_in=9.5)

# 16 结果分析
content_slide("11 结果分析", "E", [
    "无调度：早课/晚课借车成功率低至 40.7%～62.7%，潮汐需求下自然分布无法满足。",
    "贪心与最小费用流：将绝大多数场景借车成功率提升至 100%。",
    "调度显著压缩缺车时长（早课 166 → 0 站·分钟），部分场景满载时长上升。",
    "贪心与最小费用流高度重合，仅晚课成本略低（21901 vs 22051 辆·米）。",
    "结论：主动调度必要，但现有数据不能宣称最小费用流整体更优。",
], 19)

# 17 局限
content_slide("12 局限与真实性说明", "F", [
    "需求率为课程合成参数，非实测调查结果。",
    "部分道路边长来自中心线量算与比例估算，仅道路50(100米)与跨区链(469米)经用户确认。",
    "统一 120 分钟使短场景存在无需求尾段，时间加权指标仅策略间可比。",
    "预测为流体期望近似，只防缺车、未约束满站。",
    "运行环境 Python 3.13 与基线 3.12 存在环境偏差。",
], 20)

# 18 贡献与评分
table_slide("12 成员贡献（评分待确认）", "F", ["成员", "职责", "实际贡献", "评分/100"], [
    ["A", "后端与仿真", "引擎、运行管理、持久化、REST/WS、67项测试", ""],
    ["B", "调度与实验", "预测(fluid-v2)、三策略、批量统计、494项测试", ""],
    ["C", "前端", "五页面、地图交互、客户端、Mock、浏览器套件", ""],
    ["D", "地图路网数据", "底图、路网、14站、八场景、21项测试", ""],
    ["E", "联调测试集成", "契约、真实集成、7项验收、120组实验", ""],
    ["F", "文档与课程交付", "论文、答辩PPT、运行说明、来源索引", ""],
], 21)

# 19 总结
content_slide("12 总结与展望", "F", [
    "完成了双校区路网建模、离散事件仿真、库存约束预测、三种调度策略与五页面可视化。",
    "以最小费用流 + 穷举双重验证保证调度最优性；fluid-v2 改进潮汐站点供需估算。",
    "120 组对照实验验证了系统的正确性与策略效果，严格区分合成数据与真实运营。",
    "展望：接入真实调查数据、更精确随机预测、更大规模路网、补足 P1/P2。",
], 22)

# 20 致谢
s = prs.slides.add_slide(BLANK)
bg = s.shapes.add_shape(1, Inches(0), Inches(0), Inches(13.333), Inches(7.5))
bg.fill.solid()
bg.fill.fore_color.rgb = C_DARK
bg.line.fill.background()
tb, tf = add_textbox(s, 1.0, 3.0, 11.3, 1.5)
p = tf.paragraphs[0]
p.alignment = PP_ALIGN.CENTER
_set_run(p.add_run(), 40, bold=True, color=C_WHITE)
p.runs[0].text = "谢谢，请老师批评指正"
_footer(s, 23, "全体")

prs.save(OUT)
print("saved", OUT, "slides:", len(prs.slides._sldIdLst))
