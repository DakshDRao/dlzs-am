#!/usr/bin/env bash
# Run from the repository root: bash scripts/export_yosys.sh
# Uses Yosys show -format svg directly, matching the verified manual command.
set -euo pipefail
command -v yosys >/dev/null || { echo "Install yosys first."; exit 1; }
command -v dot >/dev/null || { echo "Install graphviz first."; exit 1; }
[[ -f rtl/dlzc_opt_top.sv && -d baselines ]] || {
    echo "Run this script from the dlzs-am repository root."; exit 1;
}
out="docs/images/schematics"
logs="work/yosys-diagrams/logs"
mkdir -p "$out" "$logs"
failures=()
count=0

rtl="rtl/lzc_8.sv rtl/lzc_16.sv rtl/dlzs_snap_exp.sv rtl/dlzs_b_prep.sv rtl/dlzc_shift.sv rtl/dlzc_mult.sv rtl/dlzc_mult_top.sv rtl/dlzc_opt_top.sv"
opt="$rtl baselines/drum_opt/drum_opt_operand.sv baselines/drum_opt/drum_opt_shift.sv baselines/drum_opt/drum_opt_top.sv"
drum="baselines/drum/DRUM4_16_u.v baselines/drum/DRUM6_16_u.v baselines/drum/drum_signed_top.sv"
mitchell="$rtl baselines/mitchell/mitchell_mult.sv baselines/mitchell/mitchell_mult_top.sv"

render() {
    local name="$1" top="$2" sources="$3" k="${4:-}"
    local param="" log="$logs/$name.log"
    [[ -z "$k" ]] || param="chparam -set K $k $top;"
    echo "Generating $name.svg"
    if yosys -p "
        read_verilog -sv $sources;
        $param
        hierarchy -check -top $top;
        proc;
        opt_clean;
        show -format svg -prefix $out/$name $top;
    " >"$log" 2>&1 &&
       [[ -s "$out/$name.svg" ]]; then
        # Preserve Yosys's DOT intermediate outside the final-image folder.
        if [[ -f "$out/$name.dot" ]]; then
            mv -f -- "$out/$name.dot" "$logs/$name.dot"
        fi
        count=$((count + 1))
    else
        failures+=("$name")
        echo "FAILED: $name (see $log)" >&2
    fi
}

for top in lzc_8 lzc_16 dlzs_snap_exp dlzs_b_prep dlzc_shift dlzc_mult dlzc_mult_top; do
    render "$top" "$top" "$rtl"
done
render dlzs_opt_core dlzc_opt_top "rtl/lzc_8.sv rtl/lzc_16.sv rtl/dlzs_snap_exp.sv rtl/dlzs_b_prep.sv rtl/dlzc_shift.sv rtl/dlzc_opt_top.sv"
render dlzc_opt_wrapper dlzc_opt_wrapper     "$rtl synth/wrappers/dlzc_opt_wrapper.sv"
render exact exact "baselines/exact/exact.sv"
render mitchell_mult mitchell_mult "$mitchell"
render mitchell_mult_top mitchell_mult_top "$mitchell"

for k in 3 4 5 6 7 8; do
    render "drum_opt_k$k" drum_opt_top "$opt" "$k"
    render "drum_opt_operand_k$k" drum_opt_operand "$opt" "$k"
    render "drum_opt_shift_k$k" drum_opt_shift "$opt" "$k"
done
for k in 4 6; do
    render "drum_signed_k$k" drum_signed_top "$drum" "$k"
    render "drum_unsigned_k$k" "DRUM${k}_16_u" "$drum"
done

echo "Generated $count diagrams in $out"
echo "Diagnostic logs are in $logs"
if (("${#failures[@]}")); then
    printf 'Failed: %s\n' "${failures[@]}" >&2
    exit 1
fi
echo "All 34 diagrams generated successfully."
