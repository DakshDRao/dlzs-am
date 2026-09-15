"""Plot top-k overlap from attention_multilayer.py summary.csv.

Run:
  python src/plot_attention_curves.py \
    --input results/attention_multilayer/<run>/summary.csv

The solid curves compare each design with exact signed-int16 scores, isolating
multiplier error. Dashed curves compare with original floating-point scores and
therefore include quantization plus multiplier error. Results are aggregated
over the saved text/layer/head rows by the multilayer runner.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.ticker import PercentFormatter, MultipleLocator

COLORS = {
    "exact_int16": "#202124",   # charcoal
    "dlzs_snap_q": "#D55E00",   # vermilion
    "dlzs_snap_k": "#E69F00",   # amber
    "dlzs_comp_q": "#0072B2",   # blue
    "dlzs_comp_k": "#56B4E9",   # sky blue
    "mitchell":    "#009E73",   # green
    "drum3":       "#CC79A7",   # pink
    "drum4":       "#7B4AB5",   # purple
    "drum6":       "#827343",   # olive
}

LABELS = {
    "exact_int16": "Exact INT16",
    "dlzs_snap_q": "DLZS · Q",
    "dlzs_snap_k": "DLZS · K",
    "dlzs_comp_q": "DLZS compensated · Q",
    "dlzs_comp_k": "DLZS compensated · K",
    "mitchell":    "Mitchell",
    "drum3":       "DRUM-3",
    "drum4":       "DRUM-4",
    "drum6":       "DRUM-6",
}

MARKERS = {
    "exact_int16": "o",
    "dlzs_snap_q": "^",
    "dlzs_snap_k": "v",
    "dlzs_comp_q": "s",
    "dlzs_comp_k": "D",
    "mitchell":    "P",
    "drum3":       "X",
    "drum4":       "h",
    "drum6":       "p",
}


def load_rows(path):
    with path.open(newline="", encoding="utf-8") as stream:
        rows = list(csv.DictReader(stream))
    required = {"design", "baseline", "percent", "mean_overlap",
                "min_text_overlap", "max_text_overlap"}
    if not rows or not required.issubset(rows[0]):
        raise ValueError(f"{path} must be a multilayer summary.csv")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    rows = load_rows(args.input)
    out = args.output_dir or args.input.parent / "plots"
    out.mkdir(parents=True, exist_ok=True)
    percents = sorted({int(r["percent"]) for r in rows})
    designs = sorted({r["design"] for r in rows},
                     key=lambda d: ["exact_int16", "dlzs_snap_q", "dlzs_snap_k",
                                    "mitchell", "drum3", "drum4", "drum6"].index(d)
                     if d in ["exact_int16", "dlzs_snap_q", "dlzs_snap_k",
                              "mitchell", "drum3", "drum4", "drum6"] else 99)
    values = {}
    for design in designs:
        for baseline in ("quantized_exact", "float"):
            selected = [r for r in rows if r["design"] == design and r["baseline"] == baseline]
            values[(design, baseline)] = {int(r["percent"]): float(r["mean_overlap"])
                                          for r in selected}
        

    # Consistent order, including any future designs.
    order = list(COLORS)
    designs = sorted(
        designs,
        key=lambda d: (order.index(d) if d in order else len(order), d),
    )

    # Explicit fallback colors remain consistent between panels.
    unknown = [d for d in designs if d not in COLORS]
    fallback = plt.get_cmap("tab20")
    plot_colors = dict(COLORS)
    for i, design in enumerate(unknown):
        plot_colors[design] = fallback(i % 20)

    style = {
        "font.family": "DejaVu Sans",
        "font.size": 11,
        "axes.titlesize": 13,
        "axes.labelsize": 11,
        "axes.edgecolor": "#B8BEC7",
        "axes.labelcolor": "#343A40",
        "xtick.color": "#505862",
        "ytick.color": "#505862",
        "svg.fonttype": "none",
        "pdf.fonttype": 42,
    }

    with plt.rc_context(style):
        fig, ax = plt.subplots(figsize=(9, 6.4))
        fig.patch.set_facecolor("white")
        ax.set_axisbelow(True)

        ax.axvline(
            10, color="#88929E", linestyle=":",
            linewidth=1.2, alpha=0.8, zorder=0,
        )

        plotted_y = []

        for design in designs:
            series = values.get((design, "quantized_exact"), {})
            if not series:
                continue

            xs = sorted(series)
            ys = [series[p] for p in xs]
            plotted_y.extend(ys)
            compensated = design.startswith("dlzs_comp")

            ax.plot(
                xs, ys,
                label=LABELS.get(design, design),
                color=plot_colors[design],
                marker=MARKERS.get(design, "o"),
                linewidth=2.5 if compensated else 1.8,
                markersize=6.5 if compensated else 5.5,
                markeredgecolor="white",
                markeredgewidth=0.7,
                zorder=4 if compensated else 3,
            )

        if not plotted_y:
            raise ValueError("No quantized_exact rows found in the summary.")

        ax.set_title(
            "Attention ranking preservation",
            loc="left", fontsize=16, fontweight="bold", pad=30,
        )
        ax.text(
            0, 1.025,
            "Multiplier error only · Reference: exact INT16 scores",
            transform=ax.transAxes, fontsize=10, color="#68727E",
        )

        ax.set_xlabel("Selected keys per attention row (%)", labelpad=10)
        ax.set_ylabel("Top-k index overlap", labelpad=12)
        ax.set_xticks(percents)
        ax.set_ylim(min(0.80, max(0.0, min(plotted_y) - 0.02)), 1.008)
        ax.margins(x=0.04)
        ax.yaxis.set_major_formatter(PercentFormatter(xmax=1))
        ax.yaxis.set_major_locator(MultipleLocator(0.025))

        ax.grid(axis="y", color="#DDE2E8", linewidth=0.8)
        ax.grid(axis="x", color="#EDF0F4", linewidth=0.6)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(length=0, pad=7)

        handles, labels = ax.get_legend_handles_labels()
        fig.legend(
            handles, labels,
            loc="lower center",
            bbox_to_anchor=(0.5, 0.015),
            ncol=3, frameon=False, fontsize=9,
            handlelength=2.8, columnspacing=1.8, labelspacing=0.9,
        )

        fig.tight_layout(rect=(0, 0.19, 1, 1))
        fig.savefig(out / "topk_overlap.png", dpi=300, bbox_inches="tight")
        fig.savefig(out / "topk_overlap.svg", bbox_inches="tight")
        fig.savefig(out / "topk_overlap.pdf", bbox_inches="tight")
        plt.close(fig)

    # Preserve the plotted values and source provenance beside the figure.
    plotted = []
    for design in designs:
        for baseline in ("quantized_exact",):
            for percent in percents:
                row = next((r for r in rows if r["design"] == design and
                            r["baseline"] == baseline and int(r["percent"]) == percent), None)
                if row:
                    plotted.append({"design": design, "baseline": baseline,
                                    "percent": percent,
                                    "mean_overlap": float(row["mean_overlap"]),
                                    "min_text_overlap": float(row["min_text_overlap"]),
                                    "max_text_overlap": float(row["max_text_overlap"])})
    (out / "plotted_values.json").write_text(json.dumps({
        "source_summary": str(args.input.resolve()),
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "aggregation": "values as saved by attention_multilayer.py",
        "plots": [
            "topk_overlap.png",
            "topk_overlap.svg",
            "topk_overlap.pdf",
        ],
        "values": plotted,
    }, indent=2), encoding="utf-8")
    print(f"Saved: {(out / 'topk_overlap.png').resolve()}")
    print(f"Saved: {(out / 'topk_overlap.svg').resolve()}")
    print(f"Saved: {(out / 'plotted_values.json').resolve()}")


if __name__ == "__main__":
    main()
