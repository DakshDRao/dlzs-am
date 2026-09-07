module exact(
    input wire logic [15:0] operand1,
    input wire logic [15:0] operand2,
    output wire logic [31:0] mul_out
);
assign mul_out = $signed(operand1) * $signed(operand2);
endmodule
