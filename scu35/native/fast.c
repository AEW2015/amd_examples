/* Native PMC resident-buffer throughput. Public diagnostic key only.
 * Register sequence follows the captured independent SHA/AES experiments.
 * No eFUSE, clock, revocation or persistent-storage writes. */
#include <stdint.h>
#define R(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define SRC 0x04027000u
#define DST 0x0402c000u
#define IV  0x04029400u
#define TAG 0x04029410u
#define SHA 0x04100000u
#define AES 0x040f0000u
#define DMA 0x040e0000u
#define SSS 0x040a0090u
static inline void fence(void){__asm__ volatile("fence iorw,iorw":::"memory");}
static inline uint32_t ticks(void){uint32_t v;__asm__ volatile("csrr %0,mcycle":"=r"(v)::"memory");return v;}
static unsigned wait(uint32_t a,uint32_t mask){
 uint32_t t=ticks();
 for(unsigned n=0;n<10000000u;++n){if((R(a)&mask)==mask)return 0;if(ticks()-t>100000000u)return 1;}
 return 1;
}
static unsigned transfer(uint32_t src,uint32_t dst,unsigned n,unsigned last){
 if(dst){R(DMA+0x814)=2;R(DMA+0x800)=dst;R(DMA+0x828)=0;R(DMA+0x804)=n;}
 if(src){R(DMA+0x14)=2;R(DMA)=src;R(DMA+0x28)=0;fence();R(DMA+4)=n|last;}
 if(src&&wait(DMA+0x14,2))return 2;
 if(dst&&wait(DMA+0x814,2))return 3;
 if((src&&(R(DMA+0x14)&0x5c))||(dst&&(R(DMA+0x814)&0xdc)))return 4;
 if(src&&R(DMA)!=src+n)return 5;
 if(dst&&R(DMA+0x800)!=dst+n)return 6;
 if(src)R(DMA+0x14)=2;
 if(dst)R(DMA+0x814)=2;
 fence();return 0;
}
static unsigned hash(unsigned mode,unsigned bytes){
 R(SHA+4)=1;R(SHA+4)=0;R(SHA+0xa0)=mode;R(SHA+0xa4)=1;R(SHA)=1;
 for(unsigned left=bytes;left;){
  unsigned n=left>8192?8192:left;left-=n;
  unsigned rc=transfer(SRC,0,n,left?0:1);if(rc)return rc;
 }
 return wait(SHA+8,1);
}
static unsigned aes_begin(unsigned decrypt){
 R(AES+0x10)=1;R(AES+0x10)=0;
 R(AES+0x18)=decrypt?0:1;R(AES+0x20)=0;R(AES+0x50)=2;
 R(AES+4)=0xbd858280;R(AES+8)=1;
 if(wait(AES,16))return 7;
 R(AES+0x84)=1;R(AES+0xc)=1;
 return transfer(IV,0,16,0);
}
static unsigned encrypt(unsigned bytes){
 unsigned rc=aes_begin(0);if(rc)return rc;
 for(unsigned left=bytes;left;){unsigned n=left>8192?8192:left;left-=n;
  rc=transfer(SRC,DST,n,left?0:1);if(rc)return rc;
 }
 rc=transfer(0,TAG,16,0);if(rc)return rc;
 return wait(AES,4);
}
static unsigned decrypt(unsigned bytes){
 unsigned rc=aes_begin(1);if(rc)return rc;
 rc=transfer(DST,SRC,bytes,1);if(rc)return rc;
 rc=transfer(TAG,0,16,0);if(rc)return rc;
 if(wait(AES,4))return 8;
 return (R(AES)&8)?0:0x40;
}
static unsigned pattern(unsigned i){return i%251+1;}
unsigned __attribute__((optimize("O3"))) fast_benchmark(unsigned kind,unsigned bytes,unsigned repeats,
 unsigned nonce_lo,unsigned nonce_hi,uint32_t out[128]){
 for(unsigned i=0;i<128;++i)out[i]=0;
 out[0]=0x46415354;out[2]=bytes;out[3]=repeats;out[15]=kind;
 if(kind<1||kind>5||bytes<16||(bytes&15)||bytes>1048576||repeats<1||repeats>1000||
   ((kind==3||kind==4)&&bytes>8192))return 1;
 volatile uint8_t *input=(volatile uint8_t *)(uintptr_t)SRC;
 for(unsigned i=0;i<(bytes>8192?8192:bytes);++i)input[i]=(uint8_t)pattern(i);
 uint32_t old_sss=R(SSS),rc=0;
 R(IV)=nonce_lo;R(IV+4)=nonce_hi;R(IV+8)=0;R(IV+12)=0;
 if(kind>=3){
  R(AES+0x10)=1;R(AES+0x10)=0;
  for(unsigned i=0;i<8;++i){unsigned b=i*4;R(AES+0x20c-i*4)=(b<<24)|((b+1)<<16)|((b+2)<<8)|(b+3);}
  R(SSS)=0x59;
  if(kind==4){rc=encrypt(bytes);if(rc)goto done;}
 }else R(SSS)=0x500;
 fence();
 /* Warm up the exact path once, outside the timed batch. */
 if(kind<=2)rc=hash(kind-1,bytes);
 else if(kind==3||kind==5){R(IV+8)=0x01000000;rc=encrypt(bytes);}
 else rc=decrypt(bytes);
 if(rc)goto done;
 uint32_t begin=ticks();
 for(unsigned r=0;r<repeats;++r){
  if(kind<=2)rc=hash(kind-1,bytes);
  else if(kind==3||kind==5){unsigned n=r+2;R(IV+8)=__builtin_bswap32(n);rc=encrypt(bytes);}
  else rc=decrypt(bytes);
  if(rc)break;
 }
 fence();out[1]=ticks()-begin;
 if(!rc){
  if(kind<=2){for(unsigned i=0;i<8;++i)out[6+i]=R(SHA+0x10+4*i);}
  else{
   for(unsigned i=0;i<4;++i){out[6+i]=R(TAG+4*i);out[10+i]=R(IV+4*i);}
   if(kind==3){rc=decrypt(bytes);if(rc)goto done;}
   for(unsigned i=0;i<(bytes>8192?8192:bytes);++i)if(input[i]!=(uint8_t)pattern(i))++out[5];
   /* After known-good decrypt, reject a modified tag outside the batch. */
   if(kind!=5){R(TAG)^=1;unsigned negative=decrypt(bytes);R(TAG)^=1;
    out[14]=negative;if(negative!=0x40)rc=9;}
  }
 }
done:
 out[4]=rc;out[16]=R(DMA+0x14);out[17]=R(DMA+0x814);out[18]=R(SHA+8);out[19]=R(AES);
 if(kind>=3&&!rc){R(AES+0x14)=0x801;if(wait(AES+0x64,0x801))rc=10;R(AES+0x14)=0;R(AES+0x84)=0;R(AES+0x10)=1;}
 /* A failed transaction is quarantined; host must restore the stock PDI. */
 if(!rc){R(SSS)=old_sss;fence();}
 out[4]=rc;return rc?rc:(out[5]?11:0);
}
