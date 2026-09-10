// dlzc_opt_wrapper.sv -- OOC synthesis harness for dlzc_opt_top.
//
// Structurally identical to dlzc_wrapper_test (and to the DRUM and exact
// harnesses): two input registers, the combinational multiplier, one output
// register, one clock. That makes the measured path register-to-register
// through the multiplier alone, so every row of the comparison table is
// timed over the same kind of path and differs only in the DUT.
//
// Not a pipelining choice: the multiplier stays single-cycle, like exact.

`default_nettype none

module dlzc_opt_wrapper (
    input  wire        clk,
    input  wire [15:0] a,
    input  wire [15:0] b,
    output logic [31:0] p
);
    logic [15:0] a_reg, b_reg;
    logic [31:0] p_comb;

    dlzc_opt_top u_dlzc_opt (
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
