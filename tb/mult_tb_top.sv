// mult_tb_top.sv -- verification wrapper only, not part of the synthesized design.
//
// Same pattern as lzc_tb_top: cocotb drives one toplevel per simulation, so
// both the unsigned DLZS core and the signed sign-magnitude wrapper are
// instantiated here with independent stimulus ports and one elaboration covers
// both. The wrapper adds no logic -- every port is a direct pass-through, so a
// failure seen here is a failure in the DUT.
//
// The signed ports are declared `signed` even though dlzc_mult_top's own ports
// are not. That is deliberate: it lets the cocotb side read them with
// .value.signed_integer and makes the sign convention explicit at the seam.
// The bit patterns crossing the boundary are identical either way.

`default_nettype none

module mult_tb_top (
    // Unsigned DLZS core (dlzc_mult)
    input  wire  [15:0] u_a,
    input  wire  [15:0] u_b,
    output wire  [31:0] u_mul,

    // Signed sign-magnitude wrapper (dlzc_mult_top)
    input  wire signed [15:0] s_a,
    input  wire signed [15:0] s_b,
    output wire signed [31:0] s_mul
);

    dlzc_mult dut_unsigned (
        .a       (u_a),
        .b       (u_b),
        .mul_out (u_mul)
    );

    dlzc_mult_top dut_signed (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_mul)
    );

endmodule

`default_nettype wire