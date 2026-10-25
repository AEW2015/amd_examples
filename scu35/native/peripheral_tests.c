#include <stdint.h>
#include "pmc_bsp.h"
extern uint32_t probe_execute(uint32_t,uint32_t *);
extern void execute_trap(void),probe_trap(void);
static volatile uint32_t *reg(uint32_t a) {return (volatile uint32_t *)a;}
static void clear(uint32_t out[128]) {for(unsigned i=0;i<32;++i) out[i]=0;}

unsigned pmc_wfi_test(uint32_t preload,uint32_t out[128])
{
    clear(out);out[0]=0x57464932;
    uint32_t old[2]={*reg(0x04027000),*reg(0x04027004)},fault=0;
    *reg(0x04040058)=0;*reg(0x04040038)=0;*reg(0x0404003c)=0x10;
    if(preload<100000 || preload>400000) preload=100000;
    out[19]=preload;
    *reg(0x04040050)=preload;
    *reg(0x04040078)=0;*reg(0x04040070)=0xffffffff;
    *reg(0x04040078)=3;
    *reg(0x04040038)=0x10;
    *reg(0x04027000)=0x10500073; /* wfi */
    *reg(0x04027004)=0x00008067;
    __asm__ volatile("csrci mstatus,8; csrw mtvec,%0; csrw mie,%1; fence rw,rw; fence.i"
                     ::"r"(execute_trap),"r"(0x800):"memory");
    uint64_t t=pmc_bsp_time_count();
    uint64_t c=pmc_bsp_cycle_count(),i=pmc_bsp_instret_count();
    out[20]=*reg(0x04040074);
    *reg(0x04040058)=1;
    out[1]=probe_execute(0x04027000,&fault);
    uint64_t delta_c=pmc_bsp_cycle_count()-c,delta_i=pmc_bsp_instret_count()-i;
    out[21]=*reg(0x04040074);out[22]=out[20]-out[21];
    *reg(0x04040078)=0;
    out[2]=fault;out[3]=(uint32_t)delta_c;out[4]=(uint32_t)(delta_c>>32);
    out[5]=(uint32_t)delta_i;out[6]=(uint32_t)(delta_i>>32);
    uint64_t delta_t=pmc_bsp_time_count()-t;
    out[16]=(uint32_t)delta_t;out[17]=(uint32_t)(delta_t>>32);
    out[18]=*reg(0x04040054);
    out[7]=*reg(0x04040030);out[8]=*reg(0x04040034);
    __asm__ volatile("csrr %0,mip; csrr %1,mstatus":"=r"(out[9]),"=r"(out[10]));
    *reg(0x04040058)=0;*reg(0x04040038)=0;*reg(0x0404003c)=0x10;
    *reg(0x04027000)=old[0];*reg(0x04027004)=old[1];
    __asm__ volatile("csrw mie,zero; csrw mtvec,%0; fence rw,rw; fence.i"::"r"(probe_trap):"memory");
    out[11]=*reg(0x04040030);out[12]=*reg(0x04040034);
    return fault || !(out[7]&0x10) || !(out[8]&0x10) || out[12];
}

unsigned pmc_ospi_readid_test(uint32_t out[128])
{
    clear(out);out[0]=0x4f535049;
    uint32_t reset=*reg(0x040a0058),clock=*reg(0x040a0038),wp=*reg(0x040a0020);
    out[2]=reset;out[3]=clock;out[12]=wp;
    if(!(reset&1)||!(clock&0x02000000)) {out[1]=1;return 1;}
    *reg(0x040a0020)=0;*reg(0x040a0058)=reset&~1u;
    pmc_bsp_fence();pmc_bsp_delay_loop(1000);
    uint64_t begin=pmc_bsp_cycle_count();
    unsigned rc=0;
    out[4]=*reg(0x04090000);out[5]=*reg(0x04090004);
    if((*reg(0x040a0058)&1)||!(out[4]&0x80000000u)||(out[5]&0x300)) rc=2;
    if(!rc) {
        /* Direct FCS_B select xx10, /32 baud; no flash mode/write opcode. */
        *reg(0x04090000)=(out[4]&~0x3e00u)|0x800;
        pmc_bsp_fence();out[6]=*reg(0x04090000);
        /* The documented STIG opcode must be staged before EXECUTE. */
        *reg(0x04090090)=0x9fa00000;
        pmc_bsp_fence();out[16]=*reg(0x04090090);
        *reg(0x04090090)=0x9fa00001;
        pmc_bsp_fence();
        while(*reg(0x04090090)&2) {
            out[13]=1;
            if(pmc_bsp_cycle_count()-begin>10000000ull) {rc=3;break;}
        }
        out[7]=*reg(0x04090090);out[8]=*reg(0x040900a0);out[9]=*reg(0x040900a4);
        if(!rc && (!(out[8]&0xffffff)||(out[8]&0xffffff)==0xffffff)) rc=4;
    }
    out[10]=(uint32_t)(pmc_bsp_cycle_count()-begin);
    /* Owned controller: abort the read on timeout and restore entry reset. */
    *reg(0x040a0058)=reset;pmc_bsp_fence();
    out[11]=*reg(0x040a0058);*reg(0x040a0020)=wp;pmc_bsp_fence();
    out[14]=*reg(0x040a0020);out[15]=*reg(0x040a0038);
    if(out[11]!=reset||out[14]!=wp||out[15]!=clock) rc=5;
    out[1]=rc;return rc;
}

unsigned pmc_dma_read_fault_test(uint32_t out[128])
{
    clear(out);out[0]=0x444d4145;
    out[1]=*reg(0x040a0090);
    *reg(0x040a0090)=5;
    *reg(0x040e0014)=2;*reg(0x040e0814)=2;
    *reg(0x040e0800)=0x0402c000;*reg(0x040e0828)=0;*reg(0x040e0804)=16;
    *reg(0x040e0000)=0x04010000;*reg(0x040e0028)=0;
    pmc_bsp_fence();uint64_t begin=pmc_bsp_cycle_count();
    *reg(0x040e0004)=16;
    unsigned rc=1;
    while(pmc_bsp_cycle_count()-begin<10000000ull) {
        if(*reg(0x040e0014)&0x5c) {rc=0;break;}
        if((*reg(0x040e0014)&2)&&(*reg(0x040e0814)&2)) {rc=2;break;}
    }
    out[2]=rc;out[3]=*reg(0x040e0014);out[4]=*reg(0x040e0814);
    out[5]=*reg(0x040e0008);out[6]=*reg(0x040e0808);
    out[7]=*reg(0x040e0000);out[8]=*reg(0x040e0800);
    out[9]=(uint32_t)(pmc_bsp_cycle_count()-begin);
    out[10]=*reg(0x040a0090);
    /* Leave an active/incomplete route intact. The host reloads stock next. */
    return rc;
}
