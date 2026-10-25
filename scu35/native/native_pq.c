/* Benchmark verification port of the fixed SHAKE LMS/HSS reference.
 * Public vectors are uploaded after configuration, not embedded in loader code.
 * Supports LMS n=32/h=5,10/w=2,4,8 and the demonstrated one-level HSS wrapper.
 * Benchmark implementation, not a qualified production cryptographic library. */
#include <stdint.h>
#pragma GCC optimize ("O3","no-tree-loop-distribute-patterns","no-strict-aliasing")
#define R(a) (*(volatile uint32_t *)(uintptr_t)(a))
#define INPUT ((uint8_t *)(uintptr_t)0x04027000u)
#define Z (INPUT+512)
#define SIGN ((uint8_t *)(uintptr_t)0x0402c000u)
#define MSG ((uint8_t *)(uintptr_t)0x0402d200u)
#define PUB ((uint8_t *)(uintptr_t)0x0402d280u)
#define SHA 0x04100000u
#define DMA 0x040e0000u
#define SSS 0x040a0090u
static unsigned hash_calls,hash_cycles,hash_error;
static inline void fence(void){__asm__ volatile("fence iorw,iorw":::"memory");}
static inline unsigned ticks(void){unsigned v;__asm__ volatile("csrr %0,mcycle":"=r"(v)::"memory");return v;}
static unsigned be32(const uint8_t *p){return ((unsigned)p[0]<<24)|((unsigned)p[1]<<16)|((unsigned)p[2]<<8)|p[3];}
static void put32(uint8_t *p,unsigned v){p[0]=v>>24;p[1]=v>>16;p[2]=v>>8;p[3]=v;}
static void copy(uint8_t *d,const uint8_t *s,unsigned n){
 if(d==s)return;
 while(n&&((uintptr_t)d&3)){*d++=*s++;--n;}
 if(!((uintptr_t)s&3)){
  while(n>=4){*(uint32_t *)(void *)d=*(const uint32_t *)(const void *)s;d+=4;s+=4;n-=4;}
 }else{
  while(n>=4){*(uint32_t *)(void *)d=(unsigned)s[0]|((unsigned)s[1]<<8)|((unsigned)s[2]<<16)|((unsigned)s[3]<<24);d+=4;s+=4;n-=4;}
 }
 while(n--)*d++=*s++;
}
static void zero(uint8_t *d,unsigned n){
 while(n&&((uintptr_t)d&3)){*d++=0;--n;}
 while(n>=4){*(uint32_t *)(void *)d=0;d+=4;n-=4;}
 while(n--)*d++=0;
}
static unsigned equal(const uint8_t *a,const uint8_t *b){unsigned diff=0;for(unsigned i=0;i<32;++i)diff|=a[i]^b[i];return diff==0;}
static unsigned wait(uint32_t a,unsigned mask){
 unsigned t=ticks();for(unsigned i=0;i<1000000;++i){if((R(a)&mask)==mask)return 0;if(ticks()-t>10000000)return 1;}return 1;
}
static unsigned shake(const uint8_t *data,unsigned n,uint8_t output[32]){
 if(hash_error||n>4780)return 1;
 /* Forward copy is safe for the Z aggregate because destination is below it. */
 copy(INPUT,data,n);
 unsigned bytes=((n+1+135)/136)*136;
 zero(INPUT+n,bytes-n);
 INPUT[n]=0x1f;INPUT[bytes-1]|=0x80;
 fence();unsigned start=ticks();++hash_calls;
 R(SHA+4)=1;R(SHA+4)=0;R(SHA+0xa0)=1;R(SHA+0xa4)=0;R(SHA)=1;
 R(DMA+0x14)=2;R(DMA)=(unsigned)(uintptr_t)INPUT;R(DMA+0x28)=0;
 fence();R(DMA+4)=bytes|1;
 if(wait(DMA+0x14,2)||wait(SHA+8,1)||(R(DMA+0x14)&0x5c)||R(DMA)!=(unsigned)(uintptr_t)(INPUT+bytes)){
  hash_error=1;hash_cycles+=ticks()-start;return 1;
 }
 for(unsigned i=0;i<8;++i)((uint32_t *)(void *)output)[i]=R(SHA+0x10+4*i);
 R(DMA+0x14)=2;fence();hash_cycles+=ticks()-start;return 0;
}
static void prefix(uint8_t *p,const uint8_t *I,unsigned q,unsigned domain){
 copy(p,I,16);put32(p+16,q);p[20]=(uint8_t)(domain>>8);p[21]=(uint8_t)domain;
}
static unsigned coefficient(const uint8_t *p,unsigned i,unsigned w){return (p[i*w/8]>>(8-w-(i*w%8)))&((1u<<w)-1);}
static unsigned lms(const uint8_t *sig,unsigned siglen,const uint8_t *pub,unsigned publen,const uint8_t *msg,unsigned msglen){
 if(publen!=56||siglen<44||msglen>56)return 2;
 unsigned type=be32(pub),ots=be32(pub+4),h,w,p,ls;
 if(type==15)h=5;else if(type==16)h=10;else return 2;
 if(ots==10){w=2;p=133;ls=6;}else if(ots==11){w=4;p=67;ls=4;}else if(ots==12){w=8;p=34;ls=0;}else return 2;
 unsigned q=be32(sig),path_offset=44+p*32;
 if(siglen!=path_offset+h*32||q>=(1u<<h)||be32(sig+4)!=ots||be32(sig+40+p*32)!=type)return 2;
 const uint8_t *I=pub+8;
 uint8_t buffer[136] __attribute__((aligned(4))),Q[34] __attribute__((aligned(4))),y[32] __attribute__((aligned(4))),tmp[32] __attribute__((aligned(4)));
 prefix(buffer,I,q,0x8181);copy(buffer+22,sig+8,32);copy(buffer+54,msg,msglen);
 if(shake(buffer,54+msglen,Q))return 3;
 unsigned checksum=0;
 for(unsigned i=0;i<256/w;++i)checksum+=((1u<<w)-1)-coefficient(Q,i,w);
 checksum<<=ls;Q[32]=checksum>>8;Q[33]=checksum;
 for(unsigned i=0;i<p;++i){
  copy(y,sig+40+i*32,32);copy(buffer,I,16);put32(buffer+16,q);buffer[20]=i>>8;buffer[21]=i;
  for(unsigned j=coefficient(Q,i,w);j<(1u<<w)-1;++j){buffer[22]=j;copy(buffer+23,y,32);if(shake(buffer,55,y))return 3;}
  copy(Z+i*32,y,32);
 }
 /* Build the LM-OTS public-key aggregate below Z without overlapping it. */
 prefix(INPUT,I,q,0x8080);
 copy(INPUT+22,Z,p*32);
 if(shake(INPUT,22+p*32,y))return 3;
 unsigned node=(1u<<h)+q;
 prefix(buffer,I,node,0x8282);copy(buffer+22,y,32);
 if(shake(buffer,54,tmp))return 3;
 for(unsigned i=0;i<h;++i){
  prefix(buffer,I,node>>1,0x8383);
  const uint8_t *sibling=sig+path_offset+i*32;
  if(node&1){copy(buffer+22,sibling,32);copy(buffer+54,tmp,32);}
  else{copy(buffer+22,tmp,32);copy(buffer+54,sibling,32);}
  if(shake(buffer,86,tmp))return 3;
  node>>=1;
 }
 return equal(tmp,pub+24)?0:1;
}
static unsigned verify(unsigned kind,unsigned siglen){
 if(kind==6)return lms(SIGN,siglen,PUB,56,MSG,56);
 if(kind!=7||siglen<4||be32(PUB)!=1||be32(SIGN)!=0)return 2;
 return lms(SIGN+4,siglen-4,PUB+4,56,MSG,56);
}
unsigned pq_hash_test(unsigned n,uint32_t out[128]){
 for(unsigned i=0;i<128;++i)out[i]=0;
 out[0]=0x5153484b;out[2]=n;if(n>4780)return 1;
 for(unsigned i=0;i<n;++i)SIGN[i]=(uint8_t)(i%251+1);
 unsigned old=R(SSS);uint8_t value[32] __attribute__((aligned(4)));hash_error=hash_calls=hash_cycles=0;R(SSS)=0x500;
 unsigned rc=shake(SIGN,n,value);out[1]=hash_cycles;
 if(!rc){for(unsigned i=0;i<8;++i)out[6+i]=(unsigned)value[4*i]|((unsigned)value[4*i+1]<<8)|((unsigned)value[4*i+2]<<16)|((unsigned)value[4*i+3]<<24);R(SSS)=old;}
 return rc;
}
unsigned __attribute__((optimize("O3"))) pq_benchmark(unsigned kind,unsigned which,unsigned repeats,uint32_t out[128]){
 for(unsigned i=0;i<128;++i)out[i]=0;
 out[0]=0x50514231;out[2]=56;out[3]=repeats;out[4]=which;out[10]=(kind==7)?1:0;
 unsigned siglen=(kind==7)?4464:4460;out[11]=siglen;out[12]=(kind==7)?60:56;
 if((kind!=6&&kind!=7)||which>6||!repeats||repeats>100)return 1;
 unsigned old_sss=R(SSS),offset=(kind==7)?4:0,change=0;
 uint8_t *mutated=0;unsigned old_q=0;
 if(which==1)mutated=SIGN+32;
 if(which==2)mutated=MSG;
 if(which==3)mutated=PUB+out[12]-1;
 if(which==4)--siglen;
 if(which==5)mutated=SIGN+offset+7;
 if(which==6){old_q=be32(SIGN+offset);put32(SIGN+offset,0xffffffff);}
 if(mutated){change=*mutated;*mutated^=1;}
 R(SSS)=0x500;hash_calls=hash_cycles=hash_error=0;fence();
 unsigned expected=(which==0)?0:((which<=3)?1:2),status=verify(kind,siglen);
 if(status!=expected)goto done;
 hash_calls=hash_cycles=0;
 unsigned start=ticks();
 for(unsigned i=0;i<repeats;++i){status=verify(kind,siglen);if(status!=expected)break;}
 fence();out[1]=ticks()-start;
done:
 out[5]=status;out[6]=hash_calls;out[7]=hash_cycles;
 out[8]=be32(PUB+offset);out[9]=be32(PUB+offset+4);
 if(mutated)*mutated=(uint8_t)change;
 if(which==6)put32(SIGN+offset,old_q);
 if(!hash_error){R(SSS)=old_sss;fence();}
 /* Wrong valid/reject decision or hardware failure stops dependent requests. */
 return hash_error?3:(status!=expected?4:0);
}
