#include "pmc_stream.h"

#include <stddef.h>

#define REG32(address) (*(volatile uint32_t *)(uintptr_t)(address))
#define SSS_CONFIG       UINT32_C(0x040a0090)
#define DMA_SRC_ADDR     UINT32_C(0x040e0000)
#define DMA_SRC_SIZE     UINT32_C(0x040e0004)
#define DMA_SRC_CTRL     UINT32_C(0x040e000c)
#define DMA_SRC_ISR      UINT32_C(0x040e0014)
#define DMA_SRC_MSB      UINT32_C(0x040e0028)
#define DMA_DST_ADDR     UINT32_C(0x040e0800)
#define DMA_DST_SIZE     UINT32_C(0x040e0804)
#define DMA_DST_CTRL     UINT32_C(0x040e080c)
#define DMA_DST_ISR      UINT32_C(0x040e0814)
#define DMA_DST_MSB      UINT32_C(0x040e0828)
#define SHA_START        UINT32_C(0x04100000)
#define SHA_RESET        UINT32_C(0x04100004)
#define SHA_STATUS       UINT32_C(0x04100008)
#define SHA_DIGEST       UINT32_C(0x04100010)
#define SHA_MODE         UINT32_C(0x041000a0)
#define SHA_AUTO         UINT32_C(0x041000a4)
#define DMA_DONE         UINT32_C(0x00000002)
#define DMA_SRC_ERRORS   UINT32_C(0x0000005c)
#define DMA_DST_ERRORS   UINT32_C(0x000000dc)
#define POLL_LIMIT       UINT32_C(10000000)

static int initialized;

static void io_fence(void)
{
    __asm__ volatile("fence iorw, iorw" ::: "memory");
}

static uint64_t cycle64(void)
{
    uint32_t high_before, low, high_after;
    do {
        __asm__ volatile("csrr %0, mcycleh" : "=r"(high_before) :: "memory");
        __asm__ volatile("csrr %0, mcycle" : "=r"(low) :: "memory");
        __asm__ volatile("csrr %0, mcycleh" : "=r"(high_after) :: "memory");
    } while (high_before != high_after);
    return ((uint64_t)high_before << 32) | low;
}

static int valid_range(uint32_t address, uint32_t bytes)
{
    uint64_t end = (uint64_t)address + bytes;
    uint64_t scratch_end = (uint64_t)PMC_STREAM_SCRATCH_BASE + PMC_STREAM_WINDOW_SIZE;
    uint64_t stage_end = (uint64_t)PMC_STREAM_STAGE_BASE + PMC_STREAM_WINDOW_SIZE;
    int in_scratch = address >= PMC_STREAM_SCRATCH_BASE && end <= scratch_end;
    int in_stage = address >= PMC_STREAM_STAGE_BASE && end <= stage_end;
    return (address & 3u) == 0 && bytes >= 4u && bytes <= PMC_STREAM_MAX_BYTES &&
           (bytes & 3u) == 0 && (in_scratch || in_stage);
}

static void init_result(pmc_stream_result_t *result)
{
    if (result != NULL) {
        result->status = PMC_STREAM_OK;
        result->source_isr = 0;
        result->destination_isr = 0;
        result->engine_status = 0;
        result->source_address = 0;
        result->destination_address = 0;
        result->elapsed_cycles = 0;
        result->quiescent = 0;
    }
}

static void finish_result(pmc_stream_result_t *result, pmc_stream_status_t status,
                          uint64_t start, int quiescent, uint32_t source_isr,
                          uint32_t destination_isr, uint32_t engine_status,
                          uint32_t source_address, uint32_t destination_address)
{
    if (result == NULL)
        return;
    result->status = status;
    result->source_isr = source_isr;
    result->destination_isr = destination_isr;
    result->engine_status = engine_status;
    result->source_address = source_address;
    result->destination_address = destination_address;
    result->elapsed_cycles = cycle64() - start;
    result->quiescent = (uint8_t)(quiescent != 0);
}

static void restore_route(uint32_t previous, int quiescent)
{
    if (quiescent) {
        REG32(SSS_CONFIG) = previous;
        io_fence();
    }
}

pmc_stream_status_t pmc_stream_init(void)
{
    /* Not per-transfer: caller invokes this only after confirming DMA is idle. */
    if (initialized)
        return PMC_STREAM_INVALID;
    REG32(DMA_SRC_CTRL) = UINT32_C(0x013ffa00);
    REG32(DMA_DST_CTRL) = UINT32_C(0x813ffa00);
    REG32(DMA_SRC_MSB) = 0;
    REG32(DMA_DST_MSB) = 0;
    REG32(DMA_SRC_ISR) = DMA_DONE;
    REG32(DMA_DST_ISR) = DMA_DONE;
    io_fence();
    initialized = 1;
    return PMC_STREAM_OK;
}

pmc_stream_status_t pmc_stream_dma_copy(uint32_t source, uint32_t destination,
                                         uint32_t bytes, uint64_t timeout_cycles,
                                         pmc_stream_result_t *result)
{
    uint64_t start;
    uint32_t previous_route;
    pmc_stream_status_t status = PMC_STREAM_OK;
    int quiescent = 0;

    init_result(result);
    if (!initialized)
    {
        if (result != NULL) result->status = PMC_STREAM_NOT_INITIALIZED;
        return PMC_STREAM_NOT_INITIALIZED;
    }
    if (!valid_range(source, bytes) || !valid_range(destination, bytes) ||
        timeout_cycles == 0 ||
        ((uint64_t)source < (uint64_t)destination + bytes &&
         (uint64_t)destination < (uint64_t)source + bytes))
    {
        if (result != NULL) result->status = PMC_STREAM_INVALID;
        return PMC_STREAM_INVALID;
    }

    previous_route = REG32(SSS_CONFIG);
    REG32(SSS_CONFIG) = 5u; /* DMA source -> DMA destination */
    REG32(DMA_SRC_ISR) = DMA_DONE;
    REG32(DMA_DST_ISR) = DMA_DONE;
    REG32(DMA_DST_ADDR) = destination;
    REG32(DMA_DST_MSB) = 0;
    REG32(DMA_DST_SIZE) = bytes;
    REG32(DMA_SRC_ADDR) = source;
    REG32(DMA_SRC_MSB) = 0;
    io_fence();
    start = cycle64();
    REG32(DMA_SRC_SIZE) = bytes; /* observed source-size trigger */

    status = PMC_STREAM_TIMEOUT;
    for (uint32_t poll = 0; poll < POLL_LIMIT; ++poll) {
        uint32_t source_isr = REG32(DMA_SRC_ISR);
        uint32_t destination_isr = REG32(DMA_DST_ISR);
        if ((source_isr & DMA_DONE) && (destination_isr & DMA_DONE))
            quiescent = 1;
        if ((source_isr & DMA_SRC_ERRORS) != 0) {
            status = PMC_STREAM_SOURCE_ERROR;
            break;
        }
        if ((destination_isr & DMA_DST_ERRORS) != 0) {
            status = PMC_STREAM_DESTINATION_ERROR;
            break;
        }
        if (quiescent) {
            status = (REG32(DMA_SRC_ADDR) == source + bytes &&
                      REG32(DMA_DST_ADDR) == destination + bytes)
                         ? PMC_STREAM_OK : PMC_STREAM_PROGRESS_MISMATCH;
            break;
        }
        if (cycle64() - start >= timeout_cycles)
            break;
    }

    uint32_t final_src_isr = REG32(DMA_SRC_ISR);
    uint32_t final_dst_isr = REG32(DMA_DST_ISR);
    uint32_t final_src_addr = REG32(DMA_SRC_ADDR);
    uint32_t final_dst_addr = REG32(DMA_DST_ADDR);
    if ((final_src_isr & DMA_DONE) && (final_dst_isr & DMA_DONE))
        quiescent = 1;
    if (quiescent && (status == PMC_STREAM_OK ||
                      status == PMC_STREAM_PROGRESS_MISMATCH)) {
        REG32(DMA_SRC_ISR) = DMA_DONE;
        REG32(DMA_DST_ISR) = DMA_DONE;
        io_fence();
    }
    finish_result(result, status, start, quiescent, final_src_isr,
                  final_dst_isr, 0, final_src_addr, final_dst_addr);
    restore_route(previous_route, quiescent);
    return status;
}

pmc_stream_status_t pmc_stream_sha3_256(uint32_t source, uint32_t bytes,
                                         uint64_t timeout_cycles,
                                         uint8_t digest[32],
                                         pmc_stream_result_t *result)
{
    uint64_t start;
    uint32_t previous_route;
    pmc_stream_status_t status = PMC_STREAM_OK;
    int quiescent = 0;

    init_result(result);
    if (!initialized)
    {
        if (result != NULL) result->status = PMC_STREAM_NOT_INITIALIZED;
        return PMC_STREAM_NOT_INITIALIZED;
    }
    if (digest == NULL || !valid_range(source, bytes) || timeout_cycles == 0)
    {
        if (result != NULL) result->status = PMC_STREAM_INVALID;
        return PMC_STREAM_INVALID;
    }

    previous_route = REG32(SSS_CONFIG);
    REG32(SSS_CONFIG) = 0x500u; /* DMA source -> SHA3; no destination DMA */
    REG32(SHA_RESET) = 1u;
    REG32(SHA_RESET) = 0u;
    REG32(SHA_MODE) = 0u; /* SHA3, not legacy Keccak */
    REG32(SHA_AUTO) = 1u; /* engine applies SHA3 final padding */
    REG32(SHA_START) = 1u;
    REG32(DMA_SRC_ISR) = DMA_DONE;
    REG32(DMA_SRC_ADDR) = source;
    REG32(DMA_SRC_MSB) = 0;
    io_fence();
    start = cycle64();
    REG32(DMA_SRC_SIZE) = bytes | 1u; /* LAST_WORD flag observed by loader */

    status = PMC_STREAM_TIMEOUT;
    for (uint32_t poll = 0; poll < POLL_LIMIT; ++poll) {
        uint32_t source_isr = REG32(DMA_SRC_ISR);
        uint32_t sha_status = REG32(SHA_STATUS);
        if ((source_isr & DMA_DONE) && (sha_status & 1u))
            quiescent = 1;
        if ((source_isr & DMA_SRC_ERRORS) != 0) {
            status = PMC_STREAM_SOURCE_ERROR;
            break;
        }
        if (quiescent) {
            status = PMC_STREAM_OK;
            break;
        }
        if (cycle64() - start >= timeout_cycles)
            break;
    }

    uint32_t final_src_isr = REG32(DMA_SRC_ISR);
    uint32_t final_sha_status = REG32(SHA_STATUS);
    uint32_t final_src_addr = REG32(DMA_SRC_ADDR);
    if ((final_src_isr & DMA_DONE) && (final_sha_status & 1u))
        quiescent = 1;
    if (quiescent && status == PMC_STREAM_OK) {
        for (unsigned word = 0; word < 8; ++word) {
            uint32_t value = REG32(SHA_DIGEST + 4u * word);
            for (unsigned byte = 0; byte < 4; ++byte)
                digest[4u * word + byte] = (uint8_t)(value >> (8u * byte));
        }
        REG32(DMA_SRC_ISR) = DMA_DONE;
        io_fence();
    }
    finish_result(result, status, start, quiescent, final_src_isr,
                  0, final_sha_status, final_src_addr, 0);
    restore_route(previous_route, quiescent);
    return status;
}
