// drum_signed_top.sv -- sign-magnitude wrapper for the vendored DRUM cores.
//
// WHY THIS EXISTS INSTEAD OF UPSTREAM DRUM6_16_s
// ----------------------------------------------
// Two reasons, and the second is the one that matters for the comparison.
//
// 1. Upstream DRUM6_16_s.v is functionally wrong. It computes
//        assign out_sign = a[15] & b[15];
//    The sign of a product is the XOR of the operand signs, not the AND. As
//    written it negates the result only when BOTH operands are negative --
//    precisely the quadrant whose product is positive -- and leaves
//    mixed-sign products positive. Measured against golden_model on 23,744
//    signed vectors: 0% mismatch in (+,+), 99.8% in (+,-) and (-,+), 100% in
//    (-,-). The residual passes in the mixed quadrants are zero-product pairs
//    where the sign is unobservable. Changing & to ^ makes it match the model
//    exactly, 0/23,744.
//
//    The parameterized DRUMk_M_N_s.v has the XOR right but uses ONE's
//    complement (`~a`, `~r_temp`) where two's complement is meant, so it is
//    off by one on every negated path: 99.9% mismatch in the mixed quadrants,
//    2.1% in (-,-) where the two off-by-ones usually vanish under 6-bit
//    truncation. Both wrappers are unusable as published.
//
// 2. Even with the sign bug fixed, borrowing upstream's wrapper would make the
//    AREA comparison unfair. dlzc_mult_top wraps the DLZS core in a specific
//    sign-magnitude shell; if DRUM is wrapped in a structurally different one,
//    the LUT delta between the two designs partly measures the wrappers rather
//    than the cores. This module is a line-for-line structural match to
//    rtl/dlzc_mult_top.sv -- same XOR, same conditional negate on the inputs,
//    same conditional negate on the output -- so the difference that survives
//    is the difference between the datapaths, which is the thing under study.
//
// The UNSIGNED cores are vendored verbatim. They are the paper's contribution
// and they are correct: DRUM6_16_u and DRUM4_16_u both match
// golden_model.drum(a, b, k, 16) on 23,744/23,744 vectors.
//
// The zero guard that dlzc_mult needs explicitly is not needed here: DRUM's
// LOD emits all-zeros on a zero operand, P_Encoder's default arm returns 0,
// and mm/nn fall through to a[k-1:0] == 0, so tmp == 0 and the product is 0.
// That is the same behaviour as golden_model.drum's `if a == 0 or b == 0`.

`default_nettype none

(* use_dsp = "no" *)
module drum_signed_top #(
    parameter int K = 6              // 4 or 6; selects which vendored core
) (
    input  wire logic [15:0] operand1,
    input  wire logic [15:0] operand2,
    output logic      [31:0] output_mul
);

    logic [15:0] abs_value1;
    logic [15:0] abs_value2;
    logic [31:0] mul_out1;
    logic        sign_bit;

    assign sign_bit   = operand1[15] ^ operand2[15];
    assign abs_value1 = operand1[15] ? (~operand1 + 16'd1) : operand1;
    assign abs_value2 = operand2[15] ? (~operand2 + 16'd1) : operand2;

    // abs(-32768) == 32768 == 16'h8000 read as unsigned. These nets are
    // deliberately UNSIGNED for exactly the reason dlzc_mult_top's are:
    // declaring them signed would make the magnitude negative again.
    generate
        if (K == 6) begin : g_k6
            DRUM6_16_u u_core (.a(abs_value1), .b(abs_value2), .r(mul_out1));
        end else if (K == 4) begin : g_k4
            DRUM4_16_u u_core (.a(abs_value1), .b(abs_value2), .r(mul_out1));
        end else begin : g_bad
            $error("drum_signed_top: K must be 4 or 6; only those cores are vendored");
        end
    endgenerate

    always_comb begin
        if (sign_bit)
            output_mul = ~mul_out1 + 32'd1;
        else
            output_mul = mul_out1;
    end

endmodule

`default_nettype wire
