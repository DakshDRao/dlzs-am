"""Audit a completed fixed-corpus attention evaluation.

This reports the hardest passages at one top-k percentage and summarizes the
per-design score error. It does not rerun the model or create plots.

Run:
  python src/audit_attention_run.py \
      --input results/attention_corpus_eval/<run>
"""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, pstdev


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    if not rows:
        return
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="Completed attention_corpus_eval run directory")
    parser.add_argument("--percent", type=int, default=10)
    parser.add_argument("--bottom", type=int, default=5,
                        help="Number of hardest passages to list per design")
    args = parser.parse_args()
    if args.percent not in range(5, 51, 5):
        parser.error("--percent must be one of 5, 10, ..., 50")
    if args.bottom < 1:
        parser.error("--bottom must be positive")

    run = args.input.resolve()
    manifest = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    summary = read_csv(run / "summary.csv")
    per_text = read_csv(run / "per_text.csv")
    score_errors = read_csv(run / "score_errors.csv")
    texts = manifest.get("texts", [])
    lengths = manifest.get("valid_token_lengths", [])
    truncated = manifest.get("truncated", [])
    if len(texts) != manifest.get("text_count"):
        raise ValueError("Manifest text count does not match its text list.")

    selected = [row for row in per_text
                if row["baseline"] == "quantized_exact" and
                int(row["percent"]) == args.percent]
    designs = sorted({row["design"] for row in selected})
    outlier_rows = []
    for design in designs:
        rows = sorted((row for row in selected if row["design"] == design),
                      key=lambda row: float(row["mean_overlap"]))
        for rank, row in enumerate(rows[:args.bottom], start=1):
            sample = int(row["sample"])
            outlier_rows.append({
                "design": design,
                "rank": rank,
                "sample": sample,
                "mean_overlap": float(row["mean_overlap"]),
                "valid_tokens": lengths[sample],
                "truncated": truncated[sample],
                "text": texts[sample],
            })

    design_rows = []
    for design in designs:
        values = [float(row["mean_overlap"]) for row in selected if row["design"] == design]
        error_values = [float(row["score_mae_vs_quantized_exact"])
                        for row in score_errors if row["design"] == design]
        design_rows.append({
            "design": design,
            "percent": args.percent,
            "passage_mean": mean(values),
            "passage_std": pstdev(values) if len(values) > 1 else 0.0,
            "passage_min": min(values),
            "passage_max": max(values),
            "mean_layer_score_mae": mean(error_values) if error_values else None,
            "max_layer_score_mae": max(error_values) if error_values else None,
        })

    exact_rows = [row for row in selected if row["design"] == "exact_int16"]
    if not exact_rows or any(float(row["mean_overlap"]) != 1.0 for row in exact_rows):
        raise RuntimeError("Exact int16 identity check failed in the audit input.")

    result = {
        "format": "dlzs_attention_run_audit_v1",
        "source_run": str(run),
        "source_corpus_sha256": manifest.get("corpus_sha256"),
        "device": manifest.get("device"),
        "device_name": manifest.get("device_name"),
        "text_count": manifest.get("text_count"),
        "percent": args.percent,
        "hardest_passages": outlier_rows,
        "design_summary": design_rows,
        "interpretation": "Passage-level means are averaged over all six layers and heads; low minima identify hard cases for inspection.",
    }
    (run / "outlier_report.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    write_csv(run / "outliers_10pct.csv", outlier_rows)
    write_csv(run / "design_summary.csv", design_rows)

    print(f"Run: {run}")
    print(f"Device: {manifest.get('device_name')} ({manifest.get('device')})")
    print(f"Corpus passages: {manifest.get('text_count')}")
    print(f"\nHardest passages at {args.percent}% selection:")
    print("design              rank  sample  overlap  tokens  truncated")
    for row in outlier_rows:
        print(f"{row['design']:19} {row['rank']:>4} {row['sample']:>7} "
              f"{row['mean_overlap']:>8.4f} {row['valid_tokens']:>7} {str(row['truncated']):>9}")
    print(f"\nSaved: {run / 'outlier_report.json'}")
    print(f"Saved: {run / 'outliers_10pct.csv'}")
    print(f"Saved: {run / 'design_summary.csv'}")


if __name__ == "__main__":
    main()
