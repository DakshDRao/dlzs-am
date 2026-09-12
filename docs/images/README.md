# Design images

`schematics/` is the canonical Yosys SVG collection (34 diagrams).
`vivado/elaborated/` contains the nine Vivado elaborated-design PNGs.
These describe RTL structure; they are not physical routing screenshots.

## Main designs

| Design | Yosys schematic | Vivado schematic |
|---|---|---|
| Original signed DLZS | [SVG](schematics/dlzc_mult_top.svg) | [PNG](vivado/elaborated/dlzc_mult_top.png) |
| Optimized signed DLZS | [SVG](schematics/dlzs_opt_core.svg) | [PNG](vivado/elaborated/dlzc_opt_top.png) |
| Optimized DLZS register harness | [SVG](schematics/dlzc_opt_wrapper.svg) | [PNG](vivado/elaborated/dlzc_opt_wrapper.png) |
| Exact | [SVG](schematics/exact.svg) | — |
| Mitchell signed | [SVG](schematics/mitchell_mult_top.svg) | — |
| Published DRUM signed K=4 | [SVG](schematics/drum_signed_k4.svg) | — |
| Published DRUM signed K=6 | [SVG](schematics/drum_signed_k6.svg) | — |
| Optimized DRUM K=3 | [SVG](schematics/drum_opt_k3.svg) | — |
| Optimized DRUM K=4 | [SVG](schematics/drum_opt_k4.svg) | — |
| Optimized DRUM K=5 | [SVG](schematics/drum_opt_k5.svg) | — |
| Optimized DRUM K=6 | [SVG](schematics/drum_opt_k6.svg) | — |
| Optimized DRUM K=7 | [SVG](schematics/drum_opt_k7.svg) | — |
| Optimized DRUM K=8 | [SVG](schematics/drum_opt_k8.svg) | — |

The folders also contain individual leading-one, snap, sign-preparation,
operand-extraction and shift block diagrams.

## Regeneration

From the repository root in WSL, with Yosys and Graphviz installed:

```bash
bash scripts/export_yosys.sh
```

The script writes the SVGs here and logs/DOT intermediates to the ignored
`work/yosys-diagrams/logs/` folder. It does not run Vivado implementation.

For Vivado, run `scripts/export_vivado.tcl` in a fresh GUI session with the
repository root as its Tcl argument. It exports PDFs to `vivado/elaborated/`.
The committed PNGs also include the subsequent crop/rotation step; the Tcl
script alone does not regenerate those PNGs. Keep the final images when
removing intermediate PDFs.
