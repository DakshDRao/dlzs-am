`default_nettype none

// Leading-one detector that also returns the two bits immediately below the
// leading one. Every bit selection is fixed inside a case item; the consumer
// therefore never needs a variable shift or variable part-select.
module lzc_8_meta(
    input  wire logic [7:0] input_operand,
    output logic [2:0] output_power,
    output logic       all_zero,
    output logic [1:0] below
);
    always_comb begin
        output_power = 3'b000;
        all_zero = 1'b0;
        below = 2'b00;
        casez (input_operand)
            8'b1???????: begin output_power = 3'd7; below = input_operand[6:5]; end
            8'b01??????: begin output_power = 3'd6; below = input_operand[5:4]; end
            8'b001?????: begin output_power = 3'd5; below = input_operand[4:3]; end
            8'b0001????: begin output_power = 3'd4; below = input_operand[3:2]; end
            8'b00001???: begin output_power = 3'd3; below = input_operand[2:1]; end
            8'b000001??: begin output_power = 3'd2; below = input_operand[1:0]; end
            8'b0000001?: begin output_power = 3'd1; below = {input_operand[0], 1'b0}; end
            8'b00000001: begin output_power = 3'd0; below = 2'b00; end
            default: all_zero = 1'b1;
        endcase
    end
endmodule

`default_nettype wire
