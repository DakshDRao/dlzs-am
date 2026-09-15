"""Compensated DLZS: blocks, original-mode equivalence, and actual OOC harness."""
import os
import cocotb
from cocotb.triggers import Timer
from golden_model import SIGNED_DESIGNS, to_signed
from sweep import sampled_pairs

N_RANDOM = int(os.environ.get("COMP_N_RANDOM", "") or 200000)
MODEL = SIGNED_DESIGNS["dlzs_three_level"]
BASE = SIGNED_DESIGNS["dlzs_nearest_linear"]


def signed(handle, width):
    return to_signed(int(handle.value), width)


def idle(dut):
    for name in ("clk", "a", "b", "magnitude", "bp", "select_three",
                 "shift_input", "shift_amount"):
        getattr(dut, name).value = 0


async def check(dut, a, b):
    dut.a.value = a & 65535
    dut.b.value = b & 65535
    await Timer(1, unit="ns")
    assert signed(dut.p, 32) == MODEL(a, b, 16), (a, b)
    assert signed(dut.disabled_p, 32) == BASE(a, b, 16), (a, b)
    assert int(dut.disabled_p.value) == int(dut.original_p.value), (a, b)
    assert abs(signed(dut.p, 32)) <= 1 << 30


@cocotb.test()
async def decoder_exhaustive(dut):
    idle(dut)
    for m in range(32769):
        dut.magnitude.value = m
        await Timer(1, unit="ns")
        if m:
            represented = (3 if int(dut.decoded_three.value) else 1) << int(dut.decoded_e.value)
            assert represented == MODEL(m, 1, 17), m
        else:
            assert int(dut.decoded_e.value) == 0


@cocotb.test()
async def metadata_exhaustive(dut):
    """The fixed-position metadata detector must match the mathematical bits."""
    idle(dut)
    for m in range(32769):
        dut.magnitude.value = m
        await Timer(1, unit="ns")
        if m == 0:
            assert int(dut.metadata_zero.value) == 1
            assert int(dut.metadata_k.value) == 0
            assert int(dut.metadata_below.value) == 0
            continue
        k = m.bit_length() - 1
        expected_below = ((m >> (k - 1)) & 1) << 1 if k >= 1 else 0
        if k >= 2:
            expected_below |= (m >> (k - 2)) & 1
        assert int(dut.metadata_zero.value) == 0, m
        assert int(dut.metadata_k.value) == k, m
        assert int(dut.metadata_below.value) == expected_below, m


@cocotb.test()
async def multiples_exhaustive(dut):
    idle(dut)
    for bp in range(-32768, 32769):
        dut.bp.value = bp & 131071
        for select in (0, 1):
            dut.select_three.value = select
            await Timer(1, unit="ns")
            assert signed(dut.multiple, 18) == bp * (3 if select else 1)


@cocotb.test()
async def shifter_extremes(dut):
    idle(dut)
    for value in (-98304, -32768, -1, 0, 1, 32768, 98304):
        for e in range(16):
            dut.shift_input.value = value & 262143
            dut.shift_amount.value = e
            await Timer(1, unit="ns")
            assert int(dut.shifted.value) == (value << e) & 0xffffffff


@cocotb.test()
async def all_a_extreme_b(dut):
    idle(dut)
    for a in range(-32768, 32768):
        for b in (-32768, -32767, -3, -1, 0, 1, 3, 32767):
            await check(dut, a, b)


@cocotb.test()
async def sweep_vectors(dut):
    idle(dut)
    pairs, _ = sampled_pairs(16, N_RANDOM)
    for a, b in pairs:
        await check(dut, to_signed(a, 16), to_signed(b, 16))


@cocotb.test()
async def synthesis_harness(dut):
    idle(dut)
    previous = None
    # Two register boundaries: each rising edge returns the previous inputs.
    for a, b in [(0, 0), (3, -32768), (-32768, -32768), (32767, 32767),
                 (5, 7), (7, -5), (0, 0)]:
        dut.clk.value = 0
        dut.a.value = a & 65535
        dut.b.value = b & 65535
        await Timer(1, unit="ns")
        dut.clk.value = 1
        await Timer(1, unit="ns")
        if previous is not None:
            assert signed(dut.registered_p, 32) == MODEL(*previous, 16)
        previous = (a, b)
