"""Repair passage-level ranges in an existing attention corpus run.

Older evaluator versions printed the minimum nested layer/head overlap as the
"text range".  The global means were unaffected, but this script recalculates
the correctly labelled passage-level range from per_text.csv without rerunning
the model or multiplier scoring.

Run:
  python src/repair_attention_summary.py \
      --input results/attention_corpus_eval/<run>
"""

import argparse
import csv
from pathlib import Path


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    args = parser.parse_args()
    run = args.input.resolve()
    summary_path = run / "summary.csv"
    per_text_path = run / "per_text.csv"
    summary = read_csv(summary_path)
    per_text = read_csv(per_text_path)
    for row in summary:
        values = [float(text_row["mean_overlap"]) for text_row in per_text
                  if text_row["design"] == row["design"] and
                  text_row["baseline"] == row["baseline"] and
                  text_row["percent"] == row["percent"]]
        if not values:
            raise ValueError(f"No per-text rows for {row['design']} {row['baseline']} {row['percent']}%")
        row["min_text_overlap"] = min(values)
        row["max_text_overlap"] = max(values)
    corrected = run / "summary_corrected.csv"
    write_csv(corrected, summary)
    print(f"Saved corrected summary: {corrected}")
    print("Corrected 10% passage ranges:")
    for row in summary:
        if row["baseline"] == "quantized_exact" and row["percent"] == "10":
            print(f"{row['design']:19} mean={float(row['mean_overlap']):.4f}  "
                  f"text range=[{float(row['min_text_overlap']):.4f}, "
                  f"{float(row['max_text_overlap']):.4f}]")


if __name__ == "__main__":
    main()
