// drum_tb_top.sv -- verification wrapper only, not part of any synthesized
// design.
//
// Same pattern as mult_tb_top: cocotb drives one toplevel per simulation, so
// all four DUTs are instantiated here with independent stimulus ports and one
// elaboration covers them. The wrapper adds no logic -- every port is a direct
// pass-through, so a failure seen here is a failure in the DUT.
//
// The bare unsigned cores and the signed wrappers get SEPARATE stimulus ports
// rather than sharing them. If they shared, a core fault and a wrapper fault
// would produce the same symptom -- and that is exactly the confusion that
// made upstream's DRUM6_16_s look plausible: correct core, wrong sign logic.
//
// The signed ports are declared `signed` even though drum_signed_top's own
// ports are not, so the cocotb side can read them with .to_signed(). The bit
// patterns crossing the boundary are identical either way.

`default_nettype none

module drum_tb_top (
    // Vendored unsigned cores, driven with raw 16-bit patterns
    input  wire  [15:0] u_a,
    input  wire  [15:0] u_b,
    output wire  [31:0] u_r6,
    output wire  [31:0] u_r4,

    // Our sign-magnitude wrappers
    input  wire signed [15:0] s_a,
    input  wire signed [15:0] s_b,
    output wire signed [31:0] s_r6,
    output wire signed [31:0] s_r4
);

    DRUM6_16_u dut_core6 (.a(u_a), .b(u_b), .r(u_r6));
    DRUM4_16_u dut_core4 (.a(u_a), .b(u_b), .r(u_r4));

    drum_signed_top #(.K(6)) dut_s6 (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_r6)
    );

    drum_signed_top #(.K(4)) dut_s4 (
        .operand1   (s_a),
        .operand2   (s_b),
        .output_mul (s_r4)
    );

endmodule

`default_nettype wire
