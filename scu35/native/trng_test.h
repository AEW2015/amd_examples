#ifndef SCU35_PMC_EXPLORATION_TRNG_TEST_H
#define SCU35_PMC_EXPLORATION_TRNG_TEST_H

#include <stdint.h>

#define PMC_TRNG_TEST_WORDS 128u
#define PMC_TRNG_TEST_MAGIC 0x54524e47u /* "TRNG" */
#define PMC_TRNG_TEST_VERSION 1u

enum pmc_trng_test_status {
    PMC_TRNG_TEST_OK = 0u,
    PMC_TRNG_TEST_BAD_ARGUMENT = 1u,
    PMC_TRNG_TEST_PREEXISTING_HEALTH_FLAG = 2u,
    PMC_TRNG_TEST_BUSY_OR_QUEUED = 3u,
    PMC_TRNG_TEST_RESEED_TIMEOUT = 4u,
    PMC_TRNG_TEST_RESEED_HEALTH_FAILURE = 5u,
    PMC_TRNG_TEST_GENERATE_TIMEOUT = 6u,
    PMC_TRNG_TEST_GENERATE_HEALTH_FAILURE = 7u,
    PMC_TRNG_TEST_IDENTICAL_SAMPLES = 8u
};

/* Run one HRNG startup/reseed and collect two consecutive 256-bit samples.
 * This is a bounded diagnostic smoke test, not a statistical entropy test.
 * Caller must ensure the TRNG is unused/exclusive for the call. See
 * docs/trng_driver_protocol.md for preconditions, timing assumptions and the
 * out[] map. The function writes only TRNG registers and volatile output RAM.
 */
unsigned pmc_trng_test(uint32_t out[PMC_TRNG_TEST_WORDS]);

#endif
