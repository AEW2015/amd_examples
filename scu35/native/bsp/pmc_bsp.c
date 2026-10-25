#include "pmc_bsp.h"

#define PMC_BSP_PMC_CLOCK_REG UINT32_C(0x040a0030)
#define PMC_BSP_CCU_CLOCK_REG UINT32_C(0x040a0034)
#define PMC_BSP_CLOCK_DIV_MASK UINT32_C(0x00000f00)
#define PMC_BSP_CLOCK_DIV_SHIFT 8u
#define PMC_BSP_UART_RPC_BASE UINT32_C(0x04029600)

volatile pmc_bsp_mailbox_t pmc_bsp_mailbox
    __attribute__((section(".mailbox"), aligned(4)));
_Static_assert(sizeof(pmc_bsp_mailbox_t) == 56, "PMC mailbox ABI must be 56 bytes");

void pmc_bsp_fence(void)
{
    __asm__ volatile ("fence iorw, iorw" ::: "memory");
}

void pmc_bsp_init(void)
{
    pmc_bsp_fence();
}

uint32_t pmc_bsp_mmio_read32(uintptr_t address)
{
    uint32_t value;
    pmc_bsp_fence();
    value = *(volatile const uint32_t *)address;
    pmc_bsp_fence();
    return value;
}

void pmc_bsp_mmio_write32(uintptr_t address, uint32_t value)
{
    pmc_bsp_fence();
    *(volatile uint32_t *)address = value;
    pmc_bsp_fence();
}

uint64_t pmc_bsp_cycle_count(void)
{
    uint32_t hi_before, lo, hi_after;
    do {
        __asm__ volatile ("csrr %0, mcycleh" : "=r"(hi_before) :: "memory");
        __asm__ volatile ("csrr %0, mcycle" : "=r"(lo) :: "memory");
        __asm__ volatile ("csrr %0, mcycleh" : "=r"(hi_after) :: "memory");
    } while (hi_before != hi_after);
    return ((uint64_t)hi_before << 32) | lo;
}

uint64_t pmc_bsp_instret_count(void)
{
    uint32_t hi_before, lo, hi_after;
    do {
        __asm__ volatile ("csrr %0, minstreth" : "=r"(hi_before) :: "memory");
        __asm__ volatile ("csrr %0, minstret" : "=r"(lo) :: "memory");
        __asm__ volatile ("csrr %0, minstreth" : "=r"(hi_after) :: "memory");
    } while (hi_before != hi_after);
    return ((uint64_t)hi_before << 32) | lo;
}

uint64_t pmc_bsp_time_count(void)
{
    uint32_t hi_before, lo, hi_after;
    do {
        __asm__ volatile ("csrr %0, timeh" : "=r"(hi_before) :: "memory");
        __asm__ volatile ("csrr %0, time" : "=r"(lo) :: "memory");
        __asm__ volatile ("csrr %0, timeh" : "=r"(hi_after) :: "memory");
    } while (hi_before != hi_after);
    return ((uint64_t)hi_before << 32) | lo;
}

uint32_t pmc_bsp_misa(void)
{
    uint32_t value;
    __asm__ volatile ("csrr %0, misa" : "=r"(value) :: "memory");
    return value;
}

uint32_t pmc_bsp_mcountinhibit(void)
{
    uint32_t value;
    __asm__ volatile ("csrr %0, mcountinhibit" : "=r"(value) :: "memory");
    return value;
}

void pmc_bsp_mailbox_clear(void)
{
    pmc_bsp_mailbox.magic = 0;
    pmc_bsp_mailbox.status = 0;
    pmc_bsp_mailbox.visits = 0;
    pmc_bsp_mailbox.mcause = 0;
    pmc_bsp_mailbox.mepc = 0;
    pmc_bsp_mailbox.mtval = 0;
    for (size_t i = 0; i < PMC_BSP_MAILBOX_MESSAGE_SIZE; ++i)
        pmc_bsp_mailbox.message[i] = '\0';
    pmc_bsp_fence();
}

void pmc_bsp_mailbox_publish(uint32_t status, uint32_t visits, const char *message)
{
    pmc_bsp_mailbox.magic = 0;
    pmc_bsp_mailbox.status = 0;
    pmc_bsp_mailbox.visits = visits;
    pmc_bsp_mailbox.mcause = 0;
    pmc_bsp_mailbox.mepc = 0;
    pmc_bsp_mailbox.mtval = 0;
    for (size_t i = 0; i < PMC_BSP_MAILBOX_MESSAGE_SIZE; ++i)
        pmc_bsp_mailbox.message[i] = '\0';
    if (message != NULL) {
        size_t i = 0;
        while (i + 1 < PMC_BSP_MAILBOX_MESSAGE_SIZE && message[i] != '\0') {
            pmc_bsp_mailbox.message[i] = message[i];
            ++i;
        }
    }
    pmc_bsp_fence();
    pmc_bsp_mailbox.magic = PMC_BSP_MAILBOX_MAGIC;
    pmc_bsp_fence();
    pmc_bsp_mailbox.status = status;
    pmc_bsp_fence();
}

void pmc_bsp_uart_mailbox_init(void)
{
    volatile uint32_t *rpc = (volatile uint32_t *)(uintptr_t)PMC_BSP_UART_RPC_BASE;
    for (uint32_t i = 0; i < 7; ++i)
        rpc[i] = 0;
    pmc_bsp_fence();
}

int pmc_bsp_uart_mailbox_receive(uint32_t *sequence, uint8_t *byte)
{
    volatile uint32_t *rpc = (volatile uint32_t *)(uintptr_t)PMC_BSP_UART_RPC_BASE;
    uint32_t request = rpc[0];
    uint32_t completed = rpc[3];
    if (request == completed)
        return 0;
    pmc_bsp_fence();
    uint8_t value = (uint8_t)rpc[1];
    if (sequence != NULL)
        *sequence = request;
    if (byte != NULL)
        *byte = value;
    return 1;
}

void pmc_bsp_uart_mailbox_reply(uint32_t sequence, uint8_t byte)
{
    volatile uint32_t *rpc = (volatile uint32_t *)(uintptr_t)PMC_BSP_UART_RPC_BASE;
    rpc[2] = byte;
    rpc[4] = rpc[4] + 1u;
    uint64_t cycles = pmc_bsp_cycle_count();
    rpc[5] = (uint32_t)cycles;
    rpc[6] = (uint32_t)(cycles >> 32);
    pmc_bsp_fence();
    rpc[3] = sequence;
    pmc_bsp_fence();
}

void pmc_bsp_delay_loop(uint32_t iterations)
{
    if (iterations == 0)
        return;
    __asm__ volatile (
        "1: addi %0, %0, -1\n"
        "   bnez %0, 1b"
        : "+r"(iterations)
        :
        : "memory");
}

uint32_t pmc_bsp_clock_register_read(pmc_bsp_clock_t clock)
{
    uintptr_t address;
    switch (clock) {
    case PMC_BSP_CLOCK_PMC:
        address = PMC_BSP_PMC_CLOCK_REG;
        break;
    case PMC_BSP_CLOCK_CCU:
        address = PMC_BSP_CCU_CLOCK_REG;
        break;
    default:
        return 0;
    }
    return pmc_bsp_mmio_read32(address);
}

uint32_t pmc_bsp_clock_divider_get(pmc_bsp_clock_t clock)
{
    return (pmc_bsp_clock_register_read(clock) & PMC_BSP_CLOCK_DIV_MASK) >> PMC_BSP_CLOCK_DIV_SHIFT;
}
