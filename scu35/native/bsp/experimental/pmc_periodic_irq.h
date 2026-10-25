#ifndef PMC_PERIODIC_IRQ_H
#define PMC_PERIODIC_IRQ_H
#include <stdint.h>

enum pmc_periodic_status {
 PMC_PERIODIC_OK=0, PMC_PERIODIC_INVALID=1, PMC_PERIODIC_CONTEXT_ACTIVE=2,
 PMC_PERIODIC_SOURCE_BUSY=3, PMC_PERIODIC_WATCHDOG=4,
 PMC_PERIODIC_UNEXPECTED_IRQ=5, PMC_PERIODIC_CLEANUP_FAILED=6
};
typedef struct {
 uint32_t status, events, dispatched, coalesced, wfi_returns;
 uint32_t last_cause, last_pending, first_reference, last_reference;
 uint32_t task_every_two, task_every_five, dispatch_checksum;
 uint32_t final_pending, final_enable, cleanup_errors;
 uint64_t cycle_delta, instret_delta;
 uint32_t reference_delta, saved_mtvec, restored_mtvec;
 uint32_t saved_mstatus, restored_mstatus, saved_mie, restored_mie;
} pmc_periodic_result_t;

/* Experimental single-hart scheduler demonstration. Exclusively owns PIT2
 * (periodic source), PIT3 (independent deadline interrupt), PIT4 (time reference)
 * and the IOModule interrupt controller. Enter with global MIE clear and mie=0,
 * all timers stopped and no pending PIT interrupt. Callback work is represented
 * by deterministic foreground dispatch at periods 2 and 5; the ISR only records
 * ticks. No other ISR, thread or peripheral owner may use these resources.
 *
 * load must be 100000..400000 and events 1..64. wait_wfi=0 uses awake polling;
 * wait_wfi=1 waits with global MIE disabled, then dispatches pending interrupts.
 * PIT3 bounds a missing PIT2 event if interrupt delivery itself works. External
 * host reset is still required if the CPU/interrupt fabric stops responding.
 * Ownership/stopped-state preconditions are caller-enforced. IRQ_ENABLE
 * returned zero even after an enable write in the guard experiment; control
 * readback has not been established. A nonzero read is advisory rejection only.
 * A synchronous fault in this service is fail-stop and does not return; normal
 * cleanup applies to returned timer results, with host reset as fault recovery.
 * Returns with timers stopped, own sources masked/acknowledged, original
 * preloads and machine interrupt context restored. Six success cases passed;
 * guard/watchdog qualification is recorded separately in the campaign guide.
 */
uint32_t pmc_periodic_irq_run(uint32_t load, uint32_t events, uint32_t wait_wfi,
                            pmc_periodic_result_t *result);
#endif
