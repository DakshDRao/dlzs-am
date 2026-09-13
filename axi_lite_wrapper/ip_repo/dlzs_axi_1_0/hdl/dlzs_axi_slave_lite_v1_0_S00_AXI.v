`timescale 1 ns / 1 ps
`default_nettype none

// Register map (32-bit, word-aligned accesses):
// 0x00 CONTROL: W bit 0 = START; reads zero.
// 0x04 STATUS:  R bit 0 = busy, bit 1 = done.
// 0x08 A:       RW, low 16 bits feed the signed multiplier.
// 0x0C B:       RW, low 16 bits feed the signed multiplier.
// 0x10 RESULT:  R, signed 32-bit result.
// 0x14..0x1C:   reserved, read zero, writes ignored.
// Writes to read-only registers are ignored and return OKAY.
// Unaligned accesses return SLVERR and have no write side effects.
module dlzs_axi_slave_lite_v1_0_S00_AXI #(
    parameter integer C_S_AXI_DATA_WIDTH = 32,
    parameter integer C_S_AXI_ADDR_WIDTH = 5
)(
    input  wire S_AXI_ACLK,
    input  wire S_AXI_ARESETN,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_AWADDR,
    input  wire [2:0] S_AXI_AWPROT,
    input  wire S_AXI_AWVALID,
    output wire S_AXI_AWREADY,
    input  wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_WDATA,
    input  wire [(C_S_AXI_DATA_WIDTH/8)-1:0] S_AXI_WSTRB,
    input  wire S_AXI_WVALID,
    output wire S_AXI_WREADY,
    output wire [1:0] S_AXI_BRESP,
    output wire S_AXI_BVALID,
    input  wire S_AXI_BREADY,
    input  wire [C_S_AXI_ADDR_WIDTH-1:0] S_AXI_ARADDR,
    input  wire [2:0] S_AXI_ARPROT,
    input  wire S_AXI_ARVALID,
    output wire S_AXI_ARREADY,
    output wire [C_S_AXI_DATA_WIDTH-1:0] S_AXI_RDATA,
    output wire [1:0] S_AXI_RRESP,
    output wire S_AXI_RVALID,
    input  wire S_AXI_RREADY
);
    // This peripheral implements the fixed 32-bit / 32-byte contract above.
    // synthesis translate_off
    initial begin
        if (C_S_AXI_DATA_WIDTH != 32 || C_S_AXI_ADDR_WIDTH != 5)
            $fatal(1, "DLZS AXI requires DATA_WIDTH=32 and ADDR_WIDTH=5");
    end
    // synthesis translate_on

    reg [C_S_AXI_ADDR_WIDTH-1:0] write_addr;
    reg [31:0] write_data;
    reg [3:0] write_strb;
    reg addr_prst, data_prst;
    reg axi_bvalid;
    reg [1:0] axi_bresp;

    reg [31:0] slv_reg2, slv_reg3;
    reg [15:0] operand_a_latched, operand_b_latched;
    wire [31:0] product_comb;
    reg [31:0] result_reg;
    reg busy, done;

    reg [31:0] axi_rdata;
    reg [1:0] axi_rresp;
    reg axi_rvalid;
    reg [31:0] read_value;
    integer byte_index;

    // One address slot and one data slot. Either may arrive first.
    // Slots remain occupied until the write response is accepted.
    assign S_AXI_AWREADY = S_AXI_ARESETN && !addr_prst && !axi_bvalid;
    assign S_AXI_WREADY  = S_AXI_ARESETN && !data_prst && !axi_bvalid;
    assign S_AXI_BVALID  = axi_bvalid;
    assign S_AXI_BRESP   = axi_bresp;

    wire write_commit;
    wire start;
    assign write_commit = S_AXI_ARESETN && addr_prst && data_prst
                          && !axi_bvalid;
    // A command event, never a stored CONTROL bit. Busy commands are ignored
    // by the execution controller, including on its completion edge.
    assign start = write_commit && (write_addr == 5'h00)
                   && write_strb[0] && write_data[0];

    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            write_addr <= 0;
            write_data <= 0;
            write_strb <= 0;
            addr_prst <= 0;
            data_prst <= 0;
            axi_bvalid <= 0;
            axi_bresp <= 2'b00;
        end else begin
            // Independent IFs permit simultaneous address and data capture.
            if (S_AXI_AWVALID && S_AXI_AWREADY) begin
                write_addr <= S_AXI_AWADDR;
                addr_prst <= 1'b1;
            end
            if (S_AXI_WVALID && S_AXI_WREADY) begin
                write_data <= S_AXI_WDATA;
                write_strb <= S_AXI_WSTRB;
                data_prst <= 1'b1;
            end
            if (write_commit) begin
                axi_bvalid <= 1'b1;
                axi_bresp <= (write_addr[1:0] == 2'b00) ? 2'b00 : 2'b10;
            end else if (axi_bvalid && S_AXI_BREADY) begin
                axi_bvalid <= 1'b0;
                addr_prst <= 1'b0;
                data_prst <= 1'b0;
            end
        end
    end

    // Only operand registers are software-writable storage.
    // Upper bytes read back normally but do not feed the 16-bit core.
    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            slv_reg2 <= 0;
            slv_reg3 <= 0;
        end else if (write_commit) begin
            for (byte_index = 0; byte_index < 4; byte_index = byte_index + 1) begin
                if (write_strb[byte_index]) begin
                    if (write_addr == 5'h08)
                        slv_reg2[byte_index*8 +: 8] <= write_data[byte_index*8 +: 8];
                    if (write_addr == 5'h0C)
                        slv_reg3[byte_index*8 +: 8] <= write_data[byte_index*8 +: 8];
                end
            end
        end
    end

    dlzc_opt_top dlzs1 (
        .operand1(operand_a_latched),
        .operand2(operand_b_latched),
        .output_mul(product_comb)
    );

    // Start edge: snapshot operands. Following edge: capture product.
    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            operand_a_latched <= 0;
            operand_b_latched <= 0;
            result_reg <= 0;
            busy <= 0;
            done <= 0;
        end else if (busy) begin
            result_reg <= product_comb;
            busy <= 1'b0;
            done <= 1'b1;
        end else if (start) begin
            operand_a_latched <= slv_reg2[15:0];
            operand_b_latched <= slv_reg3[15:0];
            busy <= 1'b1;
            done <= 1'b0;
        end
    end

    // Decode the incoming address; snapshot the value on its handshake.
    // A read concurrent with a register update observes the pre-update value.
    always @(*) begin
        case (S_AXI_ARADDR)
            5'h04: read_value = {30'b0, done, busy};
            5'h08: read_value = slv_reg2;
            5'h0C: read_value = slv_reg3;
            5'h10: read_value = result_reg;
            default: read_value = 32'b0;
        endcase
    end

    assign S_AXI_ARREADY = S_AXI_ARESETN && !axi_rvalid;
    assign S_AXI_RVALID = axi_rvalid;
    assign S_AXI_RDATA = axi_rdata;
    assign S_AXI_RRESP = axi_rresp;

    // Hold response data and status stable for arbitrary read backpressure.
    always @(posedge S_AXI_ACLK) begin
        if (!S_AXI_ARESETN) begin
            axi_rdata <= 0;
            axi_rresp <= 2'b00;
            axi_rvalid <= 0;
        end else if (S_AXI_ARVALID && S_AXI_ARREADY) begin
            axi_rdata <= read_value;
            axi_rresp <= (S_AXI_ARADDR[1:0] == 2'b00) ? 2'b00 : 2'b10;
            axi_rvalid <= 1'b1;
        end else if (axi_rvalid && S_AXI_RREADY) begin
            axi_rvalid <= 1'b0;
        end
    end
endmodule
`default_nettype wire
