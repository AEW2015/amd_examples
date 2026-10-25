#include "pmc_pit2_irq.h"

#include <stddef.h>
#include "pmc_bsp.h"

#define PIT2_LOAD       UINT32_C(0x04040050)
#define PIT2_CONTROL    UINT32_C(0x04040058)
#define IRQ_STATUS      UINT32_C(0x04040030)
#define IRQ_PENDING     UINT32_C(0x04040034)
#define IRQ_ENABLE      UINT32_C(0x04040038)
#define IRQ_ACK         UINT32_C(0x0404003c)
#define IRQ10_MASK      UINT32_C(0x00000010)
#define MSTATUS_MIE     UINT32_C(0x00000008)
#define MCAUSE_MACHINE_EXTERNAL UINT32_C(0x8000000b)
static volatile uint32_t irq_busy;
static volatile uint32_t irq_hits;
static volatile uint32_t irq_cause;
static volatile uint32_t irq_status;
static volatile uint32_t irq_pending;

static uint32_t csr_mstatus(void)
{
    uint32_t value;
    __asm__ volatile("csrr %0,mstatus" : "=r"(value) :: "memory");
    return value;
}

static uint32_t csr_mie(void)
{
    uint32_t value;
    __asm__ volatile("csrr %0,mie" : "=r"(value) :: "memory");
    return value;
}

static uint32_t csr_mtvec(void)
{
    uint32_t value;
    __asm__ volatile("csrr %0,mtvec" : "=r"(value) :: "memory");
    return value;
}

static uint64_t read_mcycle(void)
{
    return pmc_bsp_cycle_count();
}

static void __attribute__((interrupt("machine"), aligned(4))) pit2_irq_handler(void)
{
    __asm__ volatile("csrr %0,mcause" : "=r"(irq_cause) :: "memory");
    irq_status = pmc_bsp_mmio_read32(IRQ_STATUS);
    irq_pending = pmc_bsp_mmio_read32(IRQ_PENDING);

    /* Follow the proven one-shot sequence: stop PIT2, mask IRQs, ACK IRQ10. */
    pmc_bsp_mmio_write32(PIT2_CONTROL, 0);
    pmc_bsp_mmio_write32(IRQ_ENABLE, 0);
    pmc_bsp_mmio_write32(IRQ_ACK, IRQ10_MASK);
    pmc_bsp_fence();
    __asm__ volatile("csrw mie,zero" ::: "memory");
    ++irq_hits;
}

static void store_result(pmc_pit2_irq_result_t *out,
                         pmc_pit2_irq_status_t status,
                         uint64_t elapsed,
                         uint32_t cleanup_errors)
{
    if (out == NULL) return;
    out->status = status;
    out->hits = irq_hits;
    out->mcause = irq_cause;
    out->irq_status = irq_status;
    out->irq_pending = irq_pending;
    out->final_irq_status = pmc_bsp_mmio_read32(IRQ_STATUS);
    out->final_irq_pending = pmc_bsp_mmio_read32(IRQ_PENDING);
    out->final_irq_enable = pmc_bsp_mmio_read32(IRQ_ENABLE);
    out->cleanup_errors = cleanup_errors;
    out->elapsed_cycles = elapsed;
}

pmc_pit2_irq_status_t pmc_pit2_irq_once(uint32_t timer_load,
                                         uint64_t timeout_cycles,
                                         pmc_pit2_irq_result_t *result)
{
    uint32_t saved_mtvec, saved_mie, saved_mstatus;
    uint64_t begin, elapsed = 0;
    uint32_t cleanup_errors = 0;
    pmc_pit2_irq_status_t status = PMC_PIT2_IRQ_OK;

    if (result != NULL) {
        result->status = PMC_PIT2_IRQ_INVALID;
        result->hits = 0;
        result->mcause = 0;
        result->irq_status = 0;
        result->irq_pending = 0;
        result->final_irq_status = 0;
        result->final_irq_pending = 0;
        result->final_irq_enable = 0;
        result->cleanup_errors = 0;
        result->elapsed_cycles = 0;
    }
    if (timer_load == 0 || timeout_cycles == 0) return PMC_PIT2_IRQ_INVALID;
    if (irq_busy != 0) {
        if (result != NULL) result->status = PMC_PIT2_IRQ_BUSY;
        return PMC_PIT2_IRQ_BUSY;
    }

    /* Do not disturb an active machine-interrupt context. */
    saved_mstatus = csr_mstatus();
    saved_mie = csr_mie();
    if ((saved_mstatus & MSTATUS_MIE) != 0 || saved_mie != 0) {
        if (result != NULL) result->status = PMC_PIT2_IRQ_CONTEXT_ACTIVE;
        return PMC_PIT2_IRQ_CONTEXT_ACTIVE;
    }

    irq_busy = 1;
    saved_mtvec = csr_mtvec();
    irq_hits = 0;
    irq_cause = 0;
    irq_status = 0;
    irq_pending = 0;

    /* Stop/clear this owned source before arming the one-shot. */
    pmc_bsp_mmio_write32(PIT2_CONTROL, 0);
    pmc_bsp_mmio_write32(IRQ_ENABLE, 0);
    pmc_bsp_mmio_write32(IRQ_ACK, IRQ10_MASK);
    pmc_bsp_mmio_write32(PIT2_LOAD, timer_load);
    pmc_bsp_fence();

    __asm__ volatile("csrw mtvec,%0; csrw mie,%1"
                     :: "r"((uintptr_t)pit2_irq_handler), "r"(UINT32_C(0x800)) : "memory");
    pmc_bsp_mmio_write32(IRQ_ENABLE, IRQ10_MASK);
    __asm__ volatile("csrsi mstatus,8" ::: "memory");
    begin = read_mcycle();
    pmc_bsp_mmio_write32(PIT2_CONTROL, 1);
    pmc_bsp_fence();

    while (irq_hits == 0 && (read_mcycle() - begin) < timeout_cycles) {
        /* Bounded awake polling; WFI would make mcycle-timeout progress unclear. */
    }
    elapsed = read_mcycle() - begin;

    /* Disable machine interrupts before deterministic source cleanup. */
    __asm__ volatile("csrci mstatus,8; csrw mie,zero" ::: "memory");
    pmc_bsp_mmio_write32(PIT2_CONTROL, 0);
    pmc_bsp_mmio_write32(IRQ_ENABLE, 0);
    pmc_bsp_mmio_write32(IRQ_ACK, IRQ10_MASK);
    pmc_bsp_fence();

    if (irq_hits == 0) status = PMC_PIT2_IRQ_TIMEOUT;
    else if (irq_hits != 1 || irq_cause != MCAUSE_MACHINE_EXTERNAL ||
             (irq_pending & IRQ10_MASK) == 0)
        status = PMC_PIT2_IRQ_UNEXPECTED;

    /* Restore the original trap vector and disabled interrupt state. */
    __asm__ volatile("csrw mtvec,%0; csrw mie,%1; csrw mstatus,%2; fence iorw,iorw"
                     :: "r"(saved_mtvec), "r"(saved_mie), "r"(saved_mstatus) : "memory");
    if (csr_mtvec() != saved_mtvec)
        cleanup_errors |= PMC_PIT2_IRQ_CLEANUP_MTVEC;
    if (csr_mie() != saved_mie) cleanup_errors |= PMC_PIT2_IRQ_CLEANUP_MIE;
    if (csr_mstatus() != saved_mstatus)
        cleanup_errors |= PMC_PIT2_IRQ_CLEANUP_MSTATUS;

    if (pmc_bsp_mmio_read32(PIT2_CONTROL) != 0)
        cleanup_errors |= PMC_PIT2_IRQ_CLEANUP_TIMER_STOP;
    if (pmc_bsp_mmio_read32(IRQ_ENABLE) != 0)
        cleanup_errors |= PMC_PIT2_IRQ_CLEANUP_IRQ_MASK;
    if ((pmc_bsp_mmio_read32(IRQ_PENDING) & IRQ10_MASK) != 0)
        cleanup_errors |= PMC_PIT2_IRQ_CLEANUP_PENDING_ACK;
    if (cleanup_errors != 0) status = PMC_PIT2_IRQ_CLEANUP_FAILED;

    store_result(result, status, elapsed, cleanup_errors);
    irq_busy = 0;
    return status;
}
