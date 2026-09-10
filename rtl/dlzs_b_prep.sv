`default_nettype none
module dlzs_b_prep(
    input logic [15:0] b,
    input logic a_neg, a_zero,
    output logic [16:0] bp
);
assign bp = a_zero ? 17'b0 : a_neg ? ~{b[15], b} + 1'b1 : {b[15], b};
endmodule
