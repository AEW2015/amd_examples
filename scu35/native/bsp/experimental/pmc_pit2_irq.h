#ifndef PMC_PIT2_IRQ_H
#define PMC_PIT2_IRQ_H

#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

typedef enum {
    PMC_PIT2_IRQ_OK = 0,
    PMC_PIT2_IRQ_INVALID = 1,
    PMC_PIT2_IRQ_CONTEXT_ACTIVE = 2,
    PMC_PIT2_IRQ_TIMEOUT = 3,
    PMC_PIT2_IRQ_UNEXPECTED = 4,
    PMC_PIT2_IRQ_CLEANUP_FAILED = 5,
    PMC_PIT2_IRQ_BUSY = 6
} pmc_pit2_irq_status_t;

typedef struct {
    pmc_pit2_irq_status_t status;
    uint32_t hits;
    uint32_t mcause;
    uint32_t irq_status;
    uint32_t irq_pending;
    uint32_t final_irq_status;
    uint32_t final_irq_pending;
    uint32_t final_irq_enable;
    uint32_t cleanup_errors;
    uint64_t elapsed_cycles;
} pmc_pit2_irq_result_t;

/* Cleanup mismatch bits in pmc_pit2_irq_result_t.cleanup_errors. */
#define PMC_PIT2_IRQ_CLEANUP_TIMER_STOP   UINT32_C(0x01)
#define PMC_PIT2_IRQ_CLEANUP_IRQ_MASK     UINT32_C(0x02)
#define PMC_PIT2_IRQ_CLEANUP_PENDING_ACK  UINT32_C(0x04)
#define PMC_PIT2_IRQ_CLEANUP_MIE          UINT32_C(0x08)
#define PMC_PIT2_IRQ_CLEANUP_MTVEC        UINT32_C(0x10)
#define PMC_PIT2_IRQ_CLEANUP_MSTATUS      UINT32_C(0x20)

/*
 * Generate one bounded PIT2 interrupt. timer_load is written to the observed
 * PIT2 load register; timeout_cycles bounds the awake mcycle polling loop.
 * The API is experimental and does not use WFI.
 *
 * Caller must exclusively own the IOModule/PIT2 and IRQ10 for the whole call,
 * run on the single PMC hart, and enter with global MIE clear and mie=0. The
 * API rejects an enabled interrupt context without changing it. Since the
 * peripheral has no ownership arbitration, exclusive peripheral ownership
 * cannot be checked in software. The routine leaves PIT2 stopped, IRQ10
 * masked and acknowledged, and restores mtvec/mie/global-MIE context.
 */
pmc_pit2_irq_status_t pmc_pit2_irq_once(uint32_t timer_load,
                                         uint64_t timeout_cycles,
                                         pmc_pit2_irq_result_t *result);

#ifdef __cplusplus
}
#endif

#endif
