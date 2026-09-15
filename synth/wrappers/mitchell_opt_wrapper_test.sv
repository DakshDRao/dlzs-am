// OOC synthesis harness for the optimized signed Mitchell multiplier.
`default_nettype none

module mitchell_opt_wrapper_test (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    output logic [31:0] p
);
    logic [15:0] a_reg, b_reg;
    logic [31:0] p_comb;

    mitchell_mult_opt_top u_mitchell_opt (
        .operand1   (a_reg),
        .operand2   (b_reg),
        .output_mul (p_comb)
    );

    always_ff @(posedge clk) begin
        a_reg <= a;
        b_reg <= b;
        p     <= p_comb;
    end
endmodule

`default_nettype wire
