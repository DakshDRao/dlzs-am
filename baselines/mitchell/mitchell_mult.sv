`default_nettype none

// Mitchell (1962) approximate logarithmic multiplier.
// Unsigned 16x16 -> 32.
//
// Reference:
// J. N. Mitchell, Jr., "Computer Multiplication and Division Using
// Binary Logarithms," IRE Transactions on Electronic Computers, Aug. 1962.
//
// For A = 2^ka(1+ma), B = 2^kb(1+mb), Mitchell approximates
// log2(1+m) ~= m:
//
//   ma + mb < 1:
//       P' = 2^(ka+kb) * (1 + ma + mb)
//   ma + mb >= 1:
//       P' = 2^(ka+kb+1) * (ma + mb)
//
// With Ma = A - 2^ka and Mb = B - 2^kb:
//
//   frac = (Ma << kb) + (Mb << ka)
//         = 2^(ka+kb) * (ma + mb)
//
// so the datapath is only leading-one detection, shifts and additions.
// No multiplier operator is used in the approximate core.
//
// Zero is explicitly guarded because the logarithm/leading-one position is
// undefined for zero.
module mitchell_mult (
    input  wire logic [15:0] a,
    input  wire logic [15:0] b,
    output logic      [31:0] mul_out
);

    logic [3:0] ka;
    logic [3:0] kb;
    logic       a_is_zero;
    logic       b_is_zero;

    logic [15:0] ma;
    logic [15:0] mb;

    logic [4:0]  ksum;
    logic [31:0] frac;
    logic [31:0] base;

    lzc_16 u_lzc_a (
        .input_operand (a),
        .output_power  (ka),
        .all_zero      (a_is_zero)
    );

    lzc_16 u_lzc_b (
        .input_operand (b),
        .output_power  (kb),
        .all_zero      (b_is_zero)
    );

    // Remove the implicit leading one. These are the raw mantissa bits
    // described by Mitchell's paper.
    assign ma = a - (16'd1 << ka);
    assign mb = b - (16'd1 << kb);

    // ka + kb can reach 30, hence the explicit 5-bit operands.
    assign ksum = {1'b0, ka} + {1'b0, kb};

    // Explicit 32-bit extension is required before shifting; otherwise a
    // 16-bit left operand could truncate the shifted mantissa.
    assign frac = ({16'd0, ma} << kb) + ({16'd0, mb} << ka);

    assign base = 32'd1 << ksum;

    always_comb begin
        if (a_is_zero || b_is_zero) begin
            mul_out = 32'd0;
        end
        else if (frac < base) begin
            // ma + mb < 1: P' = base + frac.
            mul_out = base + frac;
        end
        else begin
            // ma + mb >= 1: carry into the characteristic.
            mul_out = frac << 1;
        end
    end

endmodule

`default_nettype wire
