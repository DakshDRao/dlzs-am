// drum_wrapper_test.sv -- OOC synthesis harness for the DRUM baselines.
//
// Structurally identical to synth/wrappers/dlzc_wrapper_test.sv: same two 16-bit input
// registers, same 32-bit output register, same clock. The register count is
// therefore the same 64 FFs on both designs and drops out of the LUT
// comparison, which is the point -- a harness that differs between designs
// contaminates the number it exists to produce.
//
// CORRECTION to an earlier note here: dlzc_wrapper_test instantiates
// dlzc_mult_top, which is the sign-magnitude shell, NOT the bare unsigned
// dlzc_mult core. Both harnesses are signed-in/signed-out, so the DLZS and
// DRUM rows in synth_result/ are like-for-like and the comparison table is
// not blocked. Re-check this claim against the instantiation, not against
// this comment, if either wrapper is ever edited.

`default_nettype none

module drum_wrapper_test #(
    parameter int K = 6
) (
    input  wire         clk,
    input  wire  [15:0] a,
    input  wire  [15:0] b,
    output logic [31:0] p
);
    logic [15:0] a_reg, b_reg;
    logic [31:0] p_comb;

    drum_signed_top #(.K(K)) u_drum (
        .operand1   (a_reg),
        .operand2   (b_reg),
        .output_mul (p_comb)
    );

    always_ff @(posedge clk) begin
        a_reg <= a;
        b_reg <= b;
        p     <= p_comb;
    end
endmodule

`default_nettype wire
