module dlzc_wrapper_test (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    output logic [31:0] p
);
    // Pipeline registers
    logic [15:0] a_reg, b_reg;
    logic [31:0] p_comb;
    dlzc_mult_top u_dlzc (
        .operand1(a_reg),
        .operand2(b_reg),
        .output_mul(p_comb)
    );
    always_ff @(posedge clk) begin
        a_reg <= a;
        b_reg <= b;
        p     <= p_comb;
    end
endmodule
