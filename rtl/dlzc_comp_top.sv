`default_nettype none
(* use_dsp = "no" *)
module dlzc_comp_top #(
    parameter bit COMPENSATE = 1'b1
)(
    input wire [15:0] operand1,
    input wire [15:0] operand2,
    output wire [31:0] output_mul
);
    generate if (!COMPENSATE) begin : original
        dlzc_opt_top baseline(.operand1(operand1), .operand2(operand2),
                              .output_mul(output_mul));
    end else begin : compensated
        wire [15:0] magnitude = operand1[15] ? (~operand1 + 16'd1) : operand1;
        wire [16:0] bp;
        wire [17:0] selected;
        wire [3:0] e;
        wire use_three;
        dlzs_comp_decode decode(.m(magnitude), .e(e), .use_three(use_three));
        dlzs_b_prep prepare(.b(operand2), .a_neg(operand1[15]),
                           .a_zero(~|operand1), .bp(bp));
        dlzs_b_multiple multiples(.bp(bp), .use_three(use_three), .selected(selected));
        dlzc_shift #(.INPUT_WIDTH(18)) shift_product(.bp(selected), .e(e), .p(output_mul));
    end endgenerate
endmodule
`default_nettype wire

