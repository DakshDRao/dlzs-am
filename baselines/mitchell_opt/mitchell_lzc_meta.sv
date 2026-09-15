`default_nettype none

// Leading-one detector for the optimized Mitchell datapath.
//
// In addition to the exponent k, this block returns the raw mantissa bits
// M = X - 2^k.  The reference implementation computes M with a variable
// one-hot subtractor.  Selecting the already-known lower bits here removes
// that subtractor from the datapath while preserving Mitchell's bit-exact
// definition for every non-zero 16-bit operand.
module mitchell_lzc_meta (
    input  wire logic [15:0] input_operand,
    output logic      [3:0]  output_power,
    output logic             all_zero,
    output logic      [15:0] mantissa
);
    always_comb begin
        output_power = 4'd0;
        all_zero     = 1'b0;
        mantissa     = 16'd0;

        casez (input_operand)
            16'b1???????????????: begin
                output_power = 4'd15;
                mantissa     = {1'b0, input_operand[14:0]};
            end
            16'b01??????????????: begin
                output_power = 4'd14;
                mantissa     = {2'b00, input_operand[13:0]};
            end
            16'b001?????????????: begin
                output_power = 4'd13;
                mantissa     = {3'b000, input_operand[12:0]};
            end
            16'b0001????????????: begin
                output_power = 4'd12;
                mantissa     = {4'b0000, input_operand[11:0]};
            end
            16'b00001???????????: begin
                output_power = 4'd11;
                mantissa     = {5'b00000, input_operand[10:0]};
            end
            16'b000001??????????: begin
                output_power = 4'd10;
                mantissa     = {6'b000000, input_operand[9:0]};
            end
            16'b0000001?????????: begin
                output_power = 4'd9;
                mantissa     = {7'b0000000, input_operand[8:0]};
            end
            16'b00000001????????: begin
                output_power = 4'd8;
                mantissa     = {8'b00000000, input_operand[7:0]};
            end
            16'b000000001???????: begin
                output_power = 4'd7;
                mantissa     = {9'b000000000, input_operand[6:0]};
            end
            16'b0000000001??????: begin
                output_power = 4'd6;
                mantissa     = {10'b0000000000, input_operand[5:0]};
            end
            16'b00000000001?????: begin
                output_power = 4'd5;
                mantissa     = {11'b00000000000, input_operand[4:0]};
            end
            16'b000000000001????: begin
                output_power = 4'd4;
                mantissa     = {12'b000000000000, input_operand[3:0]};
            end
            16'b0000000000001???: begin
                output_power = 4'd3;
                mantissa     = {13'b0000000000000, input_operand[2:0]};
            end
            16'b00000000000001??: begin
                output_power = 4'd2;
                mantissa     = {14'b00000000000000, input_operand[1:0]};
            end
            16'b000000000000001?: begin
                output_power = 4'd1;
                mantissa     = {15'b000000000000000, input_operand[0]};
            end
            16'b0000000000000001: begin
                output_power = 4'd0;
                mantissa     = 16'd0;
            end
            default: begin
                output_power = 4'd0;
                all_zero     = 1'b1;
                mantissa     = 16'd0;
            end
        endcase
    end
endmodule

`default_nettype wire
