"""Plot measured simulated evaluation output. No fabricated example values."""
from __future__ import annotations
import argparse
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    args = parser.parse_args()
    results = json.loads((args.artifacts/"evaluation.json").read_text(encoding="utf-8"))
    with (args.artifacts/"trace_first_episode.csv").open(encoding="utf-8", newline="") as f:
        rows = list(csv.DictReader(f))
    available = {item.name for item in font_manager.fontManager.ttflist}
    cjk = next((name for name in ("Microsoft YaHei", "Noto Sans CJK SC", "Noto Sans CJK JP", "SimHei") if name in available), None)
    plt.rcParams["font.family"] = [cjk, "DejaVu Sans"] if cjk else ["DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    text = lambda zh, en: zh if cjk else en
    fig, axes = plt.subplots(1,2,figsize=(13,5), constrained_layout=True)
    fig.suptitle(text("单关节位置跟踪：MuJoCo 仿真结果", "Single-joint position tracking: MuJoCo simulation"), fontsize=18, weight="bold")
    labels=[text("零动作","Zero"), text("未训练网络","Untrained"), "PPO", text("直接给目标","Direct target")]
    keys=["zero", "untrained", "ppo", "target_copy"]
    values=[results["policies"][k]["final_50_mean_abs_error_deg"] for k in keys]
    axes[0].bar(labels, values, color=["#8ba1b0", "#8ba1b0", "#20a77e", "#e6a149"])
    axes[0].set_ylabel(text("最后 50 步平均绝对误差（度）", "Mean absolute error, final 50 steps (deg)"))
    axes[0].set_title(text("20 个独立初始条件 · 越低越好", "20 independent initial conditions · lower is better"))
    for i,v in enumerate(values): axes[0].text(i,v+0.3,f"{v:.2f}°",ha="center",fontsize=10)
    for name, label, color in [("zero",text("零动作","Zero"),"#8ba1b0"),("ppo","PPO","#20a77e"),("target_copy",text("直接给目标","Direct target"),"#e6a149")]:
        selected=[r for r in rows if r["policy"]==name]
        axes[1].plot([float(r["time_s"]) for r in selected],[float(r["angle_rad"]) for r in selected],label=label,color=color)
    target=float(rows[0]["target_rad"])
    axes[1].axhline(target,linestyle="--",color="#4c5360",label=text("目标角","Target"))
    axes[1].set_xlabel(text("时间（秒）","Time (s)"));axes[1].set_ylabel(text("关节角（弧度）","Joint angle (rad)"))
    axes[1].set_title(text(f"第一组初始条件 · 种子 {rows[0]['seed']}", f"First initial condition · seed {rows[0]['seed']}"))
    axes[1].legend(frameon=False)
    fig.text(.5,.01,text("仅为仿真；简单任务中直接给目标是应当保留的强基线。", "Simulation only; a direct target is a useful baseline for a simple task."),ha="center",color="#63727c",fontsize=10)
    fig.savefig(args.artifacts/"tracking_comparison.png", dpi=160, bbox_inches="tight")
    print(f"Saved {args.artifacts/'tracking_comparison.png'}")


if __name__ == "__main__":
    main()
