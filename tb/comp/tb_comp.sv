`timescale 1ns/1ps
module tb_comp;
reg [15:0] a,b;
wire [31:0] p, off_p, baseline;
integer ai,bi,j,k,m,step,rounded,expected,bb,count;
integer bs[0:9];
dlzc_comp_top dut(a,b,p);
dlzc_comp_top #(.COMPENSATE(0)) disabled_dut(a,b,off_p);
dlzc_opt_top original_dut(a,b,baseline);
task check;
begin
 #1;
 ai=$signed(a); bb=$signed(b);
 m=ai<0 ? -ai:ai;
 k=0;
 for(integer z=0;z<16;z=z+1) if((m>>z)!=0) k=z;
 step= k>0 ? (1<<(k-1)):1;
 rounded=((m+step/2)/step)*step;
 expected=(ai<0 ? -rounded:rounded)*bb;
 if($signed(p)!==expected) $fatal(1,"Mismatch a=%0d b=%0d got=%0d expected=%0d",ai,bb,$signed(p),expected);
 if(off_p!==baseline) $fatal(1,"Disabled mismatch");
 count=count+1;
end
endtask
initial begin
 count=0;
 bs[0]=-32768; bs[1]=-32767; bs[2]=-12345; bs[3]=-3; bs[4]=-1;
 bs[5]=0; bs[6]=1; bs[7]=3; bs[8]=12345; bs[9]=32767;
 for(integer x=0;x<65536;x=x+1) begin
  a=x;
  for(j=0;j<10;j=j+1) begin b=bs[j];check();end
 end
 // Every B under both signs and each multiplier-selection mode.
 for(integer y=0;y<65536;y=y+1) begin
  b=y;
  a=3;check(); a=-3;check(); a=1;check(); a=-1;check();a=0;check();
 end
 $display("PASS: %0d RTL vectors; compensated reference and disabled equivalence",count);
 $finish;
end
endmodule

