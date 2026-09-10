// drum_opt_operand.sv -- one operand of the FPGA-optimised DRUM(K).
//
// Turns a 16-bit two's-complement operand X into the pair (mm_s, p) such that
//
//     mm_s * 2^p  ==  sign(X) * drum_extract(|X|, K)
//
// i.e. DRUM's K-bit truncated operand WITH X's sign already applied, plus the
// number of dropped bits. Bit-exact with scale-lab/DRUM @ 2c7ef20 (the vendored
// DRUM4/DRUM6 cores) and with golden_model.drum_extract.
//
// THE CARRY-FREE SIGN
//   Exact case, |X| < 2^K: DRUM uses |X| unchanged. X itself fits in K+1 bits
//   signed there, so X[K:0] IS the signed value. No negation.
//   Truncated case, |X| >= 2^K: DRUM's operand is {1, m, 1} -- the leading
//   one, the K-2 bits below it, and a forced 1. It is odd, and negating an odd
//   number needs no carry: ~v + 1 just sets the LSB back. So -{1,m,1} in K+1
//   bits is {1, 0, ~m, 1}, and the signed operand is
//       {s, ~s, m ^ {s...}, 1}           s = X's sign bit
//   One LUT level, no carry chain. The product sign then falls out of a
//   signed (K+1)x(K+1) multiply in the top, so there is no output negate.
//   A == 0 lands in the exact case and needs no special handling.
//
// SELECTING m
//   m is taken from |X| left-normalised by (15 - lead). For a 4-bit lead,
//   15 - lead is simply ~lead, so the shift amount needs no arithmetic and is
//   valid for every lead; in the exact case the result is garbage but is
//   never selected.
//
// RANGE
//   3 <= K <= 8 (K-2 >= 1 bit of m; the tcl and bench sweep this range).
//   mm_s is in [-(2^K - 1), 2^K - 1]; p = max(0, lead - (K-1)) <= 16 - K.

`default_nettype none

module drum_opt_operand #(
    parameter int K = 6
) (
    input  wire logic        [15:0] x,
    output logic signed      [K:0]  mm_s,
    output logic             [3:0]  p
);

    if (K < 3 || K > 8) begin : g_bad_k
        $error("drum_opt_operand: K must be in 3..8");
    end

    logic        s;
    logic [15:0] x_mag;          // unsigned: 0x8000 reads as 32768
    logic [3:0]  lead;
    logic        exact;
    logic [K-3:0] m;

    /* verilator lint_off UNUSEDSIGNAL */
    logic        lzc_all_zero;   // A == 0 is handled by the exact case
    logic [15:0] x_norm;         // only the K-2 bits below bit 15 are used
    /* verilator lint_on UNUSEDSIGNAL */

    assign s     = x[15];
    assign x_mag = s ? (~x + 16'd1) : x;

    lzc_16 u_lzc (
        .input_operand (x_mag),
        .output_power  (lead),
        .all_zero      (lzc_all_zero)
    );

    // |X| < 2^K straight off the magnitude, in parallel with the LZC.
    assign exact = ~|x_mag[15:K];

    // Leading one moved to bit 15; m is the K-2 bits directly below it.
    assign x_norm = x_mag << ~lead;
    assign m      = x_norm[14 -: K-2];

    assign mm_s = exact ? x[K:0]
                        : {s, ~s, m ^ {(K-2){s}}, 1'b1};

    // Dropped bits. lead >= K whenever !exact, so this never underflows.
    assign p = exact ? 4'd0 : (lead - 4'(K - 1));

endmodule

`default_nettype wire
