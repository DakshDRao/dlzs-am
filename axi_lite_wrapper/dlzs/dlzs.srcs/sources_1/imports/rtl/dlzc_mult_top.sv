(*use_dsp = "no" *)
module dlzc_mult_top(
    input  wire logic [15:0] operand1,
    input  wire logic [15:0] operand2,
    output logic [31:0] output_mul
);

    logic [15:0] abs_value1;
    logic [15:0] abs_value2;
    logic [31:0] mul_out1;
    logic sign_bit;
    // Continuous assignments for inputs to the core
    assign sign_bit = operand1[15] ^ operand2[15];
    assign abs_value1 = operand1[15] ? (~operand1 + 16'd1) : operand1;
    assign abs_value2 = operand2[15] ? (~operand2 + 16'd1) : operand2; // Fixed the typo!

    dlzc_mult mult1(
        .a(abs_value1),
        .b(abs_value2),
        .mul_out(mul_out1)
    );

    // Combinational logic for the output
    always_comb begin
        if (sign_bit) begin
            output_mul = ~mul_out1 + 32'd1;
        end else begin
            output_mul = mul_out1;
        end
    end

endmodule
