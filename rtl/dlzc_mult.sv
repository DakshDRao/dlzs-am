`default_nettype none

// DLZS nearest-linear, unsigned 16x16 -> 32.
// Operand A is snapped to the nearer power of two (ties round UP, matching
// golden_model.dlzs_nearest_linear); operand B is shifted. Snap direction and
// tie-break must match the model bit-for-bit.
module dlzc_mult(
    input  logic [15:0] a,
    input  logic [15:0] b,
    output logic [31:0] mul_out
);

    logic [3:0] lead_a;
    logic       a_is_zero;

    lzc_16 u_lzc (
        .input_operand (a),
        .output_power  (lead_a),
        .all_zero      (a_is_zero)
    );

    // Round up when the mantissa MSB (bit lead_a-1) is set. lead_a == 0 means
    // A == 1, which has no mantissa bits, so the test is suppressed rather
    // than allowed to index bit -1.
    logic round_up;
    assign round_up = (lead_a != 4'd0) && a[lead_a - 4'd1];

    // 5 bits: the shift reaches 16 when lead_a == 15 and round_up is set.
    // A 4-bit sum wraps to 0 there and silently drops the shift entirely.
    logic [4:0] shamt;
    assign shamt = {1'b0, lead_a} + {4'b0, round_up};

    // Zero guard mirrors the model's `if a == 0 or b == 0: return 0`.
    // b == 0 falls out of the shift naturally; a == 0 does not, because
    // lead_a is meaningless there.
    always_comb begin
        if (a_is_zero)
            mul_out = 32'd0;
        else
            mul_out = {16'd0, b} << shamt;
    end

endmodule
