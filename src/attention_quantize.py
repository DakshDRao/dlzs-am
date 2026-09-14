"""Step 3: exact signed-16-bit quantization baseline on verified Q/K.

Run from any directory:
 python src/attention_quantize.py --input /path/to/attention_sanity/run

This uses dynamic per-sample, per-head symmetric scales, separately for Q/K.
One scale covers ALL valid tokens and features in that sample/head. It is
not per-token scaling, and it is not a fixed binary-point hardware format.
This debugging baseline does not establish application accuracy.
"""
import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import numpy as np


def quantize(values, valid):
    values = values.astype(np.float64)
    masked = np.where(valid[:, None, :, None], values, 0.0)
    maximum = np.max(np.abs(masked), axis=(2, 3), keepdims=True)
    scale = np.where(maximum > 0, maximum / 32767.0, 1.0)
    rounded = np.rint(masked / scale)  # nearest, ties to even
    clipped = np.count_nonzero((rounded < -32767) | (rounded > 32767))
    integers = np.clip(rounded, -32767, 32767).astype(np.int16)
    return integers, scale, int(clipped)


def ranked_indices(scores):
    # Input key indices are in ascending order; stable sorting resolves ties
    # by smaller token index for every design.
    return np.argsort(-scores, kind="stable")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path,
                        help="Directory containing report.json and attention_tensors.npz")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "results/attention_quantization")
    args = parser.parse_args()
    source = args.input.resolve()
    with (source / "report.json").open(encoding="utf-8") as stream:
        source_report = json.load(stream)
    if source_report.get("passed") is not True:
        raise RuntimeError("Input reconstruction report must have passed.")
    with np.load(source / "attention_tensors.npz", allow_pickle=False) as data:
        q, k = data["q"], data["k"]
        valid = data["attention_mask"].astype(bool)
        input_ids = data["input_ids"]
    if q.shape != k.shape or q.ndim != 4 or valid.shape != (q.shape[0], q.shape[2]):
        raise RuntimeError("Unexpected input shapes.")
    if not np.isfinite(q).all() or not np.isfinite(k).all() or not valid.any(axis=1).all():
        raise RuntimeError("Non-finite Q/K or empty sample.")
    qi, qs, qc = quantize(q, valid)
    ki, ks, kc = quantize(k, valid)
    dimension = q.shape[-1]
    bound = dimension * 32767**2
    if bound > np.iinfo(np.int64).max:
        raise RuntimeError("Accumulator bound exceeds int64.")
    # Cast BEFORE multiplication; both products and accumulation use int64.
    exact_integer = qi.astype(np.int64) @ ki.astype(np.int64).swapaxes(-1, -2)
    reference = q.astype(np.float64) @ k.astype(np.float64).swapaxes(-1, -2)
    reference /= np.sqrt(dimension)
    dequantized = exact_integer.astype(np.float64) * qs * ks / np.sqrt(dimension)
    # Independent floating-point dot products of the dequantized operands.
    check = (qi.astype(np.float64) * qs) @ (ki.astype(np.float64) * ks).swapaxes(-1, -2)
    check /= np.sqrt(dimension)
    np.testing.assert_allclose(dequantized, check, rtol=1e-10, atol=1e-10)
    pairs = np.broadcast_to(valid[:, None, :, None] & valid[:, None, None, :], reference.shape)
    error = dequantized[pairs] - reference[pairs]
    records = []
    for sample in range(q.shape[0]):
        ids = np.flatnonzero(valid[sample])
        for head in range(q.shape[1]):
            for query in ids:
                original = reference[sample, head, query, ids]
                quantized = exact_integer[sample, head, query, ids]
                order_ref = ranked_indices(original)
                order_quant = ranked_indices(quantized)
                for percent in range(5, 51, 5):
                    count = max(1, (percent * len(ids) + 99) // 100)
                    overlap = len(set(order_ref[:count]) & set(order_quant[:count])) / count
                    # Boundary ties make top-k sensitive to the tie policy.
                    tied = count < len(ids) and quantized[order_quant[count-1]] == quantized[order_quant[count]]
                    records.append(dict(sample=sample, head=head, query=int(query),
                                        valid_keys=len(ids), percent=percent, k=count,
                                        overlap=overlap, quantized_boundary_tie=bool(tied)))
    summary = []
    for percent in range(5, 51, 5):
        rows = [r for r in records if r["percent"] == percent]
        summary.append(dict(percent=percent,
                            mean_overlap=float(np.mean([r["overlap"] for r in rows])),
                            min_overlap=float(min(r["overlap"] for r in rows)),
                            rows=len(rows), boundary_tie_rows=sum(r["quantized_boundary_tie"] for r in rows)))
    report = {
        "passed": True, "source_directory": str(source),
        "model_revision": source_report["model_revision"], "numpy_version": np.__version__,
        "layer_index": source_report["layer_index"], "shape": list(q.shape),
        "quantization": {"range": [-32767, 32767], "storage": "int16",
                         "rounding": "nearest, ties to even", "zero_point": 0,
                         "scale": "dynamic per sample/head, separately Q and K, valid tokens only",
                         "zero_tensor_scale": 1.0, "clipped_values": qc+kc,
                         "accumulator": "int64", "absolute_accumulator_bound": bound},
        "score_mae": float(np.mean(np.abs(error))),
        "score_max_absolute_error": float(np.max(np.abs(error))),
        "topk": summary, "aggregation": "equal weight per valid query/head row",
        "ranking": "descending signed score; ties use ascending key index; k=ceil(percent*valid_keys/100)",
        "scope": "two-text debug quantization baseline, no approximate multiplication, no hardware results",
    }
    run_dir = args.output_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    run_dir.mkdir(parents=True, exist_ok=False)
    with (run_dir / "report.json").open("w", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    with (run_dir / "topk_rows.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    np.savez_compressed(run_dir / "quantized_tensors.npz", q_int=qi, k_int=ki,
                        q_scale=qs, k_scale=ks, exact_integer_scores=exact_integer,
                        float_scores=reference, dequantized_scores=dequantized,
                        attention_mask=valid, input_ids=input_ids)
    print("PASS: exact int64 dot products agree with dequantized-operand reconstruction.")
    print(f"Clipped values: {qc+kc}")
    print(f"Score MAE: {report['score_mae']:.9g}")
    print(f"Maximum score error: {report['score_max_absolute_error']:.9g}")
    print("Top-k fraction | mean overlap | minimum overlap | boundary-tie rows")
    for row in summary:
        print(f"{row['percent']:>12}% | {row['mean_overlap']:.6f} | {row['min_overlap']:.6f} | {row['boundary_tie_rows']}")
    print(f"Evidence saved to: {run_dir.resolve()}")
    print("DEBUG BASELINE ONLY: no claim of representative attention accuracy.")


if __name__ == "__main__":
    main()
