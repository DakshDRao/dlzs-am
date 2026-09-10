// exact_tb_top.sv -- verification wrapper only, not part of any synthesized
// design.
//
// Same pattern as drum_tb_top and mult_tb_top: cocotb drives one toplevel per
// simulation, so both DUTs are instantiated here with independent stimulus
// ports and one elaboration covers them. The wrapper adds no logic -- every
// port is a direct pass-through, so a failure seen here is a failure in the
// DUT.
//
// WHY THE PIPELINED WRAPPER IS SIMULATED AT ALL
// ---------------------------------------------
// dlzc_wrapper_test and drum_wrapper_test are not simulated, because they are
// pure harness: they exist to give every design the same 64 flip-flops so the
// registers drop out of the LUT delta, and their combinational content is the
// DUT that tb/mult and tb/drum already cover.
//
// exact_wrapper is different in one respect that makes it worth a bench: it is
// the ONLY place in the comparison where the exact product is produced, so
// there is no other testbench in which a fault in it would show up. The exact
// row is the reference every approximate design is scored against; if it is
// wrong, every error metric in the comparison table is wrong and nothing else
// contradicts it. That asymmetry is the whole justification.
//
// Core and wrapper get SEPARATE stimulus ports rather than sharing them, for
// the reason drum_tb_top gives: if they shared, a core fault and a wrapper
// fault would produce the same symptom. Here that is not hypothetical -- the
// wrapper's register/instance connection is exactly the kind of thing that
// breaks while the combinational core underneath stays perfect.
//
// Ports are declared `signed` even though the DUTs' own ports are not, so the
// cocotb side can read them with .to_signed(). The bit patterns crossing the
// boundary are identical either way.

`default_nettype none

module exact_tb_top (
    // Combinational core, exercised with no clock in the path
    input  wire signed [15:0] c_a,
    input  wire signed [15:0] c_b,
    output wire signed [31:0] c_p,

    // Pipelined synthesis wrapper -- two input regs, one output reg
    input  wire               clk,
    input  wire signed [15:0] w_a,
    input  wire signed [15:0] w_b,
    output wire signed [31:0] w_p
);

    exact dut_core (
        .operand1 (c_a),
        .operand2 (c_b),
        .mul_out  (c_p)
    );

    exact_wrapper dut_wrap (
        .clk      (clk),
        .operand1 (w_a),
        .operand2 (w_b),
        .mul_out  (w_p)
    );

endmodule

`default_nettype wire
