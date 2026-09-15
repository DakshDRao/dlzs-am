`default_nettype none

// Optimized, unsigned 16x16 Mitchell multiplier.
//
// This is bit-exact with baselines/mitchell/mitchell_mult.sv.  The changes
// are implementation-only:
//   * the LZC returns the raw mantissa directly, avoiding two variable
//     one-hot subtractors;
//   * the no-carry branch uses OR (base + frac == base | frac because the
//     carry bit is known to be zero);
//   * the carry decision reads the bit at ksum instead of comparing the full
//     32-bit fraction against a one-hot base.
//
// The variable shifts are intentionally retained in this first optimized
// variant.  That isolates the algebra/metadata savings from any architectural
// change to the aligners, and keeps the result directly comparable with the
// reference Mitchell algorithm.
module mitchell_mult_opt (
    input  wire logic [15:0] a,
    input  wire logic [15:0] b,
    output logic      [31:0] mul_out
);
    logic [3:0]  ka, kb;
    logic        a_is_zero, b_is_zero;
    logic [15:0] ma, mb;
    logic [4:0]  ksum;
    logic [31:0] a_term, b_term, frac;
    logic [31:0] base;
    logic        carry;

    mitchell_lzc_meta u_lzc_a (
        .input_operand (a),
        .output_power  (ka),
        .all_zero      (a_is_zero),
        .mantissa      (ma)
    );

    mitchell_lzc_meta u_lzc_b (
        .input_operand (b),
        .output_power  (kb),
        .all_zero      (b_is_zero),
        .mantissa      (mb)
    );

    assign ksum  = {1'b0, ka} + {1'b0, kb};
    assign a_term = ({16'd0, ma} << kb);
    assign b_term = ({16'd0, mb} << ka);
    assign frac   = a_term + b_term;

    // For non-zero inputs frac is strictly less than 2^(ksum+1), so this
    // bit is exactly the ma+mb >= 1 carry condition.
    assign carry = frac[ksum];
    assign base  = 32'd1 << ksum;

    always_comb begin
        if (a_is_zero || b_is_zero)
            mul_out = 32'd0;
        else if (carry)
            mul_out = frac << 1;
        else
            mul_out = base | frac;
    end
endmodule

`default_nettype wire
