`default_nettype none
module dlzc_snap_exp(
    input logic [15:0] m,
    output logic [3:0] e,
    output logic all_zero
);
logic [15:0] v;
assign v = m | ((m & (m >> 1)) << 2);
lzc_16 lead1(
    .input_operand(v),
    .output_power(e),
    .all_zero(all_zero)
);


endmodule
`default_nettype wire ;
