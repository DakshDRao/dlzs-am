"""Evaluate attention top-k preservation on a fixed corpus.

This is the larger-corpus replacement for the small diagnostic runner.  It
uses a pinned DistilBERT checkpoint, captures Q/K for all six layers, checks
the floating-point attention reconstruction, then compares exact int16 and
the approximate multiplier models.  The model forward pass and the
vectorized multiplier score calculation use CUDA when available; CPU remains
the automatic fallback.

The comparison is still a *local score replacement* experiment.  Q/K in every
layer come from the unmodified floating-point model, so approximate errors are
not propagated into later layers and no task-accuracy claim is made.

Required beside this file:
  attention_quantize.py  (the shared int16 quantizer)
  golden_model.py        (the scalar bit-exact authority used by self-checks)

Typical run:
  python src/make_attention_corpus.py --output src/attention_corpus_100.json
  python src/attention_corpus_eval.py \
      --texts src/attention_corpus_100.json --device auto
"""

import argparse
from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
from pathlib import Path
import sys
import time

import numpy as np
import torch
import transformers
from transformers import AutoModel, AutoTokenizer

from attention_quantize import quantize
import golden_model as gm


PERCENTAGES = tuple(range(5, 51, 5))
APPROXIMATE_DESIGNS = (
    "dlzs_comp_q", "dlzs_comp_k", "dlzs_snap_q", "dlzs_snap_k", "mitchell", "drum3", "drum4", "drum6"
)
ALL_DESIGNS = ("exact_int16",) + APPROXIMATE_DESIGNS


def write_csv(path, rows):
    if not rows:
        raise ValueError(f"Cannot write an empty CSV: {path}")
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def load_corpus(path, limit=None):
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        texts = payload
    elif isinstance(payload, dict) and isinstance(payload.get("texts"), list):
        texts = payload["texts"]
    else:
        raise ValueError("Corpus must be a JSON list or an object containing a 'texts' list.")
    if len(texts) < 100:
        raise ValueError(f"The fixed corpus must contain at least 100 passages; found {len(texts)}.")
    if not all(isinstance(text, str) and text.strip() for text in texts):
        raise ValueError("Every corpus entry must be a non-empty string.")
    if limit is not None:
        if not 2 <= limit <= len(texts):
            raise ValueError(f"--limit must be between 2 and {len(texts)}.")
        texts = texts[:limit]
    return texts


def choose_device(requested):
    if requested == "cpu":
        return torch.device("cpu")
    if requested == "cuda":
        if not torch.cuda.is_available():
            raise RuntimeError(
                "--device cuda was requested, but torch.cuda.is_available() is false. "
                "Install a CUDA-enabled PyTorch wheel and verify the NVIDIA driver."
            )
        return torch.device("cuda")
    if torch.cuda.is_available():
        return torch.device("cuda")
    return torch.device("cpu")


def make_lead_table(device):
    """Exact leading-one values for every possible signed-int16 magnitude."""
    table = np.zeros(32769, dtype=np.int64)
    for value in range(1, len(table)):
        table[value] = value.bit_length() - 1
    return torch.from_numpy(table).to(device=device)


def lead_one_tensor(magnitude, lead_table):
    indices = torch.clamp(magnitude, min=0, max=32768)
    return lead_table[indices]


def left_shift(value, shift):
    return torch.bitwise_left_shift(value, shift)


def right_shift(value, shift):
    return torch.bitwise_right_shift(value, shift)


def signed_approx_product(a, b, design, lead_table):
    """Vectorized signed wrapper matching golden_model.SIGNED_DESIGNS."""
    magnitude_a = torch.abs(a)
    magnitude_b = torch.abs(b)
    nonzero = (magnitude_a != 0) & (magnitude_b != 0)
    negative = torch.logical_xor(a < 0, b < 0)
    sign = torch.where(negative, -torch.ones_like(a), torch.ones_like(a))

    if design == "dlzs_snap_q" or design == "dlzs_snap_k":
        snapped = magnitude_a if design == "dlzs_snap_q" else magnitude_b
        shifted = magnitude_b if design == "dlzs_snap_q" else magnitude_a
        exponent = lead_one_tensor(snapped, lead_table)
        lower_bit_position = torch.clamp(exponent - 1, min=0)
        lower_bit = torch.bitwise_and(right_shift(snapped, lower_bit_position), 1)
        round_up = (exponent > 0) & (lower_bit != 0)
        exponent = exponent + round_up.to(torch.int64)
        unsigned = left_shift(shifted, exponent)
    elif design in ("dlzs_comp_q", "dlzs_comp_k"):
        snapped = magnitude_a if design == "dlzs_comp_q" else magnitude_b
        shifted = magnitude_b if design == "dlzs_comp_q" else magnitude_a
        exponent = lead_one_tensor(snapped, lead_table)
        step = left_shift(torch.ones_like(exponent), torch.clamp(exponent - 1, min=0))
        rounded = torch.div(snapped + right_shift(step, 1), step,
                            rounding_mode="floor") * step
        unsigned = rounded * shifted
    elif design == "mitchell":
        exponent_a = lead_one_tensor(magnitude_a, lead_table)
        exponent_b = lead_one_tensor(magnitude_b, lead_table)
        base_a = left_shift(torch.ones_like(exponent_a), exponent_a)
        base_b = left_shift(torch.ones_like(exponent_b), exponent_b)
        mantissa_a = magnitude_a - base_a
        mantissa_b = magnitude_b - base_b
        fraction = (left_shift(mantissa_a, exponent_b) +
                    left_shift(mantissa_b, exponent_a))
        base = left_shift(torch.ones_like(exponent_a), exponent_a + exponent_b)
        unsigned = torch.where(fraction < base, base + fraction,
                               left_shift(fraction, 1))
    elif design in ("drum3", "drum4", "drum6"):
        significant_bits = int(design[-1])
        exponent_a = lead_one_tensor(magnitude_a, lead_table)
        exponent_b = lead_one_tensor(magnitude_b, lead_table)
        shift_a = torch.clamp(exponent_a - significant_bits + 1, min=0)
        shift_b = torch.clamp(exponent_b - significant_bits + 1, min=0)
        truncated_a = right_shift(magnitude_a, shift_a)
        truncated_b = right_shift(magnitude_b, shift_b)
        truncated_a = torch.where(shift_a > 0,
                                 torch.bitwise_or(truncated_a, 1), truncated_a)
        truncated_b = torch.where(shift_b > 0,
                                 torch.bitwise_or(truncated_b, 1), truncated_b)
        unsigned = left_shift(truncated_a * truncated_b, shift_a + shift_b)
    else:
        raise ValueError(f"Unknown approximate design: {design}")

    return torch.where(nonzero, unsigned, torch.zeros_like(unsigned)) * sign


def self_check(device, lead_table):
    """Check the vectorized CUDA/CPU kernels against the scalar authority."""
    rng = np.random.default_rng(0)
    a = rng.integers(-32767, 32768, size=4096, dtype=np.int64)
    b = rng.integers(-32767, 32768, size=4096, dtype=np.int64)
    at = torch.from_numpy(a).to(device=device)
    bt = torch.from_numpy(b).to(device=device)
    scalar = {
        "dlzs_comp_q": lambda x, y: gm.SIGNED_DESIGNS["dlzs_three_level"](x, y, 16),
        "dlzs_comp_k": lambda x, y: gm.SIGNED_DESIGNS["dlzs_three_level"](y, x, 16),
        "dlzs_snap_q": lambda x, y: gm.SIGNED_DESIGNS["dlzs_nearest_linear"](x, y, 16),
        "dlzs_snap_k": lambda x, y: gm.SIGNED_DESIGNS["dlzs_nearest_linear"](y, x, 16),
        "mitchell": lambda x, y: gm.SIGNED_DESIGNS["mitchell"](x, y, 16),
        "drum3": lambda x, y: gm.signed_wrap(lambda p, q, w: gm.drum(p, q, 3, w), x, y, 16),
        "drum4": lambda x, y: gm.SIGNED_DESIGNS["drum4"](x, y, 16),
        "drum6": lambda x, y: gm.SIGNED_DESIGNS["drum6"](x, y, 16),
    }
    for design in APPROXIMATE_DESIGNS:
        got = signed_approx_product(at, bt, design, lead_table).cpu().numpy()
        expected = np.asarray([scalar[design](int(x), int(y)) for x, y in zip(a, b)], dtype=np.int64)
        np.testing.assert_array_equal(got, expected, err_msg=f"Vectorized {design} mismatch")
    print("PASS: vectorized multiplier kernels match golden_model.py on 4096 signed pairs.", flush=True)


def score_matrix(q_tensor, k_tensor, design, lead_table, query_block, key_block):
    """Return scores using query/key tiles, never a full Q*K*D allocation."""
    batch, heads, tokens, _ = q_tensor.shape
    scores = np.empty((batch, heads, tokens, tokens), dtype=np.int64)
    for start in range(0, tokens, query_block):
        query_stop = min(tokens, start + query_block)
        q_block = q_tensor[:, :, start:query_stop, :]
        for key_start in range(0, tokens, key_block):
            key_stop = min(tokens, key_start + key_block)
            k_block = k_tensor[:, :, key_start:key_stop, :]
            if design == "exact_int16":
                products = q_block.unsqueeze(-2) * k_block.unsqueeze(-3)
            else:
                products = signed_approx_product(
                    q_block.unsqueeze(-2), k_block.unsqueeze(-3), design, lead_table
                )
            block_scores = products.sum(dim=-1, dtype=torch.int64)
            scores[:, :, start:query_stop, key_start:key_stop] = block_scores.cpu().numpy()
            del k_block, products, block_scores
        del q_block
    return scores


def update_stat(stats, key, value, tie):
    record = stats[key]
    record[0] += value
    record[1] += 1
    record[2] = min(record[2], value)
    record[3] = max(record[3], value)
    record[4] += int(tie)


def evaluate_rankings(layer, scores, exact, float_scores, valid, designs, stats):
    """Accumulate per-layer/head/text/query top-k overlap with stable ties."""
    batch, heads, tokens, _ = exact.shape
    for sample in range(batch):
        ids = np.flatnonzero(valid[sample])
        for head in range(heads):
            for query in ids:
                exact_row = exact[sample, head, query, ids]
                float_row = float_scores[sample, head, query, ids]
                exact_order = np.argsort(-exact_row, kind="stable")
                float_order = np.argsort(-float_row, kind="stable")
                references = {
                    "quantized_exact": exact_order,
                    "float": float_order,
                }
                for design in designs:
                    proposed = scores[design][sample, head, query, ids]
                    proposed_order = np.argsort(-proposed, kind="stable")
                    for baseline, reference_order in references.items():
                        for percent in PERCENTAGES:
                            count = max(1, (percent * len(ids) + 99) // 100)
                            overlap = (len(set(proposed_order[:count]) &
                                            set(reference_order[:count])) / count)
                            tie = (count < len(ids) and
                                   proposed[proposed_order[count - 1]] ==
                                   proposed[proposed_order[count]])
                            key = (layer, sample, head, design, baseline, percent)
                            update_stat(stats, key, overlap, tie)


def rows_from_stats(stats):
    rows = []
    for key, record in sorted(stats.items()):
        layer, sample, head, design, baseline, percent = key
        total, count, minimum, maximum, ties = record
        rows.append({
            "layer": layer, "sample": sample, "head": head,
            "design": design, "baseline": baseline, "percent": percent,
            "mean_overlap": total / count, "min_overlap": minimum,
            "query_rows": count, "boundary_tie_rows": ties,
        })
    return rows


def aggregate_group_rows(group_rows, group_fields):
    grouped = defaultdict(list)
    for row in group_rows:
        grouped[tuple(row[field] for field in group_fields)].append(row)
    output = []
    for key, values in sorted(grouped.items()):
        means = [row["mean_overlap"] for row in values]
        row = dict(zip(group_fields, key))
        row.update(mean_overlap=float(np.mean(means)),
                   min_overlap=float(min(row["min_overlap"] for row in values)),
                   max_overlap=float(max(row["mean_overlap"] for row in values)),
                   groups=len(values),
                   query_rows=int(sum(row["query_rows"] for row in values)),
                   boundary_tie_rows=int(sum(row["boundary_tie_rows"] for row in values)))
        output.append(row)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--texts", required=True, type=Path,
                        help="JSON corpus created by make_attention_corpus.py")
    parser.add_argument("--revision", default="12040accade4e8a0f71eabdb258fecc2e7e948be")
    parser.add_argument("--max-length", type=int, default=128)
    parser.add_argument("--batch-size", type=int, default=8)
    parser.add_argument("--query-block", type=int, default=32,
                        help="Queries processed per GPU score block; lower this if memory is tight.")
    parser.add_argument("--key-block", type=int, default=16,
                        help="Keys processed per GPU score block; lower this if memory is tight.")
    parser.add_argument("--limit", type=int,
                        help="Use only the first N corpus entries for a smoke test (still requires a 100-entry file).")
    parser.add_argument("--device", choices=("auto", "cuda", "cpu"), default="auto")
    parser.add_argument("--output-dir", type=Path,
                        default=Path(__file__).resolve().parents[1] / "results/attention_corpus_eval")
    parser.add_argument("--no-save-tensors", action="store_true",
                        help="Do not save per-layer quantized Q/K and float score tensors.")
    args = parser.parse_args()
    if not 8 <= args.max_length <= 512:
        parser.error("--max-length must be between 8 and 512")
    if args.batch_size < 1 or args.query_block < 1 or args.key_block < 1:
        parser.error("--batch-size, --query-block, and --key-block must be positive")

    script_dir = Path(__file__).resolve().parent
    for filename in ("attention_quantize.py", "golden_model.py"):
        if not (script_dir / filename).is_file():
            raise FileNotFoundError(f"Place {filename} beside this script.")
    corpus_path = args.texts.resolve()
    texts = load_corpus(corpus_path, args.limit)
    device = choose_device(args.device)
    device_name = torch.cuda.get_device_name(device) if device.type == "cuda" else "CPU"
    if args.device == "auto" and device.type == "cpu":
        print("WARNING: CUDA is unavailable in this Python environment; falling back to CPU.", flush=True)
    print(f"Device: {device} ({device_name})", flush=True)
    print(f"PyTorch: {torch.__version__}; CUDA runtime: {torch.version.cuda}", flush=True)
    if device.type == "cuda":
        torch.cuda.reset_peak_memory_stats(device)

    out = args.output_dir / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S_%fZ")
    out.mkdir(parents=True, exist_ok=False)
    torch.manual_seed(0)
    model_id = "distilbert/distilbert-base-uncased"
    print("Loading pinned DistilBERT checkpoint...", flush=True)
    model = AutoModel.from_pretrained(model_id, revision=args.revision,
                                      attn_implementation="eager", use_safetensors=True)
    model.to(device=device, dtype=torch.float32).eval()
    tokenizer = AutoTokenizer.from_pretrained(model_id, revision=args.revision)
    inputs = tokenizer(texts, padding="max_length", truncation=True,
                       max_length=args.max_length, return_tensors="pt")
    valid_all = inputs["attention_mask"].bool().numpy()
    lengths = inputs["attention_mask"].sum(dim=1).tolist()
    truncated = [len(tokenizer.encode(text, add_special_tokens=True)) > args.max_length for text in texts]

    manifest = {
        "format": "dlzs_attention_corpus_eval_v1",
        "model_id": model_id,
        "model_revision": getattr(model.config, "_commit_hash", None) or args.revision,
        "texts": texts,
        "corpus_file": str(corpus_path),
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "text_count": len(texts),
        "original_token_lengths": [len(tokenizer.encode(text, add_special_tokens=True)) for text in texts],
        "valid_token_lengths": lengths,
        "max_length": args.max_length,
        "truncated": truncated,
        "batch_size": args.batch_size,
        "query_block": args.query_block,
        "key_block": args.key_block,
        "device": str(device),
        "device_name": device_name,
        "cuda_runtime": torch.version.cuda,
        "versions": {"torch": torch.__version__, "transformers": transformers.__version__, "numpy": np.__version__},
        "method": "independent local score replacement on Q/K from the unmodified floating-point model",
        "scope": "fixed 100-passage corpus; all six layers; no propagated approximation and no task-accuracy claim",
        "source_hashes": {name: hashlib.sha256((script_dir / name).read_bytes()).hexdigest()
                          for name in ("attention_corpus_eval.py", "attention_quantize.py", "golden_model.py")},
    }
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    captured = {}
    q_parts = [[] for _ in range(model.config.n_layers)]
    k_parts = [[] for _ in range(model.config.n_layers)]
    reconstruction_by_layer = {
        layer: {"layer": layer, "max_abs_difference": 0.0, "max_row_error": 0.0,
                "max_padding_error": 0.0, "batches": 0}
        for layer in range(model.config.n_layers)
    }

    def hook_for(layer, name):
        def hook(module, arguments, value):
            captured[(layer, name)] = value.detach()
        return hook

    handles = []
    for layer, block in enumerate(model.transformer.layer):
        handles += [block.attention.q_lin.register_forward_hook(hook_for(layer, "q")),
                    block.attention.k_lin.register_forward_hook(hook_for(layer, "k"))]

    print(f"Capturing all layers for {len(texts)} passages in batches of {args.batch_size}...", flush=True)
    try:
        with torch.no_grad():
            for start in range(0, len(texts), args.batch_size):
                stop = min(len(texts), start + args.batch_size)
                batch_inputs = {name: tensor[start:stop].to(device) for name, tensor in inputs.items()}
                outputs = model(**batch_inputs, output_attentions=True, return_dict=True)
                batch_valid = batch_inputs["attention_mask"].bool()
                batch_size = stop - start
                for layer in range(model.config.n_layers):
                    q_raw = captured.pop((layer, "q"))
                    k_raw = captured.pop((layer, "k"))
                    q_heads = q_raw.reshape(batch_size, q_raw.shape[1], model.config.n_heads,
                                            q_raw.shape[2] // model.config.n_heads).transpose(1, 2)
                    k_heads = k_raw.reshape(batch_size, k_raw.shape[1], model.config.n_heads,
                                            k_raw.shape[2] // model.config.n_heads).transpose(1, 2)
                    dimension = q_heads.shape[-1]
                    score = torch.matmul(q_heads, k_heads.transpose(-2, -1)) * (dimension ** -0.5)
                    rebuilt = torch.softmax(score.masked_fill(~batch_valid[:, None, None, :], float("-inf")), dim=-1)
                    reference = outputs.attentions[layer]
                    row_mask = batch_valid[:, None, :].expand(batch_size, model.config.n_heads, q_heads.shape[2])
                    pad_mask = (~batch_valid[:, None, None, :]).expand_as(reference)
                    check = reconstruction_by_layer[layer]
                    check["max_abs_difference"] = max(check["max_abs_difference"],
                                                       float((reference - rebuilt).abs().max()))
                    check["max_row_error"] = max(check["max_row_error"],
                                                  float((rebuilt.sum(-1)[row_mask] - 1).abs().max()))
                    if pad_mask.any():
                        check["max_padding_error"] = max(check["max_padding_error"],
                                                         float(rebuilt[pad_mask].abs().max()))
                    check["batches"] += 1
                    q_parts[layer].append(q_heads.detach().cpu().numpy().astype(np.float32, copy=False))
                    k_parts[layer].append(k_heads.detach().cpu().numpy().astype(np.float32, copy=False))
                del outputs
                # Do not retain the final batch's GPU tensors through the
                # subsequent CPU quantization and score phase.
                del batch_inputs, batch_valid, q_raw, k_raw, q_heads, k_heads
                del score, rebuilt, reference, row_mask, pad_mask
                print(f"  captured passages {start + 1}-{stop}", flush=True)
    finally:
        for handle in handles:
            handle.remove()

    for check in reconstruction_by_layer.values():
        if (check["max_abs_difference"] >= 1e-5 or check["max_row_error"] >= 1e-5 or
                check["max_padding_error"] >= 1e-7):
            raise RuntimeError(f"Attention reconstruction failed: {check}")
    reconstruction_rows = list(reconstruction_by_layer.values())
    write_csv(out / "reconstruction_checks.csv", reconstruction_rows)
    print("PASS: reconstructed reference attention for every layer and corpus batch.", flush=True)
    captured.clear()
    if device.type == "cuda":
        torch.cuda.empty_cache()

    lead_table = make_lead_table(device)
    self_check(device, lead_table)
    stats = defaultdict(lambda: [0.0, 0, 1.0, 0.0, 0])
    score_error_rows = []
    layer_rows = []
    start_time = time.monotonic()

    for layer in range(model.config.n_layers):
        print(f"\nScoring layer {layer + 1}/{model.config.n_layers}...", flush=True)
        q_float = np.concatenate(q_parts[layer], axis=0)
        k_float = np.concatenate(k_parts[layer], axis=0)
        q_int, q_scale, q_clipped = quantize(q_float, valid_all)
        k_int, k_scale, k_clipped = quantize(k_float, valid_all)
        dimension = q_int.shape[-1]
        float_scores = np.matmul(q_float.astype(np.float64), k_float.astype(np.float64).swapaxes(-1, -2))
        float_scores /= np.sqrt(dimension)
        exact_scores = None
        q_tensor = torch.from_numpy(q_int).to(device=device, dtype=torch.int64)
        k_tensor = torch.from_numpy(k_int).to(device=device, dtype=torch.int64)
        layer_scores = {}
        for design in ALL_DESIGNS:
            print(f"  Computing {design}...", flush=True)
            layer_scores[design] = score_matrix(q_tensor, k_tensor, design, lead_table,
                                                args.query_block, args.key_block)
            if device.type == "cuda":
                torch.cuda.synchronize(device)
            if design == "exact_int16":
                exact_scores = layer_scores[design]
        if exact_scores is None:
            raise RuntimeError("Exact score matrix was not produced.")
        np.testing.assert_array_equal(exact_scores, q_int.astype(np.int64) @ k_int.astype(np.int64).swapaxes(-1, -2))

        for design in ALL_DESIGNS:
            pairs = np.broadcast_to(valid_all[:, None, :, None] & valid_all[:, None, None, :], exact_scores.shape)
            delta = ((layer_scores[design].astype(np.float64) - exact_scores.astype(np.float64)) *
                     q_scale * k_scale / np.sqrt(dimension))
            score_error_rows.append({
                "layer": layer, "design": design,
                "score_mae_vs_quantized_exact": float(np.abs(delta[pairs]).mean()),
                "score_max_error_vs_quantized_exact": float(np.abs(delta[pairs]).max()),
                "clipped_values": int(q_clipped + k_clipped),
            })
        evaluate_rankings(layer, layer_scores, exact_scores, float_scores, valid_all,
                          ALL_DESIGNS, stats)
        layer_groups = rows_from_stats({key: value for key, value in stats.items()
                                        if key[0] == layer})
        layer_rows.extend(aggregate_group_rows(layer_groups,
                                               ("layer", "design", "baseline", "percent")))

        if not args.no_save_tensors:
            layer_dir = out / f"layer_{layer:02d}"
            layer_dir.mkdir()
            np.savez_compressed(layer_dir / "quantized_tensors.npz",
                                q_int=q_int, k_int=k_int, q_scale=q_scale, k_scale=k_scale,
                                float_scores=float_scores, attention_mask=valid_all,
                                input_ids=inputs["input_ids"].numpy())
            (layer_dir / "report.json").write_text(json.dumps({
                "passed": True, "layer_index": layer, "shape": list(q_int.shape),
                "quantization": {"storage": "int16", "range": [-32767, 32767],
                                  "zero_point": 0, "scale": "dynamic per sample/head, separate Q/K",
                                  "rounding": "nearest ties-to-even", "accumulator": "int64",
                                  "clipped_values": int(q_clipped + k_clipped)},
                "float_score_dtype": "float64", "exact_scores_recomputed_from_qk": True,
            }, indent=2), encoding="utf-8")

        del q_tensor, k_tensor, layer_scores, q_float, k_float, float_scores
        q_parts[layer] = None
        k_parts[layer] = None
        print(f"  clipped values: {q_clipped + k_clipped}", flush=True)

    group_rows = rows_from_stats(stats)
    # Per-text means average all layer/head groups, keeping every passage at equal weight.
    text_rows = aggregate_group_rows(group_rows, ("sample", "design", "baseline", "percent"))
    summary = aggregate_group_rows(text_rows, ("design", "baseline", "percent"))
    for row in summary:
        # Keep the same summary column names used by plot_attention_curves.py
        # and by the earlier multilayer runner.
        row["min_text_overlap"] = row["min_overlap"]
        row["max_text_overlap"] = row["max_overlap"]
        row["texts"] = len(texts)
    write_csv(out / "per_text_head.csv", group_rows)
    write_csv(out / "per_text.csv", text_rows)
    write_csv(out / "per_layer.csv", layer_rows)
    write_csv(out / "summary.csv", summary)
    write_csv(out / "score_errors.csv", score_error_rows)

    if not all(row["min_overlap"] == 1.0 for row in summary
               if row["design"] == "exact_int16" and row["baseline"] == "quantized_exact"):
        raise RuntimeError("Exact ranking identity check failed.")
    manifest["elapsed_seconds"] = time.monotonic() - start_time
    manifest["peak_cuda_memory_bytes"] = (torch.cuda.max_memory_allocated(device)
                                          if device.type == "cuda" else None)
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    print("\n10% selection vs quantized exact, equal weight per passage/layer/head:", flush=True)
    for row in summary:
        if row["baseline"] == "quantized_exact" and row["percent"] == 10:
            print(f"{row['design']:19} mean={row['mean_overlap']:.4f}  "
                  f"text range=[{row['min_overlap']:.4f}, {row['max_overlap']:.4f}]", flush=True)
    print(f"\nCOMPLETED: fixed-corpus all-layer study. Results: {out.resolve()}", flush=True)
    print("No plot was generated. This measures local ranking preservation only; it is not end-to-end model accuracy or a hardware result.", flush=True)


if __name__ == "__main__":
    main()
