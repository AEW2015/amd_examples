#include "pmc_bsp.h"

/* A one-shot greeting; our independent loader runs after this returns.
   visits is a startup invocation count, not a continuing heartbeat. */
void pmc_hello(void)
{
    pmc_bsp_init();
    pmc_bsp_mailbox_publish(1,1,"Hello from SCU35 PMC!");
}
