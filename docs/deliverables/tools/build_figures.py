# -*- coding: utf-8 -*-
"""从真实 120 组实验结果生成论文/PPT 图表。

数据源：docs/integration/results/evidence/experiments/batch-120-result.json
输出：docs/deliverables/source/figures/*.png

仅使用 E 已核验的正式实验结果，不伪造数据。
"""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager

# 中文字体
for name in ("Microsoft YaHei", "SimHei", "SimSun"):
    if any(f.name == name for f in font_manager.fontManager.ttflist):
        plt.rcParams["font.sans-serif"] = [name]
        break
plt.rcParams["axes.unicode_minus"] = False

ROOT = Path(__file__).resolve().parents[3]
RESULT = ROOT / "docs/integration/results/evidence/experiments/batch-120-result.json"
OUT = ROOT / "docs/deliverables/source/figures"
OUT.mkdir(parents=True, exist_ok=True)

SCENARIO_ORDER = [
    "morning", "morning-dismissal", "lunch", "afternoon-class",
    "afternoon-dismissal", "dinner", "evening-class", "evening",
]
SCENARIO_CN = {
    "morning": "早课", "morning-dismissal": "上午下课", "lunch": "午餐",
    "afternoon-class": "午课", "afternoon-dismissal": "下午下课",
    "dinner": "晚餐", "evening-class": "晚课", "evening": "返寝",
}
ALGO_ORDER = ["none", "greedy", "min_cost_flow"]
ALGO_CN = {"none": "无调度", "greedy": "贪心", "min_cost_flow": "最小费用流"}
COLORS = {"none": "#7f7f7f", "greedy": "#1f77b4", "min_cost_flow": "#2ca02c"}


def load():
    data = json.loads(RESULT.read_text(encoding="utf-8"))
    agg = {}
    for a in data["aggregates"]:
        agg[(a["scenario_id"], a["algorithm"])] = a["metrics"]
    return data, agg


def grouped(metric, title, ylabel, out_name, scale=1.0, pct=False):
    data, agg = load()
    labels = [SCENARIO_CN[s] for s in SCENARIO_ORDER]
    series = {}
    for algo in ALGO_ORDER:
        vals = []
        errs = []
        for s in SCENARIO_ORDER:
            m = agg[(s, algo)][metric]
            vals.append(m["mean"] * scale)
            errs.append((m["stddev"] or 0) * scale)
        series[algo] = (vals, errs)

    x = range(len(labels))
    width = 0.26
    fig, ax = plt.subplots(figsize=(9.6, 4.4), dpi=150)
    for i, algo in enumerate(ALGO_ORDER):
        vals, errs = series[algo]
        off = (i - 1) * width
        bars = ax.bar([xi + off for xi in x], vals, width, yerr=errs,
                      capsize=3, label=ALGO_CN[algo], color=COLORS[algo],
                      error_kw={"elinewidth": 1.2, "ecolor": "#333333"})
        if pct:
            for b, v in zip(bars, vals):
                ax.annotate(f"{v:.1%}", (b.get_x() + b.get_width() / 2, v + max(errs) * 0.15 + 0.01),
                            ha="center", va="bottom", fontsize=7.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel(ylabel, fontsize=10)
    ax.set_title(title, fontsize=12)
    if pct:
        ax.set_ylim(0, 1.15)
    ax.legend(fontsize=9, ncol=3, loc="upper center", frameon=False)
    ax.grid(axis="y", linestyle="--", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    fig.tight_layout()
    fig.savefig(OUT / out_name, bbox_inches="tight")
    plt.close(fig)
    print("wrote", out_name)


if __name__ == "__main__":
    grouped("borrow_success_rate", "各场景借车成功率（均值 ± 样本标准差，n=5）",
            "借车成功率", "fig_borrow_success_rate.png", pct=True)
    grouped("dispatch_quantity", "各场景调度量（均值 ± 样本标准差，n=5）",
            "调度量（辆）", "fig_dispatch_quantity.png")
    grouped("dispatch_cost_bike_m", "各场景调度成本（均值 ± 样本标准差，n=5）",
            "调度成本（辆·米）", "fig_dispatch_cost.png")
    print("done")
