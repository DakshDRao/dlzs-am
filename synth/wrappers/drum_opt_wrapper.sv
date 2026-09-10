// drum_opt_wrapper.sv -- OOC synthesis harness for drum_opt_top #(K).
//
// Structurally identical to every other harness in the comparison: two input
// registers, the combinational multiplier, one output register, one clock.
// K is passed through as a generic by synth_ooc.tcl, so one file serves the
// whole K = 3..8 sweep.

`default_nettype none

module drum_opt_wrapper #(
    parameter int K = 6
) (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    output logic [31:0] p
);
    logic [15:0] a_reg, b_reg;
    logic [31:0] p_comb;

    drum_opt_top #(.K(K)) u_drum_opt (
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
