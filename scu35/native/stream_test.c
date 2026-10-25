#include <stdint.h>
#include <stddef.h>
#include "pmc_stream.h"
extern void sha3_256(const uint8_t *,size_t,uint8_t[32]);
static unsigned initialized;
static uint32_t pattern(unsigned i)
{
    uint32_t x=i*0x9e3779b9u+0x6d2b79f5u;
    x^=x>>15;x*=0x85ebca6bu;return x^(x>>13);
}
static uint32_t checksum(volatile uint32_t *p,unsigned n)
{
    uint32_t x=0x13579bdf;
    for(unsigned i=0;i<n;++i) {x=(x<<5)|(x>>27);x^=p[i]+i;}
    return x;
}

static uint64_t stream_cycle64(void)
{
    uint32_t hi0,lo,hi1;
    do {
        __asm__ volatile("csrr %0,mcycleh":"=r"(hi0)::"memory");
        __asm__ volatile("csrr %0,mcycle":"=r"(lo)::"memory");
        __asm__ volatile("csrr %0,mcycleh":"=r"(hi1)::"memory");
    } while(hi0!=hi1);
    return ((uint64_t)hi0<<32)|lo;
}

#define STREAM_REG(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define STREAM_SSS 0x040a0090u
#define STREAM_SRC_ADDR 0x040e0000u
#define STREAM_SRC_SIZE 0x040e0004u
#define STREAM_SRC_CTRL 0x040e000cu
#define STREAM_SRC_ISR 0x040e0014u
#define STREAM_SRC_STATUS 0x040e0008u
#define STREAM_SRC_MSB 0x040e0028u
#define STREAM_DST_ADDR 0x040e0800u
#define STREAM_DST_SIZE 0x040e0804u
#define STREAM_DST_CTRL 0x040e080cu
#define STREAM_DST_ISR 0x040e0814u
#define STREAM_DST_STATUS 0x040e0808u
#define STREAM_DST_MSB 0x040e0828u
#define STREAM_SHA_RESET 0x04100004u
#define STREAM_SHA_START 0x04100000u
#define STREAM_SHA_STATUS 0x04100008u
#define STREAM_SHA_MODE 0x041000a0u
#define STREAM_SHA_AUTO 0x041000a4u

/* Snapshot registers whose values reveal any accidental setup/trigger writes. */
static void stream_mmio_snapshot(uint32_t snapshot[18])
{
    snapshot[0]=STREAM_REG(STREAM_SSS);
    snapshot[1]=STREAM_REG(STREAM_SRC_CTRL);snapshot[2]=STREAM_REG(STREAM_SRC_ADDR);
    snapshot[3]=STREAM_REG(STREAM_SRC_SIZE);snapshot[4]=STREAM_REG(STREAM_SRC_ISR);
    snapshot[5]=STREAM_REG(STREAM_SRC_MSB);snapshot[6]=STREAM_REG(STREAM_SRC_STATUS);
    snapshot[7]=STREAM_REG(STREAM_DST_CTRL);snapshot[8]=STREAM_REG(STREAM_DST_ADDR);
    snapshot[9]=STREAM_REG(STREAM_DST_SIZE);snapshot[10]=STREAM_REG(STREAM_DST_ISR);
    snapshot[11]=STREAM_REG(STREAM_DST_MSB);snapshot[12]=STREAM_REG(STREAM_DST_STATUS);
    snapshot[13]=STREAM_REG(STREAM_SHA_RESET);snapshot[14]=STREAM_REG(STREAM_SHA_MODE);
    snapshot[15]=STREAM_REG(STREAM_SHA_AUTO);
    snapshot[16]=STREAM_REG(STREAM_SHA_START);
    snapshot[17]=STREAM_REG(STREAM_SHA_STATUS);
}

static int stream_snapshots_equal(const uint32_t a[18],const uint32_t b[18])
{
    for(unsigned i=0;i<18;++i) if(a[i]!=b[i]) return 0;
    return 1;
}

/*
 * Must be called before pmc_stream_test() has initialized the driver.
 * Word ABI is documented in experimental/README.md and repeated here:
 *   0 magic, 1 op, 2 failure count, 3 pre-init status mask,
 *   4 post-init rejection mask, 5 no-MMIO-change mask (pre/duplicate/args), 6 init rc,
 *   7 original SSS, 8 SSS after init, 9 forced-timeout rc, 10 its quiescent,
 *   11 packed source/destination ISR, 12-13 progress, 14-15 elapsed cycles,
 *   16 immediate SSS,
 *   17 late DONE+idle observed, 18-21 final ISR/status, 22 copy errors,
 *   23 restored SSS, 24 ISR after W1C ack, 25-27 normal DMA rc/errors/q,
 *   28-30 normal SHA rc/digest-errors/q, 31 final SSS.
 */
unsigned pmc_stream_negative_test(uint32_t out[128])
{
    uint32_t before[18],after[18],duplicate_snapshot[18];
    uint32_t initial_route,original_route,source_isr=0,destination_isr=0;
    uint32_t source_status=0,destination_status=0,copy_errors=0;
    unsigned failures=0;
    pmc_stream_result_t report;
    uint8_t digest_expected[32],digest_actual[32];

    if(out==NULL) return 1;
    for(unsigned i=0;i<32;++i) out[i]=0;
    out[0]=0x53544e47u; /* STNG */
    out[1]=19u;
    if(initialized) { out[2]=1; return 1; }

    stream_mmio_snapshot(before);
    initial_route=before[0];
    pmc_stream_status_t pre_dma=pmc_stream_dma_copy(
        PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,4,1,&report);
    pmc_stream_status_t pre_sha=pmc_stream_sha3_256(
        PMC_STREAM_SCRATCH_BASE,4,1,digest_actual,&report);
    stream_mmio_snapshot(after);
    if(pre_dma==PMC_STREAM_NOT_INITIALIZED) out[3]|=1u; else ++failures;
    if(pre_sha==PMC_STREAM_NOT_INITIALIZED) out[3]|=2u; else ++failures;
    if(stream_snapshots_equal(before,after)) out[5]|=1u; else ++failures;

    pmc_stream_status_t init_status=pmc_stream_init();
    out[6]=(uint32_t)init_status;
    if(init_status!=PMC_STREAM_OK) { out[2]=failures+1; return out[2]; }
    initialized=1;
    stream_mmio_snapshot(after);
    original_route=after[0];
    out[7]=initial_route;out[8]=original_route;

    pmc_stream_status_t duplicate=pmc_stream_init();
    stream_mmio_snapshot(duplicate_snapshot);
    if(duplicate==PMC_STREAM_INVALID) out[4]|=1u; else ++failures;
    if(stream_snapshots_equal(after,duplicate_snapshot)) {
        out[5]|=2u; /* duplicate init rejection made no MMIO change */
    } else ++failures;

    uint32_t statuses[14];
    unsigned bit=1u;
    statuses[0]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE+1,PMC_STREAM_STAGE_BASE,4,1000,&report);
    statuses[1]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE+1,4,1000,&report);
    statuses[2]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE-4,PMC_STREAM_STAGE_BASE,4,1000,&report);
    statuses[3]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE+PMC_STREAM_WINDOW_SIZE,4,1000,&report);
    statuses[4]=pmc_stream_dma_copy(UINT32_C(0xfffffffc),PMC_STREAM_STAGE_BASE,8,1000,&report);
    statuses[5]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_SCRATCH_BASE+4,8,1000,&report);
    statuses[6]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,0,1000,&report);
    statuses[7]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,2,1000,&report);
    statuses[8]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,8196,1000,&report);
    statuses[9]=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,4,0,&report);
    statuses[10]=pmc_stream_sha3_256(PMC_STREAM_SCRATCH_BASE+1,4,1000,digest_actual,&report);
    statuses[11]=pmc_stream_sha3_256(PMC_STREAM_SCRATCH_BASE-4,4,1000,digest_actual,&report);
    statuses[12]=pmc_stream_sha3_256(PMC_STREAM_SCRATCH_BASE,4,0,digest_actual,&report);
    statuses[13]=pmc_stream_sha3_256(PMC_STREAM_SCRATCH_BASE,4,1000,NULL,&report);
    for(unsigned i=0;i<14;++i,bit<<=1) {
        if(statuses[i]==PMC_STREAM_INVALID) out[4]|=bit<<1;
        else ++failures;
    }
    stream_mmio_snapshot(after);
    if(stream_snapshots_equal(after,duplicate_snapshot)) out[5]|=4u;
    else ++failures;
    if(out[4]!=0x7fffu) ++failures; /* duplicate init plus 14 invalid-argument cases */

    /* Refill known buffers, then force a deliberately tiny DMA deadline. */
    volatile uint32_t *src=(volatile uint32_t *)(uintptr_t)PMC_STREAM_SCRATCH_BASE;
    volatile uint32_t *dst=(volatile uint32_t *)(uintptr_t)PMC_STREAM_STAGE_BASE;
    for(unsigned i=0;i<PMC_STREAM_MAX_BYTES/4u;++i) {
        src[i]=pattern(i);dst[i]=~pattern(i);
    }
    __asm__ volatile("fence rw,rw":::"memory");
    pmc_stream_status_t forced=pmc_stream_dma_copy(
        PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,PMC_STREAM_MAX_BYTES,1,&report);
    out[9]=(uint32_t)forced;out[10]=report.quiescent;
    out[11]=(report.source_isr&0xffffu)|((report.destination_isr&0xffffu)<<16);
    out[12]=report.source_address;out[13]=report.destination_address;
    out[14]=(uint32_t)report.elapsed_cycles;
    out[15]=(uint32_t)(report.elapsed_cycles>>32);
    out[16]=STREAM_REG(STREAM_SSS);
    if(forced!=PMC_STREAM_TIMEOUT) ++failures;
    if((report.quiescent && out[16]!=original_route) ||
       (!report.quiescent && out[16]!=5u)) ++failures;

    uint64_t wait_start=stream_cycle64();
    int completed=0;
    for(uint32_t poll=0;poll<10000000u;++poll) {
        source_isr=STREAM_REG(STREAM_SRC_ISR);
        destination_isr=STREAM_REG(STREAM_DST_ISR);
        source_status=STREAM_REG(STREAM_SRC_STATUS);
        destination_status=STREAM_REG(STREAM_DST_STATUS);
        if((source_isr&2u)&&(destination_isr&2u)&&
           !(source_status&1u)&&!(destination_status&1u)) {completed=1;break;}
        if(stream_cycle64()-wait_start>=10000000ull) break;
    }
    out[17]=(uint32_t)completed;out[18]=source_isr;out[19]=destination_isr;
    out[20]=source_status;out[21]=destination_status;
    if(!completed) {
        out[2]=failures+1; /* Leave route/active transaction intact for stock reload. */
        return out[2];
    }
    if((source_isr&0x5cu)||(destination_isr&0xdcu)) ++failures;
    for(unsigned i=0;i<PMC_STREAM_MAX_BYTES/4u;++i)
        if(dst[i]!=src[i]) ++copy_errors;
    out[22]=copy_errors;
    if(copy_errors) ++failures;

    /* Quiescence is now observed: it is safe for this caller to restore SSS. */
    STREAM_REG(STREAM_SSS)=original_route;
    STREAM_REG(STREAM_SRC_ISR)=2u;STREAM_REG(STREAM_DST_ISR)=2u;
    __asm__ volatile("fence iorw,iorw":::"memory");
    out[23]=STREAM_REG(STREAM_SSS);
    out[24]=(STREAM_REG(STREAM_SRC_ISR)&0xffffu)|
            ((STREAM_REG(STREAM_DST_ISR)&0xffffu)<<16);
    if(out[23]!=original_route || (out[24]&0x00020002u)!=0) ++failures;

    /* The normal APIs must still work after timeout cleanup. */
    for(unsigned i=0;i<16;++i) {src[i]=pattern(i);dst[i]=~src[i];}
    __asm__ volatile("fence rw,rw":::"memory");
    pmc_stream_status_t dma_status=pmc_stream_dma_copy(
        PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,64,10000000ull,&report);
    unsigned normal_copy_errors=0;
    if(dma_status==PMC_STREAM_OK)
        for(unsigned i=0;i<16;++i) if(src[i]!=dst[i]) ++normal_copy_errors;
    out[25]=(uint32_t)dma_status;out[26]=normal_copy_errors;out[27]=report.quiescent;
    if(dma_status!=PMC_STREAM_OK || normal_copy_errors || !report.quiescent) ++failures;

    sha3_256((const uint8_t *)(uintptr_t)PMC_STREAM_SCRATCH_BASE,64,digest_expected);
    pmc_stream_status_t sha_status=pmc_stream_sha3_256(
        PMC_STREAM_SCRATCH_BASE,64,10000000ull,digest_actual,&report);
    unsigned sha_errors=0;
    if(sha_status==PMC_STREAM_OK)
        for(unsigned i=0;i<32;++i) if(digest_expected[i]!=digest_actual[i]) ++sha_errors;
    out[28]=(uint32_t)sha_status;out[29]=sha_errors;out[30]=report.quiescent;
    out[31]=STREAM_REG(STREAM_SSS);
    if(sha_status!=PMC_STREAM_OK || sha_errors || !report.quiescent || out[31]!=original_route)
        ++failures;
    out[2]=failures;
    return failures ? 1u : 0u;
}
unsigned pmc_stream_test(unsigned kind,unsigned bytes,uint32_t out[128])
{
    for(unsigned i=0;i<32;++i) out[i]=0;
    out[0]=0x5354524d;out[1]=kind;out[2]=bytes;
    if(kind<1||kind>2||bytes<4||bytes>8192||(bytes&3)) return 1;
    if(!initialized) {
        if((*(volatile uint32_t *)0x040e0008&1)||(*(volatile uint32_t *)0x040e0808&1)) return 2;
        if(pmc_stream_init()!=PMC_STREAM_OK) return 3;
        initialized=1;
    }
    volatile uint32_t *src=(volatile uint32_t *)PMC_STREAM_SCRATCH_BASE;
    volatile uint32_t *dst=(volatile uint32_t *)PMC_STREAM_STAGE_BASE;
    for(unsigned i=0;i<bytes/4;++i) {src[i]=pattern(i);dst[i]=~src[i];}
    __asm__ volatile("fence rw,rw":::"memory");
    pmc_stream_result_t report;
    pmc_stream_status_t status;
    unsigned errors=0;
    if(kind==1) {
        uint32_t expected=checksum(src,bytes/4);
        status=pmc_stream_dma_copy(PMC_STREAM_SCRATCH_BASE,PMC_STREAM_STAGE_BASE,bytes,10000000ull,&report);
        if(status==PMC_STREAM_OK) {
            for(unsigned i=0;i<bytes/4;++i) if(src[i]!=dst[i]) ++errors;
            out[16]=expected;out[24]=checksum(dst,bytes/4);
        }
    } else {
        uint8_t expected[32],actual[32]={0};
        sha3_256((const uint8_t *)PMC_STREAM_SCRATCH_BASE,bytes,expected);
        status=pmc_stream_sha3_256(PMC_STREAM_SCRATCH_BASE,bytes,10000000ull,actual,&report);
        for(unsigned i=0;i<32;++i) {
            if(expected[i]!=actual[i]) ++errors;
            out[16+i/4]|=(uint32_t)expected[i]<<(8*(i%4));
            out[24+i/4]|=(uint32_t)actual[i]<<(8*(i%4));
        }
    }
    out[3]=status;out[4]=(uint32_t)report.elapsed_cycles;out[5]=(uint32_t)(report.elapsed_cycles>>32);
    out[6]=report.source_isr;out[7]=report.destination_isr;out[8]=report.engine_status;
    out[9]=report.source_address;out[10]=report.destination_address;out[11]=report.quiescent;
    out[12]=errors;
    return status!=PMC_STREAM_OK||errors;
}
