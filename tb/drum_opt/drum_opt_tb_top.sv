// drum_opt_tb_top.sv -- verification wrapper only, not part of the synthesized design.
//
// Every K in 3..8 is elaborated side by side and driven from ONE set of
// stimulus ports, so a single time step checks all six parameterisations:
//
//   dut_op<K>   drum_opt_operand #(K)  -- the carry-free signed operand
//   dut_top<K>  drum_opt_top #(K)      -- the assembled multiplier
//   ref_pub4/6  drum_signed_top        -- the PUBLISHED DRUM4/DRUM6 cores in
//                                         the sign-magnitude shell, as an
//                                         independent second reference
//
// The wrapper adds no logic -- every port is a direct pass-through, so a
// failure seen here is a failure in the DUT.

`default_nettype none

module drum_opt_tb_top (
    // drum_opt_operand, every K, one shared operand
    input  wire        [15:0] op_x,
    output wire signed [3:0]  op_mm3,
    output wire        [3:0]  op_p3,
    output wire signed [4:0]  op_mm4,
    output wire        [3:0]  op_p4,
    output wire signed [5:0]  op_mm5,
    output wire        [3:0]  op_p5,
    output wire signed [6:0]  op_mm6,
    output wire        [3:0]  op_p6,
    output wire signed [7:0]  op_mm7,
    output wire        [3:0]  op_p7,
    output wire signed [8:0]  op_mm8,
    output wire        [3:0]  op_p8,

    // drum_opt_top, every K, plus the published cores (K=4,6), same operands
    input  wire signed [15:0] s_a,
    input  wire signed [15:0] s_b,
    output wire signed [31:0] mul3,
    output wire signed [31:0] mul4,
    output wire signed [31:0] mul5,
    output wire signed [31:0] mul6,
    output wire signed [31:0] mul7,
    output wire signed [31:0] mul8,
    output wire signed [31:0] pub4,
    output wire signed [31:0] pub6
);

    drum_opt_operand #(.K(3)) dut_op3 (.x(op_x), .mm_s(op_mm3), .p(op_p3));
    drum_opt_operand #(.K(4)) dut_op4 (.x(op_x), .mm_s(op_mm4), .p(op_p4));
    drum_opt_operand #(.K(5)) dut_op5 (.x(op_x), .mm_s(op_mm5), .p(op_p5));
    drum_opt_operand #(.K(6)) dut_op6 (.x(op_x), .mm_s(op_mm6), .p(op_p6));
    drum_opt_operand #(.K(7)) dut_op7 (.x(op_x), .mm_s(op_mm7), .p(op_p7));
    drum_opt_operand #(.K(8)) dut_op8 (.x(op_x), .mm_s(op_mm8), .p(op_p8));
    drum_opt_top #(.K(3)) dut_top3 (.operand1(s_a), .operand2(s_b), .output_mul(mul3));
    drum_opt_top #(.K(4)) dut_top4 (.operand1(s_a), .operand2(s_b), .output_mul(mul4));
    drum_opt_top #(.K(5)) dut_top5 (.operand1(s_a), .operand2(s_b), .output_mul(mul5));
    drum_opt_top #(.K(6)) dut_top6 (.operand1(s_a), .operand2(s_b), .output_mul(mul6));
    drum_opt_top #(.K(7)) dut_top7 (.operand1(s_a), .operand2(s_b), .output_mul(mul7));
    drum_opt_top #(.K(8)) dut_top8 (.operand1(s_a), .operand2(s_b), .output_mul(mul8));
    drum_signed_top #(.K(4)) ref_pub4 (.operand1(s_a), .operand2(s_b), .output_mul(pub4));
    drum_signed_top #(.K(6)) ref_pub6 (.operand1(s_a), .operand2(s_b), .output_mul(pub6));

endmodule

`default_nettype wire
