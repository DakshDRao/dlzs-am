`default_nettype none

// Signed wrapper for the optimized Mitchell core.  It follows the same
// sign-magnitude convention as mitchell_mult_top, including -32768.
(* use_dsp = "no" *)
module mitchell_mult_opt_top (
    input  wire logic signed [15:0] operand1,
    input  wire logic signed [15:0] operand2,
    output logic      signed [31:0] output_mul
);
    logic [15:0] abs_value1, abs_value2;
    logic [31:0] mul_out;
    logic        sign_bit;

    assign sign_bit   = operand1[15] ^ operand2[15];
    assign abs_value1 = operand1[15] ? (~operand1 + 16'd1) : operand1;
    assign abs_value2 = operand2[15] ? (~operand2 + 16'd1) : operand2;

    mitchell_mult_opt u_core (
        .a       (abs_value1),
        .b       (abs_value2),
        .mul_out (mul_out)
    );

    always_comb begin
        output_mul = sign_bit ? (~mul_out + 32'd1) : mul_out;
    end
endmodule

`default_nettype wire
