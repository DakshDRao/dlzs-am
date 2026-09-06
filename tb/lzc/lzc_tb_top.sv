// lzc_tb_top.sv -- verification wrapper only, not part of the synthesized design.
//
// lzc_8 and lzc_16 are separate top-level modules, but cocotb drives a single
// toplevel per simulation. Rather than run two builds, both DUTs are
// instantiated here with independent stimulus ports so one elaboration covers
// both. The wrapper adds no logic: every port is a direct pass-through, so a
// failure seen here is a failure in the DUT.

module lzc_tb_top (
    input  logic [7:0]  operand_8,
    output logic [2:0]  power_8,
    output logic        all_zero_8,

    input  logic [15:0] operand_16,
    output logic [3:0]  power_16,
    output logic        all_zero_16
);

    lzc_8 dut8 (
        .input_operand (operand_8),
        .output_power  (power_8),
        .all_zero      (all_zero_8)
    );

    lzc_16 dut16 (
        .input_operand (operand_16),
        .output_power  (power_16),
        .all_zero      (all_zero_16)
    );

endmodule
