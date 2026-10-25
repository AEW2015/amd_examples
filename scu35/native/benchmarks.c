#include "benchmarks.h"
#include <stddef.h>

extern void sha3_256(const uint8_t *input, size_t length, uint8_t output[32]);

#define MMIO32(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define SSS_CONFIG   0x040a0090u
#define DMA_SRC_ADDR 0x040e0000u
#define DMA_SRC_SIZE 0x040e0004u
#define DMA_SRC_ISR  0x040e0014u
#define DMA_SRC_MSB  0x040e0028u
#define DMA_DST_ADDR 0x040e0800u
#define DMA_DST_SIZE 0x040e0804u
#define DMA_DST_ISR  0x040e0814u
#define DMA_DST_MSB  0x040e0828u
#define SHA_RESET    0x04100004u
#define SHA_MODE     0x041000a0u
#define SHA_AUTO     0x041000a4u
#define SHA_START    0x04100000u
#define SHA_STATUS   0x04100008u
#define SHA_DIGEST   0x04100010u
#define INPUT_ADDR   0x04027000u
#define OUTPUT_ADDR  0x0402c000u
#define MAX_BYTES    8192u
#define MAX_REPEATS  1000u
#define POLL_LIMIT   10000000u
#define RESULT_MAGIC 0x42454e43u /* "BENC" */

static void barrier(void)
{
    __asm__ volatile ("fence rw,rw" ::: "memory");
}
static uint32_t ticks(void)
{
    uint32_t value;
    __asm__ volatile("csrr %0,mcycle" : "=r"(value) :: "memory");
    return value;
}

static uint32_t pattern(unsigned i)
{
    uint32_t x = (uint32_t)i * 0x9e3779b9u + 0x6d2b79f5u;
    x ^= x >> 15;
    x *= 0x85ebca6bu;
    return x ^ (x >> 13);
}

static uint32_t checksum_words(volatile uint32_t *p, unsigned count)
{
    uint32_t sum = 0x13579bdfu;
    for (unsigned i = 0; i < count; ++i)
        sum = (sum << 5) | (sum >> 27), sum ^= p[i] + i;
    return sum;
}

/* Matches loader.c:dma_write. The status error fields are masks in the ISR
 * registers, and writing SIZE starts the transfer. */
static unsigned dma_copy_transfer(uint32_t src, uint32_t dst, unsigned bytes,
                                  unsigned *quiescent)
{
    unsigned n;
    *quiescent = 0;
    MMIO32(DMA_SRC_ISR) = 2u;
    MMIO32(DMA_DST_ISR) = 2u;
    MMIO32(DMA_DST_ADDR) = dst;
    MMIO32(DMA_DST_MSB) = 0;
    MMIO32(DMA_DST_SIZE) = bytes;
    MMIO32(DMA_SRC_ADDR) = src;
    MMIO32(DMA_SRC_MSB) = 0;
    barrier();
    MMIO32(DMA_SRC_SIZE) = bytes;
    for (n = 0; n < POLL_LIMIT; ++n) {
        uint32_t si = MMIO32(DMA_SRC_ISR), di = MMIO32(DMA_DST_ISR);
        if ((si & 0x5cu) || (di & 0xdcu)) {
            if ((si & 2u) && (di & 2u)) *quiescent = 1;
            return 2;
        }
        if ((MMIO32(DMA_SRC_ISR) & 2u) && (MMIO32(DMA_DST_ISR) & 2u)) {
            *quiescent = 1;
            if (MMIO32(DMA_SRC_ADDR) != src + bytes ||
                MMIO32(DMA_DST_ADDR) != dst + bytes) return 4;
            MMIO32(DMA_SRC_ISR) = 2u;
            MMIO32(DMA_DST_ISR) = 2u;
            barrier();
            return 0;
        }
    }
    return 3;
}

/* Matches loader.c:sha3_hardware: SHA consumes the DMA source stream only;
 * there is no destination-channel transfer for a SHA operation. */
static unsigned sha3_transfer(uint32_t src, unsigned bytes, uint8_t digest[32],
                              unsigned *quiescent)
{
    unsigned n;
    uint32_t si;
    *quiescent = 0;
    MMIO32(SHA_RESET) = 1u;
    MMIO32(SHA_RESET) = 0u;
    MMIO32(SHA_MODE) = 0u;
    MMIO32(SHA_AUTO) = 1u;
    MMIO32(SHA_START) = 1u;
    MMIO32(DMA_SRC_ISR) = 2u;
    MMIO32(DMA_SRC_ADDR) = src;
    MMIO32(DMA_SRC_MSB) = 0;
    barrier();
    MMIO32(DMA_SRC_SIZE) = bytes | 1u;
    for (n = 0; n < POLL_LIMIT; ++n) {
        si = MMIO32(DMA_SRC_ISR);
        if ((si & 0x5cu) != 0) {
            if ((si & 2u) && (MMIO32(SHA_STATUS) & 1u)) *quiescent = 1;
            return 2;
        }
        if ((si & 2u) && (MMIO32(SHA_STATUS) & 1u)) {
            *quiescent = 1;
            break;
        }
    }
    if (n == POLL_LIMIT) return 3;
    for (unsigned i = 0; i < 8; ++i) {
        uint32_t v = MMIO32(SHA_DIGEST + 4u * i);
        for (unsigned b = 0; b < 4; ++b)
            digest[4u*i+b] = (uint8_t)(v >> (8u*b));
    }
    MMIO32(DMA_SRC_ISR) = 2u;
    barrier();
    return 0;
}

static unsigned valid(unsigned kind, unsigned bytes, unsigned repeats)
{
    if (kind < PMC_BENCH_CPU_ARITH || kind > PMC_BENCH_HW_SHA3 ||
        bytes < 4 || bytes > MAX_BYTES || (bytes & 3u) ||
        repeats == 0 || repeats > MAX_REPEATS)
        return 0;
    if ((kind == PMC_BENCH_SW_SHA3 || kind == PMC_BENCH_HW_SHA3) &&
        bytes > MAX_BYTES) return 0;
    /* Keep software SHA runs bounded on the small PMC core. */
    if (kind == PMC_BENCH_SW_SHA3 && repeats > 20) return 0;
    if (kind == PMC_BENCH_CPU_ARITH && repeats > 20) return 0;
    return 1;
}

unsigned pmc_benchmark(unsigned kind, unsigned bytes, unsigned repeats,
                       uint32_t out[128])
{
    volatile uint32_t *src = (volatile uint32_t *)(uintptr_t)INPUT_ADDR;
    volatile uint32_t *dst = (volatile uint32_t *)(uintptr_t)OUTPUT_ADDR;
    unsigned words = bytes / 4u, errors = 0, rc = 0;
    uint32_t checksum = 0, start, finish, old_sss = 0;
    uint8_t digest[32],expected_digest[32];

    if (!out) return 1;
    for (unsigned i = 0; i < 128; ++i) out[i] = 0;
    if (!valid(kind, bytes, repeats)) return 2;
    for (unsigned i = 0; i < words; ++i) {
        src[i] = pattern(i);
        dst[i] = 0;
    }
    barrier();

    /* CPU arithmetic/branch benchmark has a closed-form expected checksum. */
    if (kind == PMC_BENCH_CPU_ARITH) {
        uint32_t acc = 0x31415926u;
        start = ticks();
        for (unsigned r = 0; r < repeats; ++r) {
            uint32_t x = 0x1234567u + r;
            for (unsigned i = 0; i < bytes * 8u; ++i) {
                x = (x << 5) ^ (x >> 2) ^ (0x9e3779b9u + i);
                if (x & 0x80000000u) x += i ^ 0xa5a5a5a5u;
                else x -= (i * 3u) ^ 0x5a5a5a5au;
            }
            acc ^= (x << (r & 7u)) | (x >> ((32u - (r & 7u)) & 31u));
        }
        finish = ticks();
        checksum = acc;
        /* Repeat once after timing to catch execution/data corruption. */
        {
            uint32_t acc2 = 0x31415926u;
            for (unsigned r = 0; r < repeats; ++r) {
                uint32_t x = 0x1234567u + r;
                for (unsigned i = 0; i < bytes * 8u; ++i) {
                    x = (x << 5) ^ (x >> 2) ^ (0x9e3779b9u + i);
                    if (x & 0x80000000u) x += i ^ 0xa5a5a5a5u;
                    else x -= (i * 3u) ^ 0x5a5a5a5au;
                }
                acc2 ^= (x << (r & 7u)) | (x >> ((32u - (r & 7u)) & 31u));
            }
            if (acc != acc2) ++errors;
        }
    } else if (kind == PMC_BENCH_RAM_COPY) {
        start = ticks();
        for (unsigned r = 0; r < repeats; ++r)
            for (unsigned i = 0; i < words; ++i) dst[i] = src[i];
        barrier();
        finish = ticks();
        for (unsigned i = 0; i < words; ++i)
            if (dst[i] != src[i]) ++errors;
        checksum = checksum_words(dst, words);
    } else if (kind == PMC_BENCH_DMA_COPY) {
        uint32_t sss = MMIO32(SSS_CONFIG);
        unsigned quiescent = 0;
        old_sss = sss;
        /* DMA source -> DMA destination. */
        MMIO32(SSS_CONFIG) = 5u;
        barrier();
        start = ticks();
        for (unsigned r = 0; r < repeats && !rc; ++r)
            rc = dma_copy_transfer(INPUT_ADDR, OUTPUT_ADDR, bytes, &quiescent);
        barrier();
        finish = ticks();
        for (unsigned i = 0; i < words; ++i)
            if (dst[i] != src[i]) ++errors;
        checksum = checksum_words(dst, words);
        if (quiescent) {
            MMIO32(SSS_CONFIG) = old_sss;
            barrier();
        }
    } else if (kind == PMC_BENCH_SW_SHA3) {
        start = ticks();
        for (unsigned r = 0; r < repeats; ++r)
            sha3_256((const uint8_t *)(uintptr_t)INPUT_ADDR, bytes, digest);
        barrier();
        finish = ticks();
        checksum = 0;
        for (unsigned i = 0; i < 32; ++i) checksum = (checksum << 5) ^ (checksum >> 27) ^ digest[i];
    } else { /* hardware SHA3: DMA input, compare against software digest */
        uint32_t sss = MMIO32(SSS_CONFIG);
        unsigned quiescent = 0;
        old_sss = sss;
        sha3_256((const uint8_t *)(uintptr_t)INPUT_ADDR, bytes, expected_digest);
        /* SHA source field = 5; this route has no DMA destination channel. */
        MMIO32(SSS_CONFIG) = 0x500u;
        barrier();
        start = ticks();
        for (unsigned r = 0; r < repeats && !rc; ++r) {
            rc = sha3_transfer(INPUT_ADDR, bytes, digest, &quiescent);
        }
        barrier();
        finish = ticks();
        if (!rc) {
            for (unsigned i = 0; i < 8; ++i) {
                uint32_t hw = MMIO32(SHA_DIGEST + 4u * i);
                uint32_t sw = (uint32_t)expected_digest[4*i] |
                              ((uint32_t)expected_digest[4*i+1] << 8) |
                              ((uint32_t)expected_digest[4*i+2] << 16) |
                              ((uint32_t)expected_digest[4*i+3] << 24);
                out[6+i] = hw;
                if (hw != sw) ++errors;
            }
        }
        if (quiescent) {
            MMIO32(SSS_CONFIG) = old_sss;
            barrier();
        }
        for (unsigned i = 0; i < 32; ++i) checksum = (checksum << 5) ^ (checksum >> 27) ^ digest[i];
    }

    if (rc) ++errors;
    out[0] = RESULT_MAGIC;
    out[1] = finish - start; /* mcycle elapsed ticks, modulo 2^32 */
    out[2] = bytes;
    out[3] = repeats;
    out[4] = checksum;
    out[5] = errors;
    if (kind == PMC_BENCH_SW_SHA3)
        for (unsigned i = 0; i < 8; ++i)
            out[6+i] = (uint32_t)digest[4*i] |
                       ((uint32_t)digest[4*i+1] << 8) |
                       ((uint32_t)digest[4*i+2] << 16) |
                       ((uint32_t)digest[4*i+3] << 24);
    return rc ? rc : (errors ? 5u : 0u);
}
