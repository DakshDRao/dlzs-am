`default_nettype none
(* use_dsp = "no" *)
module dlzc_opt_top(
    input wire logic [15:0] operand1,
    input wire logic [15:0] operand2,
    output logic [31:0] output_mul
);
logic a_zero;
logic [3:0] e;
logic [16:0] bp;
logic [15 : 0] operandA;
assign operandA = operand1[15] ? ~operand1 + 1'b1 : operand1;
assign a_zero = !(operand1 || 1'b0);
dlzs_snap_exp snap(
    .m(operandA),
    .e(e)
);
dlzs_b_prep b_p(
    .b(operand2),
    .a_neg(operand1[15]),
    .a_zero(a_zero),
    .bp(bp)
);
dlzc_shift shft(
    .bp(bp),
    .e(e),
    .p(output_mul)
);
endmodule
`default_nettype wire
