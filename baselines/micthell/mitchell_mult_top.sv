`default_nettype none

// Signed 16x16 -> 32 Mitchell multiplier.
//
// The original Mitchell algorithm is an unsigned magnitude algorithm.
// This wrapper follows the project's established sign-magnitude convention:
// take two's-complement magnitudes, run the unsigned approximate core, and
// restore the product sign. The wrapper itself introduces no approximation.
//
// IMPORTANT: magnitude nets remain UNSIGNED. In particular, -32768 has the
// 16-bit pattern 16'h8000, which is 32768 when interpreted as unsigned.
(* use_dsp = "no" *)
module mitchell_mult_top (
    input  wire logic signed [15:0] operand1,
    input  wire logic signed [15:0] operand2,
    output logic      signed [31:0] output_mul
);

    logic [15:0] abs_value1;
    logic [15:0] abs_value2;
    logic [31:0] mul_out;
    logic        sign_bit;

    assign sign_bit = operand1[15] ^ operand2[15];

    assign abs_value1 = operand1[15] ? (~operand1 + 16'd1) : operand1;
    assign abs_value2 = operand2[15] ? (~operand2 + 16'd1) : operand2;

    mitchell_mult u_core (
        .a       (abs_value1),
        .b       (abs_value2),
        .mul_out (mul_out)
    );

    always_comb begin
        if (sign_bit)
            output_mul = ~mul_out + 32'd1;
        else
            output_mul = mul_out;
    end

endmodule

`default_nettype wire
