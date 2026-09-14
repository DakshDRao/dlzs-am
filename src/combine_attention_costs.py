"""Join attention top-k results with committed post-route hardware costs.

The attention run supplies mean/min/max overlap.  The repository's
``synth_result`` summaries supply implementation LUTs, FFs, DSP count, Fmax,
and WNS.  This creates the table needed for the Week 10--11 application gate.

Run from the repository root:
  python src/combine_attention_costs.py \
      --attention-run results/attention_corpus_eval/<run> \
      --synth-root synth_result
"""

import argparse
import csv
import hashlib
import json
from pathlib import Path


HARDWARE = {
    "dlzs_snap_q": "dlzs_opt",
    "dlzs_snap_k": "dlzs_opt",
    "drum3": "drum_opt3",
    "drum4": "drum_opt4",
    "drum6": "drum_opt6",
    "mitchell": "mitchell",
    "exact_int16": "exact_lut",
}


def read_csv(path):
    with path.open(newline="", encoding="utf-8") as stream:
        return list(csv.DictReader(stream))


def parse_summary(path):
    values = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        parts = line.split(None, 1)
        if len(parts) == 2:
            values[parts[0]] = parts[1].strip()
    return values


def number(values, key, integer=False):
    value = values.get(key, "")
    if value.lower() in {"", "n/a", "na", "none"}:
        return None
    return int(value) if integer else float(value)


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attention-run", required=True, type=Path)
    parser.add_argument("--synth-root", type=Path, default=Path("synth_result"))
    parser.add_argument("--percent", type=int, default=10)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.percent not in range(5, 51, 5):
        parser.error("--percent must be one of 5, 10, ..., 50")

    run = args.attention_run.resolve()
    synth_root = args.synth_root.resolve()
    corrected = run / "summary_corrected.csv"
    summary_path = corrected if corrected.is_file() else run / "summary.csv"
    summary = read_csv(summary_path)
    manifest_path = run / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.is_file() else {}
    selected = [row for row in summary
                if row["baseline"] == "quantized_exact" and
                int(row["percent"]) == args.percent and
                row["design"] in HARDWARE]
    if set(row["design"] for row in selected) != set(HARDWARE):
        raise ValueError("Attention summary is missing one or more expected designs.")

    rows = []
    for row in selected:
        design = row["design"]
        hardware_design = HARDWARE[design]
        report_path = synth_root / hardware_design / "summary.txt"
        if not report_path.is_file():
            raise FileNotFoundError(report_path)
        report = parse_summary(report_path)
        wns = number(report, "impl_wns_ns")
        rows.append({
            "attention_design": design,
            "hardware_design": hardware_design,
            "percent": args.percent,
            "mean_overlap": float(row["mean_overlap"]),
            "min_text_overlap": float(row.get("min_text_overlap", row.get("min_overlap", "nan"))),
            "max_text_overlap": float(row.get("max_text_overlap", row.get("max_overlap", "nan"))),
            "impl_luts": number(report, "impl_luts", integer=True),
            "impl_ffs": number(report, "impl_ffs", integer=True),
            "impl_dsps": number(report, "impl_dsps", integer=True),
            "impl_fmax_mhz": number(report, "impl_fmax_mhz"),
            "impl_wns_ns": wns,
            "meets_100mhz_constraint": None if wns is None else wns >= 0.0,
        })
    order = {name: index for index, name in enumerate(
        ("exact_int16", "dlzs_snap_q", "dlzs_snap_k", "drum3", "drum4", "drum6", "mitchell"))}
    rows.sort(key=lambda row: order[row["attention_design"]])
    output = args.output.resolve() if args.output else run / "attention_cost_table.csv"
    output.parent.mkdir(parents=True, exist_ok=True)
    write_csv(output, rows)
    metadata = {
        "format": "dlzs_attention_cost_table_v1",
        "source_attention_run": str(run),
        "source_attention_summary": str(summary_path),
        "source_synthesis_root": str(synth_root),
        "source_attention_sha256": hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        "percent": args.percent,
        "corpus_count": manifest.get("text_count"),
        "device_name": manifest.get("device_name"),
        "timing_note": "Fmax and WNS are post-route OOC report values; they are not board measurements.",
        "mapping_note": "Both DLZS snap directions use the same dlzs_opt hardware cost because the direction changes the software operand assignment, not the RTL core.",
        "rows": rows,
    }
    (output.with_suffix(".json")).write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Saved: {output}")
    print(f"Saved: {output.with_suffix('.json')}")
    print("\nDesign              overlap  min-text  LUTs  Fmax(MHz)  WNS(ns)")
    for item in rows:
        print(f"{item['attention_design']:19} {item['mean_overlap']:.4f}  "
              f"{item['min_text_overlap']:.4f}  {item['impl_luts']:>4}  "
              f"{str(item['impl_fmax_mhz']):>9}  {str(item['impl_wns_ns']):>7}")


if __name__ == "__main__":
    main()
