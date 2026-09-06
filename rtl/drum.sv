module drum(
    input wire logic [15:0] operand1,
    input wire logic [15:0] operand2,
    output logic [31:0] output_mul
);
logic all_zero;
logic [15:0] input_operand1;
logic [3:0] power1;
assign input_operand1 = operand1;
lzc_16 op1(
    .input_operand(input_operand1),
    .output_power(power1),
    .all_zero(all_zero)
);
logic [15:0] input_operand2;
logic [3:0] power2;
assign input_operand2 = operand2;
lzc_16 op2(
    .input_operand(input_operand2),
    .output_power(power2),
    .all_zero(all_zero)
);
assign output_mul = all_zero ? 32'b0 : (1 << power1) * (1 << power2) ;
endmodule
