# Fixed-corpus attention evidence

Source: `results/attention_corpus_eval/20260914T070644_541555Z`.
The files are copied verbatim, including original absolute provenance paths.
Use `summary_corrected.csv` and `design_summary.csv` for passage-level ranges.
`summary.csv` has the original minimum-field reporting bug. Mean overlaps agree.
`attention_cost_table.csv` uses LUT cells, not physical Slice LUT utilization.
The main README joins physical utilization separately from the hardware reports.

`per_text.csv` supports independent passage-mean/range recomputation.
Raw NPZ tensors and the much larger `per_text_head.csv` remain in the local run;
this curated subset is not a replacement for the complete audit input directory.
See `snapshot.json` for SHA-256 checksums.
