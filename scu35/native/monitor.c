#include <stdint.h>
#include "benchmarks.h"
#include "pmc_bsp.h"
struct monitor_control {
 uint32_t magic,phase,request,completed,op,address,count,faults;
 uint32_t mcause,mepc,mtval,mstatus,hartid,reserved[3];
 uint32_t data[128],fault_mask[4];
};
volatile struct monitor_control control __attribute__((section(".control"),aligned(4)));
extern void probe_trap(void);
extern unsigned pmc_aes_test(uint32_t *);
extern unsigned fast_benchmark(unsigned,unsigned,unsigned,unsigned,unsigned,uint32_t *);
extern unsigned pq_benchmark(unsigned,unsigned,unsigned,uint32_t *);
extern unsigned pq_hash_test(unsigned,uint32_t *);
static volatile uint32_t *reg(uint32_t a){return (volatile uint32_t *)(uintptr_t)a;}
static uint64_t cycle64(void){return pmc_bsp_cycle_count();}
static void measure_clock(unsigned events)
{
    /* The PL publishes reference-low/high and CFGCLK before sequence.
       Sample immediately after each commit, away from its next update. */
    uint32_t seen=*reg(0x04029500),first_sequence=0,latest=seen;
    uint64_t start_limit=cycle64(),first_cycles=0,first_ref=0,last_ref=0;
    uint64_t first_time=0,last_time=0;
    uint32_t pit4_start=0,pit4_end=0;
    uint32_t first_cfg=0,last_cfg=0,samples=0;
    control.data[0]=0x434c4f4b;
    if(!events||events>100) {control.faults=0xffffffff;return;}
    for(;;) {
        uint32_t sequence=*reg(0x04029500);
        if(sequence!=seen) {
            uint64_t cycles=cycle64();
            uint32_t low=*reg(0x04029504),high=*reg(0x04029508);
            uint32_t cfg=*reg(0x04029510);
            __asm__ volatile("fence rw,rw" ::: "memory");
            if(*reg(0x04029500)!=sequence) continue;
            uint64_t reference=((uint64_t)high<<32)|low;
            seen=sequence;latest=sequence;++samples;
            if(!first_sequence) {
                first_sequence=sequence;first_cycles=cycles;
                first_ref=reference;first_cfg=cfg;
                /* PIT4 is an independent down-counter observation over the
                   same FPGA-reference interval as mcycle/time. No IRQ. */
                *reg(0x04040078)=0;
                *reg(0x04040070)=0xffffffffu;
                __asm__ volatile("fence iorw,iorw" ::: "memory");
                *reg(0x04040078)=3;
                __asm__ volatile("fence iorw,iorw" ::: "memory");
                first_time=pmc_bsp_time_count();
                pit4_start=*reg(0x04040074);
            } else if(sequence-first_sequence>=events) {
                last_ref=reference;last_cfg=cfg;
                uint64_t delta_cycles=cycles-first_cycles,delta_ref=last_ref-first_ref;
                last_time=pmc_bsp_time_count();
                pit4_end=*reg(0x04040074);
                *reg(0x04040078)=0;
                __asm__ volatile("fence iorw,iorw" ::: "memory");
                control.data[1]=(uint32_t)delta_cycles;
                control.data[2]=(uint32_t)(delta_cycles>>32);
                control.data[3]=(uint32_t)delta_ref;
                control.data[4]=(uint32_t)(delta_ref>>32);
                control.data[5]=last_cfg-first_cfg;
                control.data[6]=first_sequence;control.data[7]=latest;
                control.data[8]=samples;
                control.data[9]=*reg(0x040a0030);
                control.data[10]=*reg(0x040a0034);
                control.data[11]=*reg(0x04040044);
                uint64_t delta_time=last_time-first_time;
                control.data[12]=(uint32_t)delta_time;
                control.data[13]=(uint32_t)(delta_time>>32);
                control.data[14]=pit4_start-pit4_end;
                control.data[15]=pit4_end;
                return;
            }
        }
        if(cycle64()-start_limit>2000000000ull) {
            *reg(0x04040078)=0;
            __asm__ volatile("fence iorw,iorw" ::: "memory");
            control.faults=0xfffffffe;
            control.data[1]=seen;control.data[2]=latest;
            return;
        }
    }
}

void post_configuration_monitor(void){
 extern volatile uint32_t configured_chunks,configured_commands,configured_words;
 for(unsigned i=0;i<sizeof(control)/4;++i)((volatile uint32_t *)&control)[i]=0;
 control.reserved[0]=configured_chunks;control.reserved[1]=configured_commands;control.reserved[2]=configured_words;
 __asm__ volatile("csrci mstatus,8; csrw mie,zero; csrw mtvec,%0"::"r"(probe_trap):"memory");
 control.magic=0x504d434d;
 __asm__ volatile("csrr %0,mstatus; csrr %1,mhartid":"=r"(control.mstatus),"=r"(control.hartid));
 __asm__ volatile("fence rw,rw":::"memory");control.phase=2;
 for(;;){
  uint32_t request=control.request;if(request==control.completed)continue;
  __asm__ volatile("fence rw,rw":::"memory");
  unsigned count=control.count,reps=control.data[0],lo=control.data[1],hi=control.data[2];
  control.faults=0;for(unsigned i=0;i<4;++i)control.fault_mask[i]=0;
  if(control.op==5)control.faults=pmc_benchmark(control.address,count,reps,(uint32_t *)control.data);
  else if(control.op==6)measure_clock(count);
  else if(control.op==9)control.faults=pmc_aes_test((uint32_t *)control.data);
  else if(control.op==30)control.faults=fast_benchmark(control.address,count,reps,lo,hi,(uint32_t *)control.data);
  else if(control.op==31)control.faults=pq_benchmark(control.address,count,reps,(uint32_t *)control.data);
  else if(control.op==32)control.faults=pq_hash_test(count,(uint32_t *)control.data);
  else control.faults=0xffffffff;
  __asm__ volatile("fence rw,rw":::"memory");control.completed=request;
 }
}
