#include <stdint.h>
#include <stddef.h>
#include "config_spec.h"

extern void pmc_hello(void),post_configuration_monitor(void);
extern void sha3_256(const uint8_t *,size_t,uint8_t [32]);
extern uint8_t __chunk_buffer[];
static uint32_t remaining,available,cursor,consumed;
static uint8_t expected[32];
volatile uint32_t configured_chunks,configured_commands,configured_words;
volatile uint32_t boot_initial_error_status;
volatile uint32_t boot_initial_ccu_reset;
volatile uint32_t boot_initial_dma_source_ctrl2,boot_initial_dma_destination_ctrl2;
static volatile uint32_t *reg(uint32_t address) {return (volatile uint32_t *)address;}
static void stage(uint32_t value) { *reg(0x040a0158)=value; }
static void fail(unsigned code) __attribute__((noreturn));
static void fail(unsigned code) {stage(0xe0|(code&31));for(;;) {}}
static void dma_read(uint32_t bytes)
{
    /* SBI stream -> DMA destination channel. Preserve BootROM's native
       stream framing; program our own DMA registers and poll completion. */
    *reg(0x040a0090)=10;
    *reg(0x040e0814)=2;
    *reg(0x040e0800)=(uint32_t)__chunk_buffer;
    *reg(0x040e0828)=0;
    __asm__ volatile("fence rw,rw" ::: "memory");
    *reg(0x040e0804)=bytes;
    stage(0x26);
    unsigned limit=300000000;
    while(!(*reg(0x040e0814)&2)) if(!--limit) fail(2);
    *reg(0x040e0814)=2;
    stage(0x27);
    __asm__ volatile("fence rw,rw" ::: "memory");
}
static void sha3_hardware(uint32_t bytes,uint8_t digest[32])
{
    *reg(0x04100004)=1;
    *reg(0x04100004)=0;
    *reg(0x041000a0)=0; /* SHA3 rather than legacy Keccak */
    *reg(0x041000a4)=1; /* engine applies final SHA3 padding */
    *reg(0x04100000)=1;
    *reg(0x040a0090)=0x500; /* DMA source -> SHA3 stream input */
    *reg(0x040e0014)=2;
    *reg(0x040e0000)=(uint32_t)__chunk_buffer;
    *reg(0x040e0028)=0;
    __asm__ volatile("fence rw,rw" ::: "memory");
    *reg(0x040e0004)=bytes|1; /* last-word indication for padding */
    unsigned limit=300000000;
    while(!(*reg(0x040e0014)&2)||!(*reg(0x04100008)&1))
        if(!--limit) { *reg(0x040a015c)=*reg(0x04100008);fail(26); }
    if(*reg(0x040e0014)&0x5c) fail(22);
    *reg(0x040e0014)=2;
    for(unsigned i=0;i<8;++i) {
        uint32_t v=*reg(0x04100010+4*i);
        for(unsigned b=0;b<4;++b) digest[4*i+b]=(uint8_t)(v>>(8*b));
    }
}
static void next_chunk(void)
{
    if(!remaining) fail(3);
    uint32_t bytes=remaining>0x1fe0?0x1fe0:remaining;
    uint32_t encoded=bytes+(remaining>bytes?32:0);
    uint8_t digest[32];
    dma_read(encoded);
    sha3_hardware(encoded,digest);
    for(unsigned i=0;i<32;++i) if(digest[i]!=expected[i]) {
        *reg(0x040a015c)=((uint32_t *)digest)[0];fail(4);
    }
    stage(0x28);
    if(remaining>bytes) for(unsigned i=0;i<32;++i) expected[i]=__chunk_buffer[bytes+i];
    remaining-=bytes;available=bytes/4;cursor=0;++configured_chunks;
}
static void dma_write(uint32_t source,uint32_t destination,uint32_t bytes,unsigned swap)
{
    *reg(0x040a0090)=5; /* DMA source -> DMA destination */
    *reg(0x040e0014)=2;
    *reg(0x040e0814)=2;
    (void)swap;
    *reg(0x040e0800)=destination;
    *reg(0x040e0828)=0;
    *reg(0x040e0804)=bytes;
    *reg(0x040e0000)=source;
    *reg(0x040e0028)=0;
    __asm__ volatile("fence rw,rw" ::: "memory");
    *reg(0x040e0004)=bytes;
    unsigned limit=300000000;
    while(!(*reg(0x040e0014)&2)||!(*reg(0x040e0814)&2))
        if(!--limit) fail(20);
    uint32_t errors=(*reg(0x040e0014)&0x5c)|((*reg(0x040e0814)&0xdc)<<8);
    if(errors) { *reg(0x040a015c)=errors;fail(22); }
    if(*reg(0x040e0000)!=source+bytes||*reg(0x040e0800)!=destination+bytes) {
        *reg(0x040a015c)=*reg(0x040e0800);fail(25);
    }
    *reg(0x040e0014)=2;
    *reg(0x040e0814)=2;
    __asm__ volatile("fence rw,rw" ::: "memory");
}
static uint32_t word(void)
{
    if(consumed>=CDO_BYTES/4) fail(5);
    if(cursor==available) next_chunk();
    ++consumed;
    return ((uint32_t *)__chunk_buffer)[cursor++];
}
static int permitted_write(uint32_t address)
{
    for(unsigned i=0;i<sizeof(cdo_write_addresses)/sizeof(cdo_write_addresses[0]);++i)
        if(address==cdo_write_addresses[i]) return 1;
    return 0;
}
void independent_main(void)
{
    stage(0x21);
    /* Only the laboratory non-authenticated, non-encrypted JTAG image.
       Never reinterpret a secure/encrypted image as a plaintext CDO. */
    volatile uint32_t *instance=(volatile uint32_t *)(*reg(0x0402f9c8));
    if((uint32_t)instance<0x0402b000||(uint32_t)instance>0x0402ff00) fail(1);
    volatile uint32_t *header=(volatile uint32_t *)instance[0];
    if((uint32_t)header<0x0402b000||(uint32_t)header>0x0402fcd0) fail(1);
    if(header[0]!=0x665599aa || header[1]!=0x584c4e58 || header[2] ||
       header[5]!=CDO_BYTES || instance[5]!=5 || instance[6] || instance[9] ||
       instance[12] || instance[14]) fail(1);
    uint8_t digest[32];
    static const uint8_t empty_digest[32]={0xa7,0xff,0xc6,0xf8,0xbf,0x1e,0xd7,0x66,
        0x51,0xc1,0x47,0x56,0xa0,0x61,0xd6,0x62,0xf5,0x80,0xff,0x4d,0xe4,0x3b,0x49,0xfa,
        0x82,0xd8,0x0a,0x4b,0x80,0xf8,0x43,0x4a};
    sha3_256((const uint8_t *)"",0,digest);
    for(unsigned i=0;i<32;++i) if(digest[i]!=empty_digest[i]) fail(6);
    pmc_hello();
    /* Normal PMC data-port attributes and user JTAG instruction exposure
       for this already non-secure laboratory boot. Match the baseline
       device initialization without altering eFuse or lockdown policy. */
    *reg(0x04040010)=2;
    *reg(0x040d0000)=*reg(0x040d0000)&~0x1cu;
    *reg(0x040d0004)=*reg(0x040d0004)&~0x0cu;
    /* W1C reset-latched EAM status before configuration starts. Preserve
       the initial value for diagnosis; do not clear configuration errors. */
    boot_initial_error_status=*reg(0x040b0000);
    *reg(0x040b0000)=boot_initial_error_status&0x7fffffff;
    boot_initial_ccu_reset=*reg(0x040a0060);
    boot_initial_dma_source_ctrl2=*reg(0x040e0024);
    boot_initial_dma_destination_ctrl2=*reg(0x040e0824);
    *reg(0x040a0060)=0;
    *reg(0x040e000c)=0x013ffa00;
    *reg(0x040e080c)=0x813ffa00;
    /* Cross-check the SHA hardware against our software implementation
       on a short standard SHA3 message before consuming the CDO. */
    ((uint32_t *)__chunk_buffer)[0]=0x64636261; /* "abcd" */
    uint8_t hardware_digest[32];
    sha3_256(__chunk_buffer,4,digest);
    sha3_hardware(4,hardware_digest);
    for(unsigned i=0;i<32;++i) if(digest[i]!=hardware_digest[i]) fail(27);
    /* Verify the independent DMA driver before using it for configuration. */
    for(unsigned i=0;i<2048;++i) ((uint32_t *)__chunk_buffer)[i]=0xa5917000u+i;
    dma_write((uint32_t)__chunk_buffer,0x04027000,8192,0);
    for(unsigned i=0;i<2048;++i) if(*reg(0x04027000+4*i)!=0xa5917000u+i) {
        *reg(0x040a015c)=*reg(0x04027000+4*i);fail(23);
    }
    *reg(0x040b0024)=*reg(0x040b0024)|0x06000000;
    remaining=CDO_BYTES;
    for(unsigned i=0;i<32;++i) expected[i]=cdo_root[i];
    stage(0x22);
    uint32_t h[5];for(unsigned i=0;i<5;++i) h[i]=word();
    if(h[0]!=4||h[1]!=0x004f4443||h[2]!=0x200||h[3]+5!=CDO_BYTES/4||
       (uint32_t)(h[0]+h[1]+h[2]+h[3]+h[4])!=0xffffffff) fail(7);
    stage(0x23);
    while(consumed<CDO_BYTES/4) {
        uint32_t command=word(),op=command&0xffff,n=(command>>16)&255;
        if(command>>24) fail(8);
        if(n==255) n=word();
        if(n>CDO_BYTES/4-consumed) fail(9);
        ++configured_commands;
        if(op==0x103) {
            if(n!=2) fail(10);
            uint32_t address=word(),value=word();
            if(!permitted_write(address)) fail(11);
            *reg(address)=value;
        } else if(op==0x101) {
            if(n!=4&&n!=6) fail(12);
            uint32_t address=word(),mask=word(),value=word(),timeout=word();
            if(n==6) {word();word();}
            if(address!=0x040c0000&&address!=0x04130000) fail(13);
            unsigned limit=timeout*1000000u;
            if(!limit||limit>300000000u) limit=300000000u;
            while((*reg(address)&mask)!=value) if(!--limit) fail(14);
        } else if(op==0x10d) {
            if(n<3) fail(15);
            uint32_t high=word(),address=word(),span=word();
            if(high||address!=0x04070000||span!=0x4000) fail(16);
            static const uint32_t pre_addresses[]={0x40a0000,0x40a0020,0x40a0024,0x40a0030,0x40a0034,0x40a0050,0x40a0054,0x40a0058,0x40a005c,0x40a0060,0x40a0064,0x40a0080,0x40a0084,0x40a0088,0x40a008c,0x40a00e8,0x40a0140,0x40a0144,0x40a0148,0x40a014c,0x40a0150,0x40d0000,0x40d0004,0x40e000c,0x40e0024,0x40e080c,0x40e0824,0x4130000,0x4130014,0x413001c,0x4130020,0x4130114,0x4130118,0x4130134};
            static const uint32_t pre_values[]={0x1,0x0,0x0,0x300,0x2000400,0x0,0x0,0x1,0x0,0x0,0x1,0x0,0x4,0x1,0x1,0x0,0xd,0x0,0x0,0x0,0x300,0x0,0x0,0x13ffa00,0x81bfff8,0x813ffa00,0x81bfff8,0x0,0x0,0x0,0x9,0xc0080c,0x38003fec,0x0};
            for(unsigned r=0;r<sizeof(pre_addresses)/4;++r) {
                uint32_t got=*reg(pre_addresses[r]);
                if(got!=pre_values[r]) {
                    *reg(0x040a015c)=got;stage(0xa0|(r<<8));for(;;) {}
                }
            }
            stage(0x24);
            uint32_t left=n-3,index=0;
            while(left) {
                if(cursor==available) next_chunk();
                uint32_t take=available-cursor,offset=index&(span-1);
                if(take>left) take=left;
                if(take>span-offset) take=span-offset;
                dma_write((uint32_t)__chunk_buffer+4*cursor,address+4*offset,4*take,1);
                cursor+=take;consumed+=take;configured_words+=take;
                index+=take;left-=take;
            }
            __asm__ volatile("fence rw,rw" ::: "memory");
            stage(0x25);
        } else if(op==0x119) {
            while(n--) word();
        } else if(op==0x111||op==0x130) {
            if(n) fail(17); /* synchronous stream: no deferred DMA to finish */
        } else fail(18);
    }
    if(remaining||cursor!=available||configured_commands!=CDO_COMMANDS||
       configured_words!=CDO_STREAM_WORDS) fail(19);
    if(*reg(0x040b0000)) fail(21);
    stage(0x29);
    unsigned startup_limit=50000000;
    while((*reg(0x04130114)&0x6010)!=0x6010) {
        *reg(0x040a015c)=*reg(0x04130114);
        if(!--startup_limit) {
            stage(0xf6|((*reg(0x04130020)&255)<<8)|
                  ((*reg(0x04130014)&1)<<16)|((*reg(0x040a0060)&1)<<17)|
                  ((boot_initial_ccu_reset&1)<<18));
            for(;;) {}
        }
    }
    *reg(0x040a015c)=*reg(0x04130114);
    stage(0x10);
    post_configuration_monitor();
}
