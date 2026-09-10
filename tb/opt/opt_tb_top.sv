// opt_tb_top.sv -- verification wrapper only, not part of the synthesized design.
//
// cocotb drives one toplevel per simulation, so every block of the optimised
// datapath is instantiated here with its OWN stimulus ports, and one
// elaboration covers all of them:
//
//   dlzs_snap_exp   A branch:  |A| -> snapped exponent e
//   dlzs_b_prep     B branch:  B, a_neg, a_zero -> prepared B (17-bit)
//   dlzc_shift      two-level shifter: bp << e
//   dlzc_opt_top    the assembled multiplier
//   dlzc_mult_top   the OLD verified multiplier, driven by the SAME operands
//                   as dlzc_opt_top, as an independent second reference
//
// Driving the blocks independently means a failure is localised to one
// module instead of surfacing only at the top. The wrapper adds no logic --
// every port is a direct pass-through, so a failure seen here is a failure
// in the DUT.
//
// Signed ports are declared `signed` so the cocotb side can read them as two's
// complement; the bit patterns crossing the boundary are identical either way.

`default_nettype none

module opt_tb_top (
    // dlzs_snap_exp
    input  wire        [15:0] sn_m,
    output wire        [3:0]  sn_e,

    // dlzs_b_prep
    input  wire        [15:0] bpr_b,
    input  wire               bpr_a_neg,
    input  wire               bpr_a_zero,
    output wire signed [16:0] bpr_bp,

    // dlzc_shift
    input  wire signed [16:0] sh_bp,
    input  wire        [3:0]  sh_e,
    output wire signed [31:0] sh_p,

    // dlzc_opt_top (new) and dlzc_mult_top (old), same operands
    input  wire signed [15:0] s_a,
    input  wire signed [15:0] s_b,
    output wire signed [31:0] s_mul,
    output wire signed [31:0] s_mul_ref
);

    dlzs_snap_exp dut_snap (
        .m (sn_m),
        .e (sn_e)
    );

    dlzs_b_prep dut_bprep (
        .b      (bpr_b),
        .a_neg  (bpr_a_neg),
        .a_zero (bpr_a_zero),
        .bp     (bpr_bp)
    );

    dlzc_shift dut_shift (
        .bp (sh_bp),
        .e  (sh_e),
        .p  (sh_p)
    );

    dlzc_opt_top dut_opt (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_mul)
    );

    dlzc_mult_top ref_old (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_mul_ref)
    );

endmodule

`default_nettype wire
