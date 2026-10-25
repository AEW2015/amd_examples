#include <stdint.h>
#include "pmc_pit2_irq.h"

unsigned pmc_pit2_api_test(uint32_t kind,uint32_t out[128])
{
    for(unsigned n=0;n<32;++n) out[n]=0;
    out[0]=0x50495251;out[1]=kind;
    uint32_t vector,mie,status;
    __asm__ volatile("csrr %0,mtvec; csrr %1,mie; csrr %2,mstatus"
                     :"=r"(vector),"=r"(mie),"=r"(status));
    out[16]=vector;out[17]=mie;out[18]=status;
    pmc_pit2_irq_result_t report;
    pmc_pit2_irq_status_t rc;
    uint32_t expected=PMC_PIT2_IRQ_OK;
    if(kind==0) rc=pmc_pit2_irq_once(10000,10000000,&report);
    else if(kind==1) {
        expected=PMC_PIT2_IRQ_TIMEOUT;
        rc=pmc_pit2_irq_once(1000000,1000,&report);
    } else if(kind==2) {
        expected=PMC_PIT2_IRQ_CONTEXT_ACTIVE;
        __asm__ volatile("csrw mie,%0"::"r"(0x800):"memory");
        rc=pmc_pit2_irq_once(10000,10000000,&report);
        __asm__ volatile("csrr %0,mie; csrw mie,%1":"=r"(out[22]):"r"(mie):"memory");
    } else if(kind==3) {
        expected=PMC_PIT2_IRQ_INVALID;
        rc=pmc_pit2_irq_once(0,10000000,&report);
    } else if(kind==4) {
        expected=PMC_PIT2_IRQ_INVALID;
        rc=pmc_pit2_irq_once(10000,0,&report);
    } else return 1;
    out[2]=rc;out[3]=expected;out[4]=report.status;
    out[5]=report.hits;out[6]=report.mcause;out[7]=report.irq_status;
    out[8]=report.irq_pending;out[9]=report.final_irq_status;
    out[10]=report.final_irq_pending;out[11]=report.final_irq_enable;
    out[12]=report.cleanup_errors;
    out[13]=(uint32_t)report.elapsed_cycles;
    out[14]=(uint32_t)(report.elapsed_cycles>>32);
    __asm__ volatile("csrr %0,mtvec; csrr %1,mie; csrr %2,mstatus"
                     :"=r"(out[19]),"=r"(out[20]),"=r"(out[21]));
    return rc!=expected || report.status!=expected || report.cleanup_errors ||
           out[19]!=vector || out[20]!=mie || out[21]!=status ||
           (kind==2 && out[22]!=0x800);
}
