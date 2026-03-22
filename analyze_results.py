#!/usr/bin/env python3
"""
analyze_results.py
==================
Reads every run_XX_... folder inside analysis_results/,
parses meta.json + output.log, then produces:
  • chart_cut_vs_config.png       — Max-Cut per run (bar chart)
  • chart_runtime.png             — Runtime per run (bar chart)
  • chart_p_comparison_n15.png    — p=1/2/3 effect on n=15 (grouped bar)
  • chart_scatter_nodes_cut.png   — Scatter: nodes vs cut grouped by p
  • chart_shots_vs_cut.png        — Shots vs cut for n=15 configs
  • chart_edge_vs_cut.png         — Edge count vs Max-Cut (scatter)
  • analysis_report.md            — Markdown summary with tables
Usage:
  python analyze_results.py <results_dir>
"""

import sys, os, json, re, glob
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# ── Colour palette ────────────────────────────────────────────────
BG, FG    = "#0F1117", "#E8EAF6"
COL_A     = "#4FC3F7"
COL_B     = "#EF9A9A"
COL_CUT   = "#FFD54F"
COL_G     = "#A5D6A7"

def _dark():
    plt.rcParams.update({
        "figure.facecolor": BG, "axes.facecolor": BG,
        "text.color": FG,       "axes.labelcolor": FG,
        "xtick.color": FG,      "ytick.color": FG,
        "axes.edgecolor": "#2C2C3C", "grid.color": "#2C2C3C",
        "font.family": "monospace",
    })


# ── Parsers ───────────────────────────────────────────────────────

def _parse_log(path):
    out = {"best_cut": None, "best_bitstring": None,
           "nodes_loaded": None, "edges_loaded": None}
    if not os.path.exists(path):
        return out
    txt = open(path).read()

    m = re.search(r"→ (\d+) nodes", txt)
    if m: out["nodes_loaded"] = int(m.group(1))

    m = re.search(r"→ (\d+) edges", txt)
    if m: out["edges_loaded"] = int(m.group(1))

    m = re.search(r"Best bitstring\s*:\s*(\S+)", txt)
    if m: out["best_bitstring"] = m.group(1)

    m = re.search(r"Max-Cut value\s*:\s*([\d.]+)", txt)
    if m: out["best_cut"] = float(m.group(1))

    return out


def load_runs(results_dir):
    runs = []
    for d in sorted(glob.glob(os.path.join(results_dir, "run_*"))):
        meta_f = os.path.join(d, "meta.json")
        if not os.path.exists(meta_f):
            continue
        meta = json.load(open(meta_f))
        log  = _parse_log(os.path.join(d, "output.log"))
        runs.append({**meta, **log,
                     "run_dir": d,
                     "run_name": os.path.basename(d)})
    return runs


# ── Chart helpers ─────────────────────────────────────────────────

def _save(fig, path):
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"    ✓ {os.path.basename(path)}")


def _bar_annotate(ax, bars, vals, fmt="{:.0f}"):
    for bar, v in zip(bars, vals):
        ax.text(bar.get_x() + bar.get_width()/2,
                bar.get_height() + max(vals)*0.01,
                fmt.format(v), ha="center", va="bottom",
                fontsize=7.5, color=FG)


# ── 1. Max-Cut per run ────────────────────────────────────────────

def chart_cut_vs_config(runs, out_dir):
    _dark()
    valid = [r for r in runs if r.get("best_cut") is not None]
    if not valid: return

    labels = [f"n={r['nodes']}\np={r['p']}" for r in valid]
    cuts   = [r["best_cut"] for r in valid]
    nodes  = [r["nodes"] for r in valid]
    norm   = plt.Normalize(min(nodes), max(nodes))
    colors = [plt.cm.plasma(norm(n)) for n in nodes]

    fig, ax = plt.subplots(figsize=(14, 5), facecolor=BG)
    ax.set_facecolor(BG)
    bars = ax.bar(range(len(valid)), cuts, color=colors,
                  edgecolor="#1A1A2E", linewidth=0.8)
    _bar_annotate(ax, bars, cuts)

    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("Best Max-Cut Value")
    ax.set_title("Max-Cut Value — All 15 Configurations", fontsize=13, pad=14)
    ax.grid(axis="y", alpha=0.25)

    sm = plt.cm.ScalarMappable(cmap="plasma", norm=norm)
    sm.set_array([])
    cb = plt.colorbar(sm, ax=ax, pad=0.02, fraction=0.025)
    cb.set_label("Node Count", fontsize=9)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, "chart_cut_vs_config.png"))


# ── 2. Runtime bar chart ──────────────────────────────────────────

def chart_runtime(runs, out_dir):
    _dark()
    valid = [r for r in runs if r.get("duration_sec") is not None]
    if not valid: return

    labels   = [f"n={r['nodes']}\np={r['p']}" for r in valid]
    runtimes = [r["duration_sec"] for r in valid]
    colors   = [COL_A if r["status"] == "SUCCESS" else COL_B for r in valid]

    fig, ax = plt.subplots(figsize=(14, 5), facecolor=BG)
    ax.set_facecolor(BG)
    bars = ax.bar(range(len(valid)), runtimes, color=colors,
                  edgecolor="#1A1A2E", linewidth=0.8)
    _bar_annotate(ax, bars, runtimes, fmt="{:.0f}s")

    ax.set_xticks(range(len(valid)))
    ax.set_xticklabels(labels, fontsize=7.5)
    ax.set_ylabel("Runtime (seconds)")
    ax.set_title("Execution Time per Configuration", fontsize=13, pad=14)
    ax.grid(axis="y", alpha=0.25)

    ax.legend(handles=[
        mpatches.Patch(color=COL_A, label="Success"),
        mpatches.Patch(color=COL_B, label="Failed"),
    ], facecolor="#1A1A2E", edgecolor=COL_A, labelcolor=FG)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, "chart_runtime.png"))


# ── 3. p comparison for n=15 ─────────────────────────────────────

def chart_p_comparison(runs, out_dir):
    _dark()
    n15 = sorted(
        [r for r in runs if r["nodes"] == 15 and r.get("best_cut") is not None],
        key=lambda r: r["p"]
    )
    if not n15: return

    colors = [COL_A, COL_CUT, COL_B]
    fig, axes = plt.subplots(1, 2, figsize=(12, 5), facecolor=BG)

    # Left: cut value
    ax = axes[0]
    ax.set_facecolor(BG)
    cuts = [r["best_cut"] for r in n15]
    p_labels = [f"p={r['p']}" for r in n15]
    bars = ax.bar(range(len(n15)), cuts,
                  color=colors[:len(n15)], edgecolor="#1A1A2E")
    _bar_annotate(ax, bars, cuts)
    ax.set_xticks(range(len(n15)))
    ax.set_xticklabels(p_labels, fontsize=10)
    ax.set_ylabel("Max-Cut Value")
    ax.set_title("Effect of p on Max-Cut (n=15)", fontsize=11, pad=10)
    ax.grid(axis="y", alpha=0.25)

    # Right: runtime
    ax = axes[1]
    ax.set_facecolor(BG)
    times = [r.get("duration_sec", 0) for r in n15]
    bars = ax.bar(range(len(n15)), times,
                  color=colors[:len(n15)], edgecolor="#1A1A2E")
    _bar_annotate(ax, bars, times, fmt="{:.0f}s")
    ax.set_xticks(range(len(n15)))
    ax.set_xticklabels(p_labels, fontsize=10)
    ax.set_ylabel("Runtime (s)")
    ax.set_title("Runtime vs p (n=15)", fontsize=11, pad=10)
    ax.grid(axis="y", alpha=0.25)

    plt.suptitle("QAOA Depth (p) Comparison  —  n=15 Nodes",
                 color=FG, fontsize=13, y=1.02)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, "chart_p_comparison_n15.png"))


# ── 4. Scatter: nodes vs cut, coloured by p ──────────────────────

def chart_scatter_nodes_cut(runs, out_dir):
    _dark()
    valid = [r for r in runs if r.get("best_cut") is not None]
    if not valid: return

    fig, ax = plt.subplots(figsize=(10, 6), facecolor=BG)
    ax.set_facecolor(BG)

    p_col = {1: COL_A, 2: COL_CUT, 3: COL_B}
    for pv, col in p_col.items():
        sub = [r for r in valid if r["p"] == pv]
        if not sub: continue
        xs = [r["nodes"] for r in sub]
        ys = [r["best_cut"] for r in sub]
        ax.scatter(xs, ys, color=col, s=110, label=f"p={pv}",
                   edgecolors="white", linewidths=1.2, zorder=5)
        if len(xs) > 1:
            z = np.polyfit(xs, ys, 1)
            xl = np.linspace(min(xs), max(xs), 100)
            ax.plot(xl, np.poly1d(z)(xl), color=col,
                    alpha=0.45, linewidth=1.5, linestyle="--")

    ax.set_xlabel("Number of Nodes")
    ax.set_ylabel("Best Max-Cut Value")
    ax.set_title("Nodes vs Max-Cut (grouped by QAOA depth p)", fontsize=12, pad=12)
    ax.legend(facecolor="#1A1A2E", edgecolor=COL_A, labelcolor=FG)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, "chart_scatter_nodes_cut.png"))


# ── 5. Shots vs cut for n=15 ─────────────────────────────────────

def chart_shots_vs_cut(runs, out_dir):
    _dark()
    n15 = sorted(
        [r for r in runs if r["nodes"] == 15 and r.get("best_cut") is not None],
        key=lambda r: r["shots"]
    )
    if len(n15) < 2: return

    fig, ax = plt.subplots(figsize=(8, 5), facecolor=BG)
    ax.set_facecolor(BG)
    xs = [r["shots"] for r in n15]
    ys = [r["best_cut"] for r in n15]
    ax.plot(xs, ys, color=COL_A, linewidth=2, marker="o",
            markersize=9, markeredgecolor="white", markeredgewidth=1.2)
    for x, y, r in zip(xs, ys, n15):
        ax.annotate(f"p={r['p']}\n{y:.0f}", (x, y),
                    textcoords="offset points", xytext=(0, 12),
                    ha="center", fontsize=8, color=FG)
    ax.set_xscale("log")
    ax.set_xlabel("Shots (log scale)")
    ax.set_ylabel("Max-Cut Value")
    ax.set_title("Shots vs Max-Cut Value  —  n=15 Configs", fontsize=12, pad=12)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, "chart_shots_vs_cut.png"))


# ── 6. Edge count vs Max-Cut scatter ─────────────────────────────

def chart_edge_vs_cut(runs, out_dir):
    _dark()
    valid = [r for r in runs
             if r.get("best_cut") is not None
             and r.get("edges_loaded") is not None]
    if not valid: return

    fig, ax = plt.subplots(figsize=(9, 5), facecolor=BG)
    ax.set_facecolor(BG)
    xs = [r["edges_loaded"] for r in valid]
    ys = [r["best_cut"] for r in valid]
    ns = [r["nodes"] for r in valid]
    norm = plt.Normalize(min(ns), max(ns))
    sc = ax.scatter(xs, ys, c=[norm(n) for n in ns], cmap="viridis",
                    s=100, edgecolors="white", linewidths=1.0, zorder=5)
    if len(xs) > 1:
        z = np.polyfit(xs, ys, 1)
        xl = np.linspace(min(xs), max(xs), 100)
        ax.plot(xl, np.poly1d(z)(xl), color=COL_CUT,
                linewidth=1.5, linestyle="--", label="trend")

    cb = plt.colorbar(sc, ax=ax, pad=0.02, fraction=0.025)
    cb.set_label("Node Count", fontsize=9)
    ax.set_xlabel("Number of Edges")
    ax.set_ylabel("Best Max-Cut Value")
    ax.set_title("Edge Count vs Max-Cut Value", fontsize=12, pad=12)
    ax.grid(alpha=0.25)
    plt.tight_layout()
    _save(fig, os.path.join(out_dir, "chart_edge_vs_cut.png"))


# ── Markdown report ───────────────────────────────────────────────

def write_report(runs, out_dir):
    valid  = [r for r in runs if r.get("best_cut") is not None]
    failed = [r for r in runs if r.get("status") == "FAILED"]
    best   = max(valid, key=lambda r: r["best_cut"]) if valid else None
    fastest = min(valid, key=lambda r: r.get("duration_sec", 9e9)) if valid else None

    lines = []
    lines += [
        "# QAOA Social Network — Experiment Analysis Report\n\n",
        f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n",
        "---\n\n",
        "## Overview\n\n",
        f"| Metric | Value |\n|--------|-------|\n",
        f"| Total runs | {len(runs)} |\n",
        f"| Successful | {len(valid)} |\n",
        f"| Failed | {len(failed)} |\n",
    ]
    if valid:
        total_t = sum(r.get("duration_sec", 0) for r in valid)
        avg_t   = total_t / len(valid)
        lines += [
            f"| Total runtime | {total_t}s |\n",
            f"| Avg runtime / run | {avg_t:.1f}s |\n",
        ]
    lines.append("\n")

    # Summary table
    lines += [
        "## Configuration & Results\n\n",
        "| # | n | p | shots | max_iter | top_k | Max-Cut | Bitstring | Time | Status |\n",
        "|---|---|---|-------|----------|-------|---------|-----------|------|--------|\n",
    ]
    for r in runs:
        cut = f"{r['best_cut']:.0f}" if r.get("best_cut") else "—"
        bs  = (r.get("best_bitstring") or "—")
        bs  = bs[:12] + "…" if len(bs) > 12 else bs
        icon = "✅" if r.get("status") == "SUCCESS" else "❌"
        lines.append(
            f"| {r['run']} | {r['nodes']} | {r['p']} | {r['shots']} "
            f"| {r['max_iter']} | {r['top_k']} | {cut} | `{bs}` "
            f"| {r.get('duration_sec','?')}s | {icon} |\n"
        )
    lines.append("\n")

    # Key findings
    lines.append("## Key Findings\n\n")
    if best:
        lines += [
            f"### 🏆 Best Max-Cut\n",
            f"- **Run {best['run']}** — n={best['nodes']}, p={best['p']}, shots={best['shots']}\n",
            f"- Max-Cut Value: **{best['best_cut']:.0f}**\n",
            f"- Bitstring: `{best.get('best_bitstring','?')}`\n\n",
        ]
    if fastest:
        lines += [
            f"### ⚡ Fastest Run\n",
            f"- **Run {fastest['run']}** — n={fastest['nodes']}, p={fastest['p']}, shots={fastest['shots']}\n",
            f"- Runtime: **{fastest.get('duration_sec','?')}s**\n\n",
        ]

    # Node-group averages
    if valid:
        from collections import defaultdict
        ng = defaultdict(list)
        for r in valid: ng[r["nodes"]].append(r["best_cut"])
        lines += [
            "### Effect of Node Count on Max-Cut\n\n",
            "| Nodes | Avg Cut | Max Cut |\n|-------|---------|----------|\n",
        ]
        for n in sorted(ng):
            vals = ng[n]
            lines.append(f"| {n} | {sum(vals)/len(vals):.1f} | {max(vals):.0f} |\n")
        lines.append("\n")

    # p comparison for n=15
    n15 = sorted([r for r in valid if r["nodes"] == 15], key=lambda r: r["p"])
    if n15:
        lines += [
            "### QAOA Depth (p) Comparison — n=15\n\n",
            "| p | shots | Max-Cut | Runtime |\n|---|-------|---------|----------|\n",
        ]
        for r in n15:
            lines.append(f"| {r['p']} | {r['shots']} | {r['best_cut']:.0f} | {r.get('duration_sec','?')}s |\n")
        bp = max(n15, key=lambda r: r["best_cut"])
        lines.append(f"\n> Best depth for n=15: **p={bp['p']}** → cut={bp['best_cut']:.0f}\n\n")

    # Charts section
    lines += [
        "## Generated Charts\n\n",
        "| File | Description |\n|------|-------------|\n",
        "| `chart_cut_vs_config.png` | Max-Cut value across all 15 runs |\n",
        "| `chart_runtime.png` | Execution time per configuration |\n",
        "| `chart_p_comparison_n15.png` | Effect of QAOA depth p on n=15 |\n",
        "| `chart_scatter_nodes_cut.png` | Scatter: nodes vs cut grouped by p |\n",
        "| `chart_shots_vs_cut.png` | Shots vs cut value for n=15 configs |\n",
        "| `chart_edge_vs_cut.png` | Edge count vs Max-Cut scatter |\n",
        "\n",
    ]

    # Per-run list
    lines.append("## Per-Run Output Files\n\n")
    for r in runs:
        cut  = f"{r['best_cut']:.0f}" if r.get("best_cut") else "N/A"
        icon = "✅" if r.get("status") == "SUCCESS" else "❌"
        lines += [
            f"### {icon} Run {r['run']} — `{r['run_name']}`\n",
            f"n={r['nodes']}, p={r['p']}, shots={r['shots']}, "
            f"max_iter={r['max_iter']}, top_k={r['top_k']}  \n",
            f"Max-Cut: **{cut}** | Bitstring: `{r.get('best_bitstring','?')}`  \n",
            f"Duration: {r.get('duration_sec','?')}s\n\n",
        ]

    path = os.path.join(out_dir, "analysis_report.md")
    with open(path, "w") as f:
        f.writelines(lines)
    print(f"    ✓ analysis_report.md")
    return path


# ── Entry point ───────────────────────────────────────────────────

def main():
    results_dir = sys.argv[1] if len(sys.argv) > 1 else "./analysis_results"
    print(f"\n{'═'*55}")
    print(f"  QAOA Analysis  —  {results_dir}")
    print(f"{'═'*55}")

    runs = load_runs(results_dir)
    if not runs:
        print(f"  ✗ No run folders found in {results_dir}")
        sys.exit(1)

    print(f"  Loaded {len(runs)} run(s). Generating charts…\n")
    _dark()

    chart_cut_vs_config(runs, results_dir)
    chart_runtime(runs, results_dir)
    chart_p_comparison(runs, results_dir)
    chart_scatter_nodes_cut(runs, results_dir)
    chart_shots_vs_cut(runs, results_dir)
    chart_edge_vs_cut(runs, results_dir)
    write_report(runs, results_dir)

    print(f"\n  ✅ Done!  Report → {results_dir}/analysis_report.md")
    print(f"{'═'*55}\n")


if __name__ == "__main__":
    main()
