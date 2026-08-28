# DLZS-AM

FPGA-optimized differential log-domain approximate multiplier with error
compensation — design, characterization, and application to attention-sparsity
prediction.

B.Tech ECE major project, NIT Andhra Pradesh.

## Status

- [x] Week 1–2: golden model (exact, Mitchell, DRUM(k), DLZS ×4 snap modes)
- [ ] Week 1–2: metrics + exhaustive sweep + related-work note + spec choice
- [ ] Week 3–5: DLZS RTL + verification
- [ ] Week 6–7: baselines + OOC synthesis
- [ ] Week 8–9: PYNQ integration
- [ ] Week 10–11: attention top-k application study
- [ ] Week 12–13: error compensation
- [ ] Week 14: writeup

## Layout

    src/golden_model.py   bit-exact reference models (no floats in any datapath)
    src/metrics.py        MRED, NMED, max RED, signed bias, error rate
    tests/                regression suite — run before every commit
    results/              generated tables and plots (git-ignored)

## Running

    python3 tests/test_golden_model.py

## Framing

Log-domain multiplication is Mitchell (1962) and is **not** claimed as novel
here. The claimed contribution is the first standalone FPGA implementation and
characterization of the differential/asymmetric log scheme (DLZS, from SOFA,
Wang et al., MICRO 2024), plus error compensation for it.