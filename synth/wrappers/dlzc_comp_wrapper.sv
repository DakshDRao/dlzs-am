// Same 16+16 input and 32 output register harness as the baseline study.
module dlzc_comp_wrapper(
    input wire clk,
    input wire [15:0] a, b,
    output logic [31:0] p
);
    logic [15:0] a_reg, b_reg;
    wire [31:0] result;
    always @(posedge clk) begin
        a_reg <= a;
        b_reg <= b;
        p <= result;
    end
    dlzc_comp_top core(.operand1(a_reg), .operand2(b_reg), .output_mul(result));
endmodule
