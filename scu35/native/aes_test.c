/* Independent MMIO AES diagnostic. Protocol/register facts are documented in
 * docs/pmc_crypto_test_protocol_20261008.md. Only volatile USER_KEY_7 is used. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(uintptr_t)(a))
static uint32_t ticks(void) {uint32_t v;__asm__ volatile("csrr %0,mcycle":"=r"(v));return v;}
static void fence(void) {__asm__ volatile("fence rw,rw" ::: "memory");}
static unsigned wait_mask(uint32_t address,uint32_t mask)
{
    uint32_t start=ticks();
    while((R(address)&mask)!=mask) if(ticks()-start>100000000u) return 1;
    return 0;
}
static unsigned transfer(uint32_t source,uint32_t dest,unsigned bytes,unsigned last)
{
    if(dest) {
        R(0x040e0814)=2;R(0x040e0800)=dest;R(0x040e0828)=0;
        fence();R(0x040e0804)=bytes;
    }
    if(source) {
        R(0x040e0014)=2;R(0x040e0000)=source;R(0x040e0028)=0;
        fence();R(0x040e0004)=bytes|last;
    }
    if(source&&wait_mask(0x040e0014,2)) return 2;
    if(dest&&wait_mask(0x040e0814,2)) return 3;
    if((source&&(R(0x040e0014)&0x5c))||(dest&&(R(0x040e0814)&0xdc))) return 4;
    if(source) R(0x040e0014)=2;
    if(dest) R(0x040e0814)=2;
    fence();return 0;
}
static void bytes_from_hex(uint32_t address,const char *hex,unsigned bytes)
{
    volatile uint8_t *p=(volatile uint8_t *)(uintptr_t)address;
    for(unsigned i=0;i<bytes;++i) {
        unsigned a=hex[2*i],b=hex[2*i+1];
        a=a<='9'?a-'0':a-'A'+10;b=b<='9'?b-'0':b-'A'+10;
        p[i]=(uint8_t)((a<<4)|b);
    }
}
unsigned pmc_aes_test(uint32_t out[128])
{
    static const char key[]="D416A6931D52E0F50AA089A757B11A891CBD1B83847D4BED9E2938CD4C54A8BA";
    static const char iv[]="85365F88B0B56298DFEA5AB200000000";
    static const char aad[]="9A7B86E782CCAA6AB221BD03470BDC2E";
    static const char plain[]="2FBF029EE9FBD611C24D814E6AFF2677C35A83BCE5632CE789436C6882CA1C71";
    static const char cipher[]="598CD19F1683B41B4C59E1C157D41501A3C08902F0EA3A376A8B0D9988CFF8C1";
    static const char tag[]="ADCEFE2F6EE4C7060E44AA5EDF0DBEBC";
    for(unsigned i=0;i<128;++i) out[i]=0;
    out[0]=0x41455354;
    out[1]=R(0x040f0000);
    uint32_t old_sss=R(0x040a0090),start=ticks();
    unsigned rc=0,stage=1,errors=0;
    bytes_from_hex(0x04027000,key,32);
    bytes_from_hex(0x04027040,iv,16);
    bytes_from_hex(0x04027060,aad,16);
    bytes_from_hex(0x04027080,plain,32);
    bytes_from_hex(0x04027100,cipher,32);
    bytes_from_hex(0x04027120,tag,16);
    R(0x040f0010)=1;R(0x040f0010)=0;
    for(unsigned i=0;i<8;++i) {
        volatile uint8_t *p=(volatile uint8_t *)(uintptr_t)(0x04027000+4*i);
        uint32_t value=((uint32_t)p[0]<<24)|((uint32_t)p[1]<<16)|((uint32_t)p[2]<<8)|p[3];
        R(0x040f020c-4*i)=value;
    }
    R(0x040f0018)=1;R(0x040f0020)=0;
    R(0x040f0050)=2;R(0x040f0004)=0xbd858280;R(0x040f0008)=1;
    stage=2;if(wait_mask(0x040f0000,16)) {rc=1;goto done;}
    R(0x040a0090)=0x59; /* DMA->AES and AES->DMA, Spartan source encodings. */
    R(0x040f000c)=1;R(0x040f0084)=1;
    stage=3;rc=transfer(0x04027040,0,16,0);if(rc) goto done;
    R(0x040f006c)=1;
    stage=4;rc=transfer(0x04027060,0,16,0);if(rc) goto done;
    R(0x040f006c)=0;
    stage=5;rc=transfer(0x04027080,0x0402c100,32,1);if(rc) goto done;
    stage=6;rc=transfer(0,0x0402c120,16,0);if(rc) goto done;
    stage=7;if(wait_mask(0x040f0000,4)) {rc=1;goto done;}
    for(unsigned i=0;i<12;++i) {
        out[8+i]=R(0x0402c100+4*i);
        if(out[8+i]!=R(0x04027100+4*i)) ++errors;
    }
done:
    out[2]=R(0x040f0000);out[3]=stage;out[4]=rc;
    out[5]=errors;out[6]=ticks()-start;
    /* Clear only our test key and its expanded schedule, then reset AES.
       Never touch a PUF/eFuse/other-user-key mask or security lock. */
    R(0x040f0014)=0x801;
    unsigned cleanup=wait_mask(0x040f0064,0x801);
    out[7]=R(0x040f0064);
    R(0x040f0014)=0;R(0x040f0084)=0;R(0x040f0010)=1;
    if(rc==0) R(0x040a0090)=old_sss;
    fence();
    return rc?rc:(cleanup?6:(errors?5:0));
}
