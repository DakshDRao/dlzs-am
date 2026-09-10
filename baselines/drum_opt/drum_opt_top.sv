// drum_opt_top.sv -- FPGA-optimised signed DRUM(K), 16x16 -> 32.
//
// Bit-exact drop-in for drum_signed_top (the published DRUM cores inside a
// sign-magnitude shell) and for golden_model.signed_wrap(drum(.., K), a, b, 16),
// with the same ports as every other top in the comparison.
//
// What changed versus the published design, all without changing a result:
//   * No 32-bit output negate. Each operand carries its own sign into a
//     signed (K+1)x(K+1) multiply (see drum_opt_operand), and the multiplier
//     folds the sign into its partial products.
//   * Structured lzc_16 instead of the ripple LOD + one-hot case encoder.
//   * The exact-case flag comes straight off |X|, in parallel with the LZC.
//   * pa + pb is computed off the LZCs while the multiply is in flight, so
//     the adder is off the critical path.
//
// What did NOT change: both operands still need |X| -- DRUM truncates both, so
// neither can stay in two's complement the way DLZS's B does. Two 16-bit
// negates in parallel; that is the algorithm's cost, not an effort gap.
//
// The multiply is the one `*` in the design; synth runs with -max_dsp 0.

`default_nettype none

(* use_dsp = "no" *)
module drum_opt_top #(
    parameter int K = 6
) (
    input  wire logic [15:0] operand1,
    input  wire logic [15:0] operand2,
    output logic      [31:0] output_mul
);

    logic signed [K:0]     mm_a, mm_b;
    logic        [3:0]     pa, pb;
    logic signed [2*K+1:0] prod;
    logic        [4:0]     sh;

    drum_opt_operand #(.K(K)) u_op_a (.x(operand1), .mm_s(mm_a), .p(pa));
    drum_opt_operand #(.K(K)) u_op_b (.x(operand2), .mm_s(mm_b), .p(pb));

    // Both operands signed and the target 2K+2 bits wide, so both are
    // sign-extended before the multiply and the product is exact.
    assign prod = mm_a * mm_b;
    assign sh   = {1'b0, pa} + {1'b0, pb};

    drum_opt_shift #(.K(K)) u_shift (.prod(prod), .sh(sh), .p(output_mul));

endmodule

`default_nettype wire
