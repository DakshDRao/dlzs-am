module exact_wrapper(
    input wire clk,
    input wire logic [15:0] operand1,
    input wire logic [15:0] operand2,
    output logic [31:0] mul_out
);
logic [15:0] a_reg, b_reg;
logic [31:0] p_comb;
exact ex1(
    .operand1(a_reg),
    .operand2(b_reg),
    .mul_out(p_comb)
);
always_ff@(posedge clk) begin
    a_reg <= operand1;
    b_reg <= operand2;
    p_comb <= mul_out;
end
endmodule
