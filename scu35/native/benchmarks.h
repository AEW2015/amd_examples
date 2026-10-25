#ifndef SCU35_PMC_BENCHMARKS_H
#define SCU35_PMC_BENCHMARKS_H

#include <stdint.h>

/* Benchmark IDs accepted by pmc_benchmark(). */
#define PMC_BENCH_CPU_ARITH   1u
#define PMC_BENCH_RAM_COPY    2u
#define PMC_BENCH_DMA_COPY    3u
#define PMC_BENCH_SW_SHA3     4u
#define PMC_BENCH_HW_SHA3     5u

/* out[0..13]: magic, elapsed mcycle ticks, bytes, repeats, checksum,
 * error count, then eight little-endian words of SHA3-256 digest.
 * Remaining words are zero. Returns 0 on success, nonzero on error.
 */
unsigned pmc_benchmark(unsigned kind, unsigned bytes, unsigned repeats,
                       uint32_t out[128]);

#endif
