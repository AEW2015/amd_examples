#include "trng_test.h"

#define MMIO32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define TRNG_BASE       0x04120000u
#define TRNG_INT_CTRL   (TRNG_BASE + 0x00u)
#define TRNG_STATUS     (TRNG_BASE + 0x04u)
#define TRNG_CTRL       (TRNG_BASE + 0x08u)
#define TRNG_CTRL_2     (TRNG_BASE + 0x0cu)
#define TRNG_CTRL_3     (TRNG_BASE + 0x10u)
#define TRNG_CORE_OUT   (TRNG_BASE + 0xc0u)
#define TRNG_RESET      (TRNG_BASE + 0xd0u)
#define TRNG_OSC_EN     (TRNG_BASE + 0xd4u)

#define ST_QCNT_MASK    0x00000e00u
#define ST_QCNT_SHIFT   9u
#define ST_CERTF        0x00000008u
#define ST_DTF          0x00000002u
#define ST_DONE         0x00000001u
#define ST_HEALTH_MASK  (ST_CERTF | ST_DTF)

#define CTRL_PERSO_DISABLE 0x00000400u
#define CTRL_SINGLE_GEN    0x00000200u
#define CTRL_PRNG_MODE     0x00000080u
#define CTRL_PRNG_START    0x00000020u
#define CTRL_PRNG_XS       0x00000008u
#define CTRL_TRSS_EN       0x00000004u
#define CTRL_PRNG_SRST     0x00000001u
#define CTRL_ACTIVITY_MASK (CTRL_PRNG_START)

#define RESET_BIT       0x00000001u
#define OSC_ENABLE      0x00000001u
#define REP_CUTOFF      66u
#define ADAPT_CUTOFF    645u
#define DIT_VALUE       12u
#define DF_LENGTH       7u
#define SEED_LIFE       256u /* HRNG reseed interval configured by vendor default */

#ifndef PMC_TRNG_MCLK_HZ
#define PMC_TRNG_MCLK_HZ 400000000u /* conservative delay bound, not a measured clock */
#endif
#define RESET_DELAY_CYCLES ((PMC_TRNG_MCLK_HZ / 100000u) + 1u) /* 10 us */
#define POLL_LIMIT_CYCLES 500000000u
#define GENERATE_BYTES 32u
#define GENERATE_WORDS 8u

#define OUT_STATUS       2u
#define OUT_INITIAL_STAT 3u
#define OUT_INITIAL_CTRL 4u
#define OUT_INITIAL_OSC  5u
#define OUT_INITIAL_RST  6u
#define OUT_FINAL_STAT   7u
#define OUT_FINAL_CTRL  8u
#define OUT_FINAL_OSC   9u
#define OUT_FINAL_RST  10u
#define OUT_ELAPSED     11u
#define OUT_SAMPLE_A    16u
#define OUT_SAMPLE_B    24u
#define OUT_EQUAL       12u

static uint32_t rdcycle32(void)
{
    uint32_t value;
    __asm__ volatile("csrr %0,mcycle" : "=r"(value) :: "memory");
    return value;
}

static void io_barrier(void)
{
    __asm__ volatile("fence rw,rw" ::: "memory");
}

static void delay_reset(void)
{
    uint32_t start = rdcycle32();
    while ((uint32_t)(rdcycle32() - start) < RESET_DELAY_CYCLES) {
        __asm__ volatile("nop");
    }
}

static int wait_status(uint32_t mask, uint32_t expected)
{
    uint32_t start = rdcycle32();
    do {
        uint32_t status = MMIO32(TRNG_STATUS);
        if ((status & ST_HEALTH_MASK) != 0u) return -1;
        if ((status & mask) == expected) return 0;
    } while ((uint32_t)(rdcycle32() - start) < POLL_LIMIT_CYCLES);
    return -2;
}

static void set_bits(uint32_t address, uint32_t mask, uint32_t value)
{
    uint32_t current = MMIO32(address);
    MMIO32(address) = (current & ~mask) | (value & mask);
    io_barrier();
}

static void reset_core(void)
{
    set_bits(TRNG_RESET, RESET_BIT, RESET_BIT);
    delay_reset();
    set_bits(TRNG_RESET, RESET_BIT, 0u);
}

static void reset_prng(void)
{
    set_bits(TRNG_CTRL, CTRL_PRNG_SRST, CTRL_PRNG_SRST);
    delay_reset();
    set_bits(TRNG_CTRL, CTRL_PRNG_SRST, 0u);
}

static int reseed_hrng(void)
{
    /* The register field layout comes from xtrngpsx_hw.h/CDO. CTRL_2/3 are
       programmed as full words because vendor header declares them write-only. */
    MMIO32(TRNG_CTRL_2) = (REP_CUTOFF << 8) | DIT_VALUE;
    MMIO32(TRNG_CTRL_3) = (ADAPT_CUTOFF << 8) | DF_LENGTH;
    io_barrier();

    set_bits(TRNG_CTRL, CTRL_PERSO_DISABLE | CTRL_PRNG_START,
             CTRL_PERSO_DISABLE);
    set_bits(TRNG_OSC_EN, OSC_ENABLE, OSC_ENABLE);
    set_bits(TRNG_CTRL, CTRL_PRNG_MODE | CTRL_TRSS_EN | CTRL_PRNG_XS,
             CTRL_TRSS_EN);
    set_bits(TRNG_CTRL, CTRL_PRNG_START, CTRL_PRNG_START);

    if (wait_status(ST_DONE, ST_DONE) != 0) return -1;
    set_bits(TRNG_CTRL, CTRL_PRNG_START | CTRL_TRSS_EN, 0u);
    return 0;
}

static int generate_32(uint32_t out[GENERATE_WORDS], int start_stream)
{
    unsigned i;
    if (start_stream) {
        set_bits(TRNG_CTRL,
                 CTRL_PRNG_MODE | CTRL_SINGLE_GEN | CTRL_PRNG_START,
                 CTRL_PRNG_MODE);
        set_bits(TRNG_CTRL, CTRL_PRNG_START, CTRL_PRNG_START);
    }

    for (i = 0u; i < 2u; ++i) {
        if (wait_status(ST_QCNT_MASK, 4u << ST_QCNT_SHIFT) != 0) return -1;
        for (unsigned j = 0u; j < 4u; ++j) {
            uint32_t raw = MMIO32(TRNG_CORE_OUT); /* FIFO pop: intentionally only here */
            out[i * 4u + j] = __builtin_bswap32(raw);
        }
        io_barrier();
    }
    return 0;
}

static void restore_register_state(uint32_t ctrl, uint32_t osc, uint32_t reset)
{
    /* End in reset while restoring the entry configuration. Internal DRBG
       state cannot be reconstructed; call only when the unit is unused. */
    set_bits(TRNG_RESET, RESET_BIT, RESET_BIT);
    delay_reset();
    MMIO32(TRNG_CTRL) = ctrl;
    MMIO32(TRNG_OSC_EN) = osc;
    io_barrier();
    set_bits(TRNG_RESET, RESET_BIT, reset & RESET_BIT);
}

unsigned pmc_trng_test(uint32_t out[PMC_TRNG_TEST_WORDS])
{
    uint32_t initial_ctrl, initial_osc, initial_reset, initial_status;
    uint32_t start, status = PMC_TRNG_TEST_OK;
    unsigned i;

    if (out == 0) return PMC_TRNG_TEST_BAD_ARGUMENT;
    for (i = 0u; i < PMC_TRNG_TEST_WORDS; ++i) out[i] = 0u;
    out[0] = PMC_TRNG_TEST_MAGIC;
    out[1] = PMC_TRNG_TEST_VERSION;

    initial_status = MMIO32(TRNG_STATUS);
    initial_ctrl = MMIO32(TRNG_CTRL);
    initial_osc = MMIO32(TRNG_OSC_EN);
    initial_reset = MMIO32(TRNG_RESET);
    out[OUT_INITIAL_STAT] = initial_status;
    out[OUT_INITIAL_CTRL] = initial_ctrl;
    out[OUT_INITIAL_OSC] = initial_osc;
    out[OUT_INITIAL_RST] = initial_reset;
    start = rdcycle32();

    /* Do not clear a previously reported health failure, consume a pending
       output word, or take over a currently-started operation. */
    if ((initial_status & ST_HEALTH_MASK) != 0u) {
        status = PMC_TRNG_TEST_PREEXISTING_HEALTH_FLAG;
        goto done;
    }
    if (((initial_status & ST_QCNT_MASK) != 0u) ||
        ((initial_ctrl & CTRL_ACTIVITY_MASK) != 0u)) {
        status = PMC_TRNG_TEST_BUSY_OR_QUEUED;
        goto done;
    }

    reset_core();
    reset_prng();
    if (reseed_hrng() != 0) {
        uint32_t s = MMIO32(TRNG_STATUS);
        status = (s & ST_HEALTH_MASK) ? PMC_TRNG_TEST_RESEED_HEALTH_FAILURE :
                                        PMC_TRNG_TEST_RESEED_TIMEOUT;
        goto cleanup;
    }
    if (generate_32(&out[OUT_SAMPLE_A], 1) != 0) {
        uint32_t s = MMIO32(TRNG_STATUS);
        status = (s & ST_HEALTH_MASK) ? PMC_TRNG_TEST_GENERATE_HEALTH_FAILURE :
                                        PMC_TRNG_TEST_GENERATE_TIMEOUT;
        goto cleanup;
    }
    if (generate_32(&out[OUT_SAMPLE_B], 0) != 0) {
        uint32_t s = MMIO32(TRNG_STATUS);
        status = (s & ST_HEALTH_MASK) ? PMC_TRNG_TEST_GENERATE_HEALTH_FAILURE :
                                        PMC_TRNG_TEST_GENERATE_TIMEOUT;
        goto cleanup;
    }
    out[OUT_EQUAL] = 1u;
    for (i = 0u; i < GENERATE_WORDS; ++i) {
        if (out[OUT_SAMPLE_A + i] != out[OUT_SAMPLE_B + i]) {
            out[OUT_EQUAL] = 0u;
            break;
        }
    }
    if (out[OUT_EQUAL] != 0u) status = PMC_TRNG_TEST_IDENTICAL_SAMPLES;

cleanup:
    restore_register_state(initial_ctrl, initial_osc, initial_reset);
done:
    out[OUT_STATUS] = status;
    out[OUT_FINAL_STAT] = MMIO32(TRNG_STATUS);
    out[OUT_FINAL_CTRL] = MMIO32(TRNG_CTRL);
    out[OUT_FINAL_OSC] = MMIO32(TRNG_OSC_EN);
    out[OUT_FINAL_RST] = MMIO32(TRNG_RESET);
    out[OUT_ELAPSED] = (uint32_t)(rdcycle32() - start);
    io_barrier();
    return status;
}
