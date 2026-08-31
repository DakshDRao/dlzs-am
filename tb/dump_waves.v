// Waveform dump helper, included only when WAVES=1 under Icarus.
module cocotb_waves;
initial begin
    $dumpfile("lzc.fst");
    $dumpvars(0, lzc_tb_top);
end
endmodule