// drum_wrapper_test.sv -- OOC synthesis harness for the DRUM baselines.
//
// Structurally identical to rtl/dlzc_wrapper_test.sv: same two 16-bit input
// registers, same 32-bit output register, same clock. The register count is
// therefore the same 64 FFs on both designs and drops out of the LUT
// comparison, which is the point -- a harness that differs between designs
// contaminates the number it exists to produce.
//
// NOTE the difference from dlzc_wrapper_test: that harness instantiates the
// UNSIGNED core dlzc_mult, so the DLZS row currently in synth_result/ is for
// the unsigned datapath with no sign-magnitude shell. Synthesize like against
// like -- either add a signed DLZS harness, or report the unsigned DRUM core
// here. Do not compare signed DRUM against unsigned DLZS.

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
