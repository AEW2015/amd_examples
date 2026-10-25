#ifndef PMC_BSP_H
#define PMC_BSP_H

#include <stddef.h>
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

#define PMC_BSP_RAM_BASE          UINT32_C(0x04020000)
#define PMC_BSP_RAM_APERTURE_SIZE UINT32_C(0x00010000)
#define PMC_BSP_MAILBOX_ADDRESS   UINT32_C(0x04029000)
#define PMC_BSP_MAILBOX_MAGIC     UINT32_C(0x48454c4f) /* "HELO" */
#define PMC_BSP_MAILBOX_MESSAGE_SIZE 32u

typedef struct {
    uint32_t magic;
    uint32_t status;
    uint32_t visits;
    uint32_t mcause;
    uint32_t mepc;
    uint32_t mtval;
    char message[PMC_BSP_MAILBOX_MESSAGE_SIZE];
} pmc_bsp_mailbox_t;

/* This object occupies the documented 56-byte shared mailbox at 0x04029000. */
extern volatile pmc_bsp_mailbox_t pmc_bsp_mailbox;

typedef enum {
    PMC_BSP_CLOCK_PMC = 0,
    PMC_BSP_CLOCK_CCU = 1
} pmc_bsp_clock_t;

/* Initialization is intentionally passive: it does not change clocking or MMIO. */
void pmc_bsp_init(void);

/* Ordered 32-bit MMIO access. The address must be aligned and mapped. */
uint32_t pmc_bsp_mmio_read32(uintptr_t address);
void pmc_bsp_mmio_write32(uintptr_t address, uint32_t value);
void pmc_bsp_fence(void);

/* Coherent RV32 reads of the 64-bit machine counters and timer. */
uint64_t pmc_bsp_cycle_count(void);
uint64_t pmc_bsp_instret_count(void);
uint64_t pmc_bsp_time_count(void);
uint32_t pmc_bsp_misa(void);
uint32_t pmc_bsp_mcountinhibit(void);

/* Publish a HELLO mailbox record. Message is truncated to 31 chars and NUL-terminated. */
void pmc_bsp_mailbox_publish(uint32_t status, uint32_t visits, const char *message);
void pmc_bsp_mailbox_clear(void);

/*
 * UART RPC mailbox shared with the matching FPGA UART bridge at 0x04029600.
 * This is not a native PMC UART driver. Init clears seven words; receive
 * returns 1 when RX sequence differs from DONE sequence, else 0. Reply stores
 * the response and service timing before committing DONE sequence.
 */
void pmc_bsp_uart_mailbox_init(void);
int pmc_bsp_uart_mailbox_receive(uint32_t *sequence, uint8_t *byte);
void pmc_bsp_uart_mailbox_reply(uint32_t sequence, uint8_t byte);

/* Bounded loop delay. The argument is iterations, not calibrated time. */
void pmc_bsp_delay_loop(uint32_t iterations);

/* Read-only clock control access: PMC=0x040a0030, CCU=0x040a0034. */
uint32_t pmc_bsp_clock_register_read(pmc_bsp_clock_t clock);
uint32_t pmc_bsp_clock_divider_get(pmc_bsp_clock_t clock);

#ifdef __cplusplus
}
#endif

#endif
