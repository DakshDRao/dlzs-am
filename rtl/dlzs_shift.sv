`default_nettype none
module dlzs_shift(
    input logic [16:0] bp,
    input logic [3:0] e,
    output logic [31:0] p
);
logic [31:0] s1;
logic [31:0] sign_bp;
assign sign_bp = {{15{bp[16]}}, bp};
always_comb begin
    case (e[3:2])
        2'b01: s1 = sign_bp << 4'd4;
        2'b10: s1 = sign_bp << 4'd8;
        2'b11: s1 = sign_bp << 4'd12;
        default : s1 = sign_bp;
    endcase
end
always_comb begin
    case (e[1:0])
        2'b01: p = s1 << 3'd1;
        2'b10: p = s1 << 3'd2;
        2'b11: p = s1 << 3'd3;
        default : p = s1;
    endcase
end
endmodule
