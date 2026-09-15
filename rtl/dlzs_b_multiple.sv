`default_nettype none
module dlzs_b_multiple(
    input wire [16:0] bp,
    input wire use_three,
    output wire [17:0] selected
);
    wire signed [17:0] extended_b = {bp[16], bp};
    wire signed [17:0] triple_b = extended_b + (extended_b <<< 1);
    assign selected = use_three ? triple_b : extended_b;
endmodule
`default_nettype wire

