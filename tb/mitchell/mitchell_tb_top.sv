// mitchell_tb_top.sv -- verification wrapper only.
// It is not part of any synthesized design.
`default_nettype none

module mitchell_tb_top (
    // Unsigned Mitchell core.
    input  wire        [15:0] u_a,
    input  wire        [15:0] u_b,
    output wire        [31:0] u_mul,

    // Signed sign-magnitude Mitchell wrapper.
    input  wire signed [15:0] s_a,
    input  wire signed [15:0] s_b,
    output wire signed [31:0] s_mul
);

    mitchell_mult dut_unsigned (
        .a       (u_a),
        .b       (u_b),
        .mul_out (u_mul)
    );

    mitchell_mult_top dut_signed (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_mul)
    );

endmodule

`default_nettype wire
