module lzc_16(
    input logic [15:0] input_operand,
    output logic [3:0] output_power,
    output logic all_zero
);
logic [7:0] first_half;
logic [7:0] second_half;
logic [2:0] output_power1;
logic [2:0] output_power2;
logic all_zero1;
logic all_zero2;
lzc_8 lzc_8_1(
    .all_zero(all_zero1),
    .input_operand(first_half),
    .output_power(output_power1)
);
lzc_8 lzc_8_2(
    .all_zero(all_zero2),
    .input_operand(second_half),
    .output_power(output_power2)
);
always_comb begin
    first_half = input_operand[15:8];
    second_half = input_operand[7:0];
    output_power = 4'b0;
    all_zero = 1'b0;
    all_zero = all_zero1 & all_zero2;
    output_power = all_zero1 ? {1'b0, output_power2} : {1'b1, output_power1};
end
endmodule
