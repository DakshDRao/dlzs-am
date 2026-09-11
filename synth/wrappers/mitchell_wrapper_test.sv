// OOC synthesis harness for the signed Mitchell multiplier.
//
// Same register shell as the other multiplier rows:
//   16-bit input registers -> combinational multiplier -> 32-bit output register.
// Keeping the shell identical makes the LUT/timing comparison meaningful.
`default_nettype none

module mitchell_wrapper_test (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    output logic [31:0] p
);

    logic [15:0] a_reg, b_reg;
    logic [31:0] p_comb;

    mitchell_mult_top u_mitchell (
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
