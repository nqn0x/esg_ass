"""
esg_rag/eval/plot_ablation.py
-----------------------------
Reads scoreboard.csv and plots a grouped bar chart:
  X-axis: pipeline variant labels (v01_dense_only, v02_hybrid, etc.)
  Y-axis: 4 RAGAS metrics as grouped bars

Usage:
    python -m esg_rag.eval.plot_ablation
    python -m esg_rag.eval.plot_ablation --out docs/ablation.png
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

SCOREBOARD = Path("esg_rag/eval/scoreboard.csv")
DEFAULT_OUT = Path("docs/ablation.png")

METRICS = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
COLORS  = ["#2196F3", "#4CAF50", "#FF9800", "#E91E63"]
LABELS  = ["Faithfulness", "Answer Relevancy", "Context Precision", "Context Recall"]


def load_scoreboard(path: Path = SCOREBOARD) -> list[dict]:
    if not path.exists():
        raise FileNotFoundError(f"Scoreboard not found: {path}. Run harness first.")
    rows = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows.append(row)
    return rows


def plot(out: Path = DEFAULT_OUT) -> None:
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    import numpy as np

    rows = load_scoreboard()
    if not rows:
        print("Scoreboard is empty — run harness first.")
        return

    labels    = [r["label"] for r in rows]
    n_vars    = len(labels)
    n_metrics = len(METRICS)

    x = np.arange(n_vars)
    width = 0.18
    offsets = np.linspace(-(n_metrics - 1) / 2, (n_metrics - 1) / 2, n_metrics) * width

    fig, ax = plt.subplots(figsize=(max(10, n_vars * 2.5), 6))

    for i, (metric, color, ml) in enumerate(zip(METRICS, COLORS, LABELS)):
        values = [float(r.get(metric, 0) or 0) for r in rows]
        bars = ax.bar(x + offsets[i], values, width, label=ml, color=color, alpha=0.85)
        # Value labels on bars
        for bar, val in zip(bars, values):
            if val > 0:
                ax.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height() + 0.01,
                    f"{val:.2f}",
                    ha="center", va="bottom", fontsize=7, color="#333",
                )

    ax.set_xticks(x)
    ax.set_xticklabels(labels, rotation=20, ha="right", fontsize=9)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel("Score (0–1)", fontsize=11)
    ax.set_title("Pipeline Ablation — RAGAS Metrics", fontsize=13, fontweight="bold")
    ax.legend(loc="upper right", fontsize=9)
    ax.axhline(0.5, color="#ccc", linestyle="--", linewidth=0.8)
    ax.grid(axis="y", alpha=0.3)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    # Annotate which is baseline
    if labels:
        ax.annotate(
            "baseline →",
            xy=(0, float(rows[0].get("faithfulness", 0) or 0)),
            xytext=(0.3, 0.95),
            textcoords="axes fraction",
            fontsize=8, color="#666",
        )

    out.parent.mkdir(parents=True, exist_ok=True)
    plt.tight_layout()
    plt.savefig(out, dpi=150)
    plt.close()
    print(f"  Saved → {out}")


def print_scoreboard() -> None:
    """Print scoreboard as a readable table."""
    rows = load_scoreboard()
    if not rows:
        print("Scoreboard is empty.")
        return

    cols = ["label", "faithfulness", "answer_relevancy", "context_precision",
            "context_recall", "avg_latency_ms", "n_questions", "timestamp"]

    header = f"{'label':30} {'faith':6} {'relev':6} {'prec':6} {'recall':6} {'ms':6} {'n':4}"
    print(f"\n{'='*70}")
    print(header)
    print("-" * 70)
    for r in rows:
        print(
            f"{r.get('label',''):30} "
            f"{float(r.get('faithfulness',0) or 0):.3f}  "
            f"{float(r.get('answer_relevancy',0) or 0):.3f}  "
            f"{float(r.get('context_precision',0) or 0):.3f}  "
            f"{float(r.get('context_recall',0) or 0):.3f}  "
            f"{float(r.get('avg_latency_ms',0) or 0):6.0f}  "
            f"{r.get('n_questions',''):4}"
        )
    print("=" * 70 + "\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Plot ablation chart")
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    parser.add_argument("--print-only", action="store_true",
                        help="Just print the scoreboard table, no chart")
    args = parser.parse_args()

    if args.print_only:
        print_scoreboard()
    else:
        print_scoreboard()
        plot(Path(args.out))
