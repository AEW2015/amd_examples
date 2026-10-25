#include <stdint.h>
#include "pmc_bsp.h"
static volatile uint32_t *reg(uint32_t a) {return (volatile uint32_t *)a;}
static volatile uint32_t base,mask,hits,cause,irq_status,irq_pending,gpi;
static void __attribute__((interrupt("machine"),aligned(4))) handler(void)
{
    __asm__ volatile("csrr %0,mcause":"=r"(cause));
    irq_status=*reg(0x04040030);irq_pending=*reg(0x04040034);
    gpi=*reg(0x04040020);
    *reg(base+8)=0;*reg(0x04040038)=0;*reg(0x0404003c)=mask;
    pmc_bsp_fence();
    __asm__ volatile("csrw mie,zero":::"memory");
    ++hits;
}

unsigned pmc_iomodule_irq_test(uint32_t timer,uint32_t out[128])
{
    for(unsigned n=0;n<32;++n) out[n]=0;
    out[0]=0x494f4d49;out[1]=timer;
    if(timer<1 || timer>4) return 1;
    uint32_t old_vector,old_status,old_mie;
    __asm__ volatile("csrr %0,mtvec; csrr %1,mstatus; csrr %2,mie"
                     :"=r"(old_vector),"=r"(old_status),"=r"(old_mie));
    if((old_status&8)||old_mie) return 2;
    base=0x04040040+16*(timer-1);mask=1u<<(timer+2);
    hits=cause=irq_status=irq_pending=gpi=0;
    out[2]=base;out[3]=mask;out[4]=10000;
    out[5]=*reg(0x04040020);
    /* This monitor image establishes GPO1=2 in its loader. Change only
       its two prescale selectors, keeping security/lockdown bits at zero. */
    *reg(0x04040010)=0;
    for(unsigned i=0;i<4;++i) *reg(0x04040048+16*i)=0;
    *reg(0x04040038)=0;*reg(0x0404003c)=mask;
    *reg(base)=10000;
    __asm__ volatile("csrw mtvec,%0; csrw mie,%1"::"r"(handler),"r"(0x800):"memory");
    *reg(0x04040038)=mask;
    __asm__ volatile("csrsi mstatus,8":::"memory");
    uint64_t begin=pmc_bsp_cycle_count();
    *reg(base+8)=1;pmc_bsp_fence();
    while(!hits && pmc_bsp_cycle_count()-begin<10000000ull) {}
    uint64_t elapsed=pmc_bsp_cycle_count()-begin;
    __asm__ volatile("csrci mstatus,8; csrw mie,zero":::"memory");
    *reg(base+8)=0;*reg(0x04040038)=0;*reg(0x0404003c)=mask;
    *reg(0x04040010)=2;pmc_bsp_fence();
    out[6]=hits;out[7]=cause;out[8]=irq_status;out[9]=irq_pending;
    out[10]=gpi;out[11]=*reg(0x04040020);
    out[12]=*reg(0x04040030);out[13]=*reg(0x04040034);
    out[14]=*reg(base+4);out[15]=(uint32_t)elapsed;out[16]=(uint32_t)(elapsed>>32);
    __asm__ volatile("csrw mtvec,%0; csrw mie,%1; csrw mstatus,%2"
                     ::"r"(old_vector),"r"(old_mie),"r"(old_status):"memory");
    __asm__ volatile("csrr %0,mtvec; csrr %1,mie; csrr %2,mstatus"
                     :"=r"(out[17]),"=r"(out[18]),"=r"(out[19]));
    out[20]=old_vector;out[21]=old_mie;out[22]=old_status;
    return hits!=1 || cause!=0x8000000b || !(irq_pending&mask) ||
           (out[13]&mask) || out[17]!=old_vector || out[18]!=old_mie || out[19]!=old_status;
}
