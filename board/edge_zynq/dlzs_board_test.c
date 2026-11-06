/*
 * DLZS AXI4-Lite on-board regression -- EDGE ZYNQ (xc7z010), bare metal.
 *
 * Put this file and dlzs_vectors.h into the src/ folder of a Vitis
 * "Hello World" application (delete helloworld.c). Output goes to the PS
 * UART at 115200 8N1. Copy the whole console log into evidence/.
 *
 * Register map (README section 8):
 *   0x00 W  CONTROL bit0 = start      0x08 RW operand A (low 16 bits)
 *   0x04 R  STATUS  bit0 busy, bit1 done   0x0C RW operand B (low 16 bits)
 *   0x10 R  result (signed 32-bit)
 */
#include <stdint.h>
#include "xil_io.h"
#include "xil_printf.h"
#include "xparameters.h"
#include "dlzs_vectors.h"

/* Cortex-A9 global timer, read directly (xtime_l.h is gone in the 2025.x
 * SDT flow). It counts at CPU/2: the EDGE preset runs the CPU at 667 MHz. */
#define GTIMER_LO   0xF8F00200U
#define GTIMER_HI   0xF8F00204U
#define GTIMER_CTRL 0xF8F00208U
#define GTIMER_HZ   333333333ULL
typedef uint64_t XTime;
static void XTime_GetTime(XTime *t)
{
    uint32_t hi, lo;
    do {
        hi = Xil_In32(GTIMER_HI);
        lo = Xil_In32(GTIMER_LO);
    } while (Xil_In32(GTIMER_HI) != hi);
    *t = ((uint64_t)hi << 32) | lo;
}
#define COUNTS_PER_SECOND GTIMER_HZ

/* The macro name depends on the Vitis version; fall back to the address
 * assigned in the Vivado Address Editor. */
#if defined(XPAR_DLZS_AXI_0_S00_AXI_BASEADDR)
#define DLZS_BASE XPAR_DLZS_AXI_0_S00_AXI_BASEADDR
#elif defined(XPAR_DLZS_AXI_0_BASEADDR)
#define DLZS_BASE XPAR_DLZS_AXI_0_BASEADDR
#else
#define DLZS_BASE 0x43C00000U
#endif

#define REG_CONTROL 0x00
#define REG_STATUS  0x04
#define REG_A       0x08
#define REG_B       0x0C
#define REG_RESULT  0x10
#define STATUS_DONE 0x2u
#define POLL_LIMIT  100000u
#define MAX_REPORT  20

/* Returns 0 on success, -1 on timeout. */
static int dlzs_mul(int16_t a, int16_t b, int32_t *p)
{
    Xil_Out32(DLZS_BASE + REG_A, (uint32_t)(uint16_t)a);
    Xil_Out32(DLZS_BASE + REG_B, (uint32_t)(uint16_t)b);
    Xil_Out32(DLZS_BASE + REG_CONTROL, 1u);
    for (uint32_t i = 0; i < POLL_LIMIT; i++) {
        if (Xil_In32(DLZS_BASE + REG_STATUS) & STATUS_DONE) {
            *p = (int32_t)Xil_In32(DLZS_BASE + REG_RESULT);
            return 0;
        }
    }
    return -1;
}

static int smoke(void)
{
    /* Hand-checkable: 3 snaps to 4 (ties round up), 0 guard, signs. */
    static const struct { int16_t a, b; int32_t p; } t[] = {
        {3, 5, 20}, {4, 5, 20}, {0, 1234, 0}, {-4, 5, -20},
        {4, -5, -20}, {-4, -5, 20}, {1, -32768, -32768},
    };
    int bad = 0;
    for (unsigned i = 0; i < sizeof t / sizeof t[0]; i++) {
        int32_t got;
        if (dlzs_mul(t[i].a, t[i].b, &got)) {
            xil_printf("  TIMEOUT a=%d b=%d\r\n", t[i].a, t[i].b);
            return -1;
        }
        xil_printf("  %6d x %6d = %11d  (expect %11d) %s\r\n", t[i].a, t[i].b,
                   got, t[i].p, got == t[i].p ? "ok" : "MISMATCH");
        bad += got != t[i].p;
    }
    return bad;
}

int main(void)
{
    xil_printf("\r\n=== DLZS on-board regression (EDGE ZYNQ xc7z010) ===\r\n");
    xil_printf("base 0x%08x  model %s  seed %d\r\n", DLZS_BASE,
               DLZS_VEC_MODEL, DLZS_VEC_SEED);
    xil_printf("vectors %d (%d corner + %d random)\r\n", DLZS_VEC_COUNT,
               DLZS_VEC_N_CORNER, DLZS_VEC_N_RANDOM);

    xil_printf("-- smoke test --\r\n");
    int s = smoke();
    if (s < 0) {
        xil_printf("ABORT: peripheral not responding (check bitstream/address)\r\n");
        return 1;
    }

    xil_printf("-- full regression --\r\n");
    uint32_t mismatches = 0, timeouts = 0;
    XTime t0, t1;
    Xil_Out32(GTIMER_CTRL, Xil_In32(GTIMER_CTRL) | 1u);   /* make sure it runs */
    XTime_GetTime(&t0);
    for (uint32_t i = 0; i < DLZS_VEC_COUNT; i++) {
        const dlzs_vec_t *v = &dlzs_vectors[i];
        int32_t got;
        if (dlzs_mul(v->a, v->b, &got)) {
            if (++timeouts <= MAX_REPORT)
                xil_printf("  TIMEOUT #%d a=%d b=%d\r\n", i, v->a, v->b);
            continue;
        }
        if (got != v->p && ++mismatches <= MAX_REPORT)
            xil_printf("  MISMATCH #%d a=%d b=%d got=%d expect=%d\r\n",
                       i, v->a, v->b, got, v->p);
    }
    XTime_GetTime(&t1);
    /* XTime counts at half the CPU clock (COUNTS_PER_SECOND). */
    uint32_t us = (uint32_t)((t1 - t0) / (COUNTS_PER_SECOND / 1000000));

    xil_printf("checked %d  mismatches %d  timeouts %d  smoke_fail %d\r\n",
               DLZS_VEC_COUNT, mismatches, timeouts, s);
    xil_printf("elapsed %d us (%d ns per AXI multiply incl. polling)\r\n",
               us, (uint32_t)(((uint64_t)us * 1000u) / DLZS_VEC_COUNT));
    xil_printf("RESULT: %s\r\n",
               (mismatches == 0 && timeouts == 0 && s == 0) ? "PASS" : "FAIL");
    return 0;
}
