/* AMD AXI Timer v2.0 register layout (PG079 / xtmrctr_l.h).
 * Both 32-bit channels form one free-running 64-bit counter at 100 MHz.
 * No interrupt, external capture or PWM is enabled.
 */
#define TMR_BASE 0x40000000U
#define TMR_CASC 0x800U
#define TMR_ENT  0x080U
#define TMR_LOAD 0x020U
#define TMR_ARHT 0x010U
static u64 timer_ticks64(void) {
    u32 hi,lo,again;
    do {
        hi=Xil_In32(TMR_BASE+0x18U);
        lo=Xil_In32(TMR_BASE+0x08U);
        again=Xil_In32(TMR_BASE+0x18U);
    } while(hi!=again);
    return ((u64)hi<<32)|lo;
}
/* Existing CMP v2 rows contain 32-bit elapsed ticks. Each individual interval
 * is below 2^32 ticks (42.95 s); subtraction remains modulo 2^32. The hardware
 * timer and coherent reader are 64-bit. Read overhead is retained, not removed.
 */
static u32 ticks(void) { return (u32)timer_ticks64(); }
static void timer_load(u32 hi,u32 lo) {
    Xil_Out32(TMR_BASE,0U);
    Xil_Out32(TMR_BASE+0x10U,0U);
    Xil_Out32(TMR_BASE+4U,lo);
    Xil_Out32(TMR_BASE+0x14U,hi);
    Xil_Out32(TMR_BASE+0x10U,TMR_LOAD);
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_LOAD);
    Xil_Out32(TMR_BASE+0x10U,0U);
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_ARHT);
}
static int timer_selftest(void) {
    /* Force a lower-half carry without waiting 42.95 seconds. */
    timer_load(0x12345678U,0xfffff000U);
    u64 stopped=timer_ticks64();
    if(stopped!=0x12345678fffff000ULL)return 1;
    if(timer_ticks64()!=stopped)return 2;
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_ARHT|TMR_ENT);
    u64 now=stopped;
    for(u32 n=0;n<100000U;++n){now=timer_ticks64();if((u32)(now>>32)!=0x12345678U)break;}
    if((u32)(now>>32)!=0x12345679U || now<=stopped)return 3;
    xil_printf("TMR_TEST,carry,1,%u\r\n",(u32)(now-stopped));
    timer_load(0,0);
    if(timer_ticks64()!=0)return 4;
    Xil_Out32(TMR_BASE,TMR_CASC|TMR_ARHT|TMR_ENT);
    u64 last=timer_ticks64();
    u32 lo=~0U,hi=0;
    for(u32 n=0;n<1000;++n){
        now=timer_ticks64();
        if(now<=last)return 5;
        u32 delta=(u32)(now-last);if(delta<lo)lo=delta;if(delta>hi)hi=delta;
        last=now;
    }
    if((Xil_In32(TMR_BASE)&(TMR_CASC|TMR_ENT|0x40U))!=(TMR_CASC|TMR_ENT))return 6;
    xil_printf("TMR_TEST,monotonic,1000,%u,%u\r\n",lo,hi);
    xil_printf("TMR_META,axi_timer,64,100000000,40000000\r\n");
    return 0;
}
