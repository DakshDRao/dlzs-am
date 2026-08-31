module lzc_8(
    input logic [7:0] input_operand,
    output logic [2:0] output_power,
    output logic all_zero
);
always_comb begin
    output_power = 3'b0;
    all_zero = 1'b0;
    casez(input_operand)
        8'b1???????: output_power = 3'b111;
        8'b01??????: output_power = 3'b110;
        8'b001?????: output_power = 3'b101;
        8'b0001????: output_power = 3'b100;
        8'b00001???: output_power = 3'b011;
        8'b000001??: output_power = 3'b010;
        8'b0000001?: output_power = 3'b001;
        8'b00000001: output_power = 3'b000;
        default: all_zero = 1;
    endcase
end
endmodule
