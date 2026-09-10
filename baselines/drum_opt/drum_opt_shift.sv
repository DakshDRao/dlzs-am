// drum_opt_shift.sv -- final left shift of the FPGA-optimised DRUM(K).
//
// Places the signed (2K+2)-bit product at 2^sh. The product is sign-extended
// to 32 bits first, so the shift works unchanged for negative values.
//
// The shift amount (pa + pb) is ready long before the product -- it comes off
// the two LZCs, the product comes out of the multiplier -- so only the data
// side of this shifter is on the critical path. It is written as one `<<`
// and left for Vivado to map; the controls arriving early is what matters.
//
// RANGE: sh <= 2*(16-K) <= 26. The true DRUM result for any signed 16-bit
// inputs fits in 32-bit signed for every K in 3..8 (worst case ~1.68e9 at
// K=3), so bits shifted off the top are always copies of the sign.

`default_nettype none

module drum_opt_shift #(
    parameter int K = 6
) (
    input  wire logic signed [2*K+1:0] prod,
    input  wire logic        [4:0]     sh,
    output logic             [31:0]    p
);

    logic [31:0] prod_ext;

    assign prod_ext = {{(32-(2*K+2)){prod[2*K+1]}}, prod};
    assign p        = prod_ext << sh;

endmodule

`default_nettype wire
