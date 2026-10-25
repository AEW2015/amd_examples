#include <stdint.h>
#include "pmc_bsp.h"
#include "pmc_pit2_irq.h"

int main(void)
{
    pmc_pit2_irq_result_t result;
    pmc_bsp_mailbox_clear();
    pmc_bsp_mailbox_publish(0x49525132, 0, "PIT2 IRQ candidate pending HW");

    /* Test only on the independent PMC image with exclusive PIT2/IRQ10 ownership. */
    pmc_pit2_irq_status_t status = pmc_pit2_irq_once(UINT32_C(10000),
                                                       UINT64_C(10000000),
                                                       &result);
    pmc_bsp_mailbox_publish((uint32_t)status, result.hits,
                            status == PMC_PIT2_IRQ_OK ? "PIT2 one-shot passed" :
                            "PIT2 candidate requires review");
    return status == PMC_PIT2_IRQ_OK ? 0 : 1;
}
