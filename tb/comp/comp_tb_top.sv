`default_nettype none
module comp_tb_top(
    input wire clk,
    input wire [15:0] a, b,
    input wire [15:0] magnitude,
    input wire [16:0] bp,
    input wire select_three,
    input wire [17:0] shift_input,
    input wire [3:0] shift_amount,
    output wire [31:0] p, disabled_p, original_p, registered_p,
    output wire [3:0] decoded_e,
    output wire decoded_three,
    output wire [3:0] metadata_k,
    output wire [1:0] metadata_below,
    output wire metadata_zero,
    output wire [17:0] multiple,
    output wire [31:0] shifted
);
    dlzc_comp_top dut(.operand1(a), .operand2(b), .output_mul(p));
    dlzc_comp_top #(.COMPENSATE(0)) off_dut(.operand1(a), .operand2(b), .output_mul(disabled_p));
    dlzc_opt_top reference_dut(.operand1(a), .operand2(b), .output_mul(original_p));
    dlzc_comp_wrapper registered_dut(.clk(clk), .a(a), .b(b), .p(registered_p));
    dlzs_comp_decode decoder(.m(magnitude), .e(decoded_e), .use_three(decoded_three));
    lzc_16_meta metadata(.input_operand(magnitude), .output_power(metadata_k),
                         .all_zero(metadata_zero), .below(metadata_below));
    dlzs_b_multiple multiples(.bp(bp), .use_three(select_three), .selected(multiple));
    dlzc_shift #(.INPUT_WIDTH(18)) shifter(.bp(shift_input), .e(shift_amount), .p(shifted));
endmodule
`default_nettype wire
