#ifndef PMC_STREAM_H
#define PMC_STREAM_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PMC_STREAM_SCRATCH_BASE UINT32_C(0x04027000)
#define PMC_STREAM_STAGE_BASE UINT32_C(0x0402c000)
#define PMC_STREAM_WINDOW_SIZE UINT32_C(0x00002000)
#define PMC_STREAM_MAX_BYTES UINT32_C(8192)

typedef enum {
    PMC_STREAM_OK = 0,
    PMC_STREAM_INVALID = 1,
    PMC_STREAM_SOURCE_ERROR = 2,
    PMC_STREAM_DESTINATION_ERROR = 3,
    PMC_STREAM_TIMEOUT = 4,
    PMC_STREAM_PROGRESS_MISMATCH = 5,
    PMC_STREAM_NOT_INITIALIZED = 6
} pmc_stream_status_t;

typedef struct {
    pmc_stream_status_t status;
    uint32_t source_isr;
    uint32_t destination_isr;
    uint32_t engine_status;
    uint32_t source_address;
    uint32_t destination_address;
    uint64_t elapsed_cycles;
    uint8_t quiescent;
} pmc_stream_result_t;

/*
 * Configure the independently observed DMA source/destination controls once.
 * Caller must first ensure both channels are idle and exclusively owned.
 */
pmc_stream_status_t pmc_stream_init(void);

/*
 * Copy non-overlapping ranges in the reserved 8 KiB scratch window at
 * 0x04027000 or staging window at 0x0402c000. Addresses and length must be
 * word aligned; length is 4..8192 bytes. timeout_cycles is relative mcycle.
 * A result is optional.
 */
pmc_stream_status_t pmc_stream_dma_copy(uint32_t source, uint32_t destination,
                                         uint32_t bytes, uint64_t timeout_cycles,
                                         pmc_stream_result_t *result);

/*
 * SHA3-256 a word-aligned PMC RAM range (4..8192 bytes). Digest bytes are
 * returned in standard SHA3 output order. timeout_cycles is relative mcycle.
 */
pmc_stream_status_t pmc_stream_sha3_256(uint32_t source, uint32_t bytes,
                                         uint64_t timeout_cycles,
                                         uint8_t digest[32],
                                         pmc_stream_result_t *result);

#ifdef __cplusplus
}
#endif

#endif
