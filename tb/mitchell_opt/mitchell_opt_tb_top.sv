// Verification wrapper for the optimized Mitchell multiplier.
`default_nettype none

module mitchell_opt_tb_top (
    input  wire        [15:0] u_a,
    input  wire        [15:0] u_b,
    output wire        [31:0] u_mul,
    input  wire signed [15:0] s_a,
    input  wire signed [15:0] s_b,
    output wire signed [31:0] s_mul
);
    mitchell_mult_opt dut_unsigned (
        .a       (u_a),
        .b       (u_b),
        .mul_out (u_mul)
    );

    mitchell_mult_opt_top dut_signed (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_mul)
    );
endmodule

`default_nettype wire
