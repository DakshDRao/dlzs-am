`default_nettype none

// 16-bit metadata LZC. `below` is {m[k-1],m[k-2]} for k=floor(log2(m)).
// The two 8-bit blocks run in parallel. The explicit cross-half cases avoid a
// variable shift when the leading one is bit 8 or bit 9.
module lzc_16_meta(
    input  wire logic [15:0] input_operand,
    output logic [3:0] output_power,
    output logic       all_zero,
    output logic [1:0] below
);
    logic [2:0] high_power, low_power;
    logic [1:0] high_below, low_below;
    logic high_zero, low_zero;

    lzc_8_meta high_lzc(
        .input_operand(input_operand[15:8]),
        .output_power(high_power),
        .all_zero(high_zero),
        .below(high_below)
    );
    lzc_8_meta low_lzc(
        .input_operand(input_operand[7:0]),
        .output_power(low_power),
        .all_zero(low_zero),
        .below(low_below)
    );

    always_comb begin
        all_zero = high_zero & low_zero;
        output_power = 4'b0000;
        below = 2'b00;

        if (!high_zero) begin
            output_power = {1'b1, high_power};
            if (high_power >= 3'd2)
                below = high_below;
            else if (high_power == 3'd1)
                below = {input_operand[8], input_operand[7]};
            else
                below = {input_operand[7], input_operand[6]};
        end else if (!low_zero) begin
            output_power = {1'b0, low_power};
            if (low_power >= 3'd2)
                below = low_below;
            else if (low_power == 3'd1)
                below = {input_operand[0], 1'b0};
            else
                below = 2'b00;
        end
    end
endmodule

`default_nettype wire
