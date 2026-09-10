`default_nettype none
module dlzs_snap_exp(
    input logic [15:0] m,
    output logic [3:0] e
);
logic [15:0] v;
logic all_zero;
assign v = m | ((m & (m >> 1)) << 2);
lzc_16 lead1(
    .input_operand(v),
    .output_power(e),
    .all_zero(all_zero)
);


endmodule
`default_nettype wire
