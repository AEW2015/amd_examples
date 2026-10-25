#include "pmc_periodic_irq.h"
#include "pmc_bsp.h"

#define REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define IRQ_PENDING 0x04040034u
#define IRQ_STATUS 0x04040030u
#define IRQ_ENABLE 0x04040038u
#define IRQ_ACK 0x0404003cu
#define PIT2 0x04040050u
#define PIT3 0x04040060u
#define PIT4 0x04040070u
#define SOURCES 0x30u
#define ALL_PIT 0x78u
static volatile uint32_t busy,hits,target,done,reason,cause,pending;
static volatile uint32_t first_ref,last_ref;
static uint32_t csr_status(void) {uint32_t x; __asm__ volatile("csrr %0,mstatus":"=r"(x));return x;}
static uint32_t csr_ie(void) {uint32_t x; __asm__ volatile("csrr %0,mie":"=r"(x));return x;}
static uint32_t csr_vector(void) {uint32_t x; __asm__ volatile("csrr %0,mtvec":"=r"(x));return x;}
static void fence_io(void) {__asm__ volatile("fence iorw,iorw":::"memory");}

static void __attribute__((interrupt("machine"),aligned(4))) periodic_handler(void)
{
 __asm__ volatile("csrr %0,mcause":"=r"(cause)::"memory");
 if (!(cause&0x80000000u)) {
  /* Fault reporting must not perform further MMIO after a bus fault. */
  reason=PMC_PERIODIC_UNEXPECTED_IRQ; done=1;
  for (;;) {}
 }
 pending=REG(IRQ_PENDING);
 if (cause!=0x8000000bu || (pending&SOURCES)==0 || (pending&~SOURCES)!=0) {
  reason=PMC_PERIODIC_UNEXPECTED_IRQ; done=1;
 } else {
  if (pending&0x10u) {
   uint32_t ref=REG(PIT4+4);
   if (!hits) first_ref=ref;
   last_ref=ref; ++hits;
  }
  if (hits>=target) done=1;
  else if (pending&0x20u) {reason=PMC_PERIODIC_WATCHDOG;done=1;}
 }
 if (done) {REG(PIT2+8)=0;REG(PIT3+8)=0;REG(IRQ_ENABLE)=0;__asm__ volatile("csrw mie,zero":::"memory");}
 REG(IRQ_ACK)=pending&SOURCES; fence_io();
}

uint32_t pmc_periodic_irq_run(uint32_t load,uint32_t events,uint32_t wait_wfi,
                            pmc_periodic_result_t *out)
{
 if (!out) return PMC_PERIODIC_INVALID;
 *out=(pmc_periodic_result_t){0};
 if (load<100000u || load>400000u || events<1u || events>64u || wait_wfi>1u)
  return out->status=PMC_PERIODIC_INVALID;
 uint32_t ms=csr_status(),mi=csr_ie(),mv=csr_vector();
 out->saved_mtvec=mv;out->saved_mie=mi;out->saved_mstatus=ms;
 if (busy || (ms&8u) || mi) return out->status=PMC_PERIODIC_CONTEXT_ACTIVE;
 if (REG(IRQ_ENABLE) || ((REG(IRQ_STATUS)|REG(IRQ_PENDING))&ALL_PIT))
  return out->status=PMC_PERIODIC_SOURCE_BUSY;
 /* Advisory rejection only: zero control readback does not prove stopped.
    The caller must establish exclusive ownership and stop all three timers. */
 if ((REG(PIT2+8)|REG(PIT3+8)|REG(PIT4+8))&1u)
  return out->status=PMC_PERIODIC_SOURCE_BUSY;
 uint32_t old2=REG(PIT2),old3=REG(PIT3),old4=REG(PIT4);
 busy=1;hits=done=reason=cause=pending=first_ref=last_ref=0;target=events;
 REG(PIT2+8)=0;REG(PIT3+8)=0;REG(PIT4+8)=0;REG(IRQ_ENABLE)=0;REG(IRQ_ACK)=SOURCES;
 REG(PIT2)=load;REG(PIT3)=load*(events+8u)*2u;REG(PIT4)=0xffffffffu;
 REG(PIT4+8)=3;fence_io();
 uint64_t begin=pmc_bsp_cycle_count(),instructions=pmc_bsp_instret_count();
 uint32_t reference=REG(PIT4+4),dispatch=0,checksum=0;
 __asm__ volatile("csrw mtvec,%0; csrw mie,%1"::"r"((uintptr_t)periodic_handler),"r"(0x800u):"memory");
 REG(IRQ_ENABLE)=SOURCES;REG(PIT3+8)=1;REG(PIT2+8)=3;fence_io();
 if (!wait_wfi) __asm__ volatile("csrsi mstatus,8":::"memory");
 while (!done) {
  if (!wait_wfi && reference-REG(PIT4+4)>=load*(events+8u)*2u) {
   __asm__ volatile("csrci mstatus,8":::"memory");
   if (!done) {reason=PMC_PERIODIC_WATCHDOG;done=1;}
   break;
  }
  uint32_t observed=hits;
  if (observed>dispatch+1u) out->coalesced+=observed-dispatch-1u;
  while (dispatch<observed) {
   ++dispatch;checksum=(checksum<<5)^dispatch^(checksum>>27);
   if (dispatch%2u==0) ++out->task_every_two;
   if (dispatch%5u==0) ++out->task_every_five;
  }
  if (wait_wfi) {
   __asm__ volatile("csrci mstatus,8":::"memory");
   /* WFI may return spuriously; enabled pending IRQs can wake it even with
      global MIE clear. Recheck the predicate on every iteration. */
   if (!done) {__asm__ volatile("wfi":::"memory");++out->wfi_returns;}
   __asm__ volatile("csrsi mstatus,8":::"memory");
   /* Pending interrupt dispatch must have an instruction window before masking. */
   __asm__ volatile("nop; nop; nop; nop":::"memory");
  }
 }
 __asm__ volatile("csrci mstatus,8; csrw mie,zero":::"memory");
 while (dispatch<hits) {
  ++dispatch;checksum=(checksum<<5)^dispatch^(checksum>>27);
  if (dispatch%2u==0) ++out->task_every_two;
  if (dispatch%5u==0) ++out->task_every_five;
 }
 out->cycle_delta=pmc_bsp_cycle_count()-begin;
 out->instret_delta=pmc_bsp_instret_count()-instructions;
 out->reference_delta=reference-REG(PIT4+4);
 REG(PIT2+8)=0;REG(PIT3+8)=0;REG(PIT4+8)=0;REG(IRQ_ENABLE)=0;REG(IRQ_ACK)=SOURCES;
 REG(PIT2)=old2;REG(PIT3)=old3;REG(PIT4)=old4;fence_io();
 out->events=hits;out->dispatched=dispatch;out->dispatch_checksum=checksum;
 out->last_cause=cause;out->last_pending=pending;out->first_reference=first_ref;out->last_reference=last_ref;
 out->final_pending=REG(IRQ_PENDING);out->final_enable=REG(IRQ_ENABLE);
 __asm__ volatile("csrw mtvec,%0; csrw mie,%1; csrw mstatus,%2; fence iorw,iorw"::"r"(mv),"r"(mi),"r"(ms):"memory");
 out->restored_mtvec=csr_vector();out->restored_mie=csr_ie();out->restored_mstatus=csr_status();
 uint32_t clean=0;
 if (out->final_pending&SOURCES) clean|=1;
 if (out->final_enable) clean|=2;
 if (out->restored_mtvec!=mv || out->restored_mie!=mi || out->restored_mstatus!=ms) clean|=4;
 if (REG(PIT2)!=old2 || REG(PIT3)!=old3 || REG(PIT4)!=old4) clean|=8;
 out->cleanup_errors=clean;busy=0;
 return out->status=clean?PMC_PERIODIC_CLEANUP_FAILED:reason;
}
