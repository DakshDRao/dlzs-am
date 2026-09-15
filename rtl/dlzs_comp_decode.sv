`default_nettype none
// Signed-16 magnitude domain: 0..32768.
// This decoder deliberately avoids m >> (k-2): a variable shift synthesized
// into a mux network was the main timing cost of the first compensation build.
module dlzs_comp_decode(
    input wire [15:0] m,
    output logic [3:0] e,
    output logic use_three
);
    wire [3:0] k;
    wire all_zero;
    wire [1:0] region;
    lzc_16_meta lod(.input_operand(m), .output_power(k),
                    .all_zero(all_zero), .below(region));
    always_comb begin
        e = k;
        use_three = 1'b0;
        if (!all_zero && k != 0) begin
            case (region)
                2'b01, 2'b10: begin
                    use_three = 1'b1;
                    e = k - 4'd1;
                end
                2'b11: e = k + 4'd1;
                default: e = k;
            endcase
        end
    end
endmodule
`default_nettype wire
